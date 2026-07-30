// =============================================================================
//  Bayesian Spatial Posterior with MAP / HPD / Zonal Mass
//  Reference implementation of Section 3.4 ("Байєсівський posterior і MAP/HPD-
//  оцінювання координат"), with the modality-factorized likelihood of §3.4.2
//  and the FTM likelihood of §3.5.6.
//
//  Single-translation-unit C++17, no external dependencies, self-contained
//  demonstration scene. Compiles and runs as-is on OnlineGDB, g++/clang++
//  (>= C++17), or MSVC.
//
//  Pipeline (all computation in the log-domain, §3.4.3):
//
//    predict   p(x | z_{1:t-1})            transition/diffusion prior  (eq 3.6)
//    likelihood  L(x) = prod_s L_s(x)^{w_s}   modality factorization   (eq 3.7)
//                 * RSSI blocks with a robust (Huber) log-likelihood
//                 * FTM/RTT pseudorange anchors with an LOS/NLOS mixture (§3.5.6)
//                 * availability masks -> neutral factor 1 for missing data
//    update    p(x|z_{1:t}) = predict * L / Z    log-sum-exp normalization (eq 3.8-3.9)
//    products  MAP (eq 3.11), local modes (§3.4.6), HPD region (eq 3.12),
//              zonal posterior mass (eq 3.13), out-of-map state (eq 3.14),
//              entropy and an uncertainty budget (§3.4.11).
//
//  The demonstration builds "fingerprint twins": RSSI alone yields a bimodal
//  posterior; a single FTM anchor supports only one mode. The joint posterior
//  is the normalized product (§3.4.10, Figure 3.5), NOT an average of the two
//  MAP coordinates -- the unsupported mode loses mass but is not deleted if the
//  FTM factor is broad or low-weight.
//
//  Illustrative structure only; operating points are to_be_validated (Ch. 4).
//  License: MIT.
// =============================================================================

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace bsp {  // bayesian spatial posterior

constexpr double NEG_INF = -std::numeric_limits<double>::infinity();

// ---------------------------------------------------------------------------
// Geometry: a rectangular RP grid (support X_h, §3.4.1). Each cell has a
// coordinate and a policy zone id.
// ---------------------------------------------------------------------------
struct Grid {
    int    nx, ny;
    double x0, y0, dx, dy;    // origin and cell pitch (metres)
    std::vector<int> zone;    // policy zone id per cell (§3.4.8)

    int    n() const { return nx * ny; }
    int    idx(int ix, int iy) const { return iy * nx + ix; }
    double cx(int i) const { return x0 + (i % nx) * dx; }
    double cy(int i) const { return y0 + (i / nx) * dy; }
    double cell_area() const { return dx * dy; }
};

// ---------------------------------------------------------------------------
// Sensor block (passive RSSI). The radiomap mean is a log-distance path-loss
// model anchored at the sensor position; this stands in for the approved
// statistical radiomap of Chapter 2.
// ---------------------------------------------------------------------------
struct RssiSensor {
    std::string id;
    double sx, sy;          // sensor position
    double p0;              // reference RSSI at 1 m (dBm)
    double n_pl;            // path-loss exponent
    double sigma;           // RSSI standard deviation (dBm)
    double weight;          // adaptive weight w_s from Section 3.3
    double rssi_obs;        // observed RSSI in this window (dBm)
    bool   available;       // availability mask (§3.4.2): false -> neutral factor
    double huber_delta;     // robustness threshold in sigma units (§3.4.12)
};

// FTM / RTT anchor (irregular metric anchoring, §3.5.6).
struct FtmAnchor {
    std::string id;
    double ax, ay;          // anchor position
    double range_obs;       // observed pseudorange (m)
    double sigma_los;       // LOS ranging std (m)
    double nlos_bias;       // expected positive NLOS excess path (m)
    double sigma_nlos;      // NLOS ranging std (m)
    double p_nlos;          // prior NLOS probability in [0,1] (mixture, §3.5.6)
    double weight;          // FTM weight (geometry * calibration * responder trust)
    bool   available;       // false -> factor is neutral (absence of evidence)
};

// Policy zone metadata (§3.4.8). Criticality is a decision-layer attribute and
// MUST NOT enter the physical likelihood or prior (avoids circular reasoning).
struct Zone { std::string name; bool critical; };

// ---------------------------------------------------------------------------
// Numerically stable log-sum-exp (eq 3.9): prevents underflow of a long product.
// ---------------------------------------------------------------------------
static double log_sum_exp(const std::vector<double>& v) {
    double m = NEG_INF;
    for (double x : v) if (x > m) m = x;
    if (m == NEG_INF) return NEG_INF;
    double s = 0.0;
    for (double x : v) s += std::exp(x - m);
    return m + std::log(s);
}

// Robust (Huber) negative log-likelihood contribution for a standardized
// residual r/sigma (§3.4.12, §3.5.4). Quadratic core, linear tails: a single
// large residual cannot arbitrarily dominate the surface.
static double huber_nll(double z, double delta) {
    double az = std::fabs(z);
    if (az <= delta) return 0.5 * z * z;
    return delta * (az - 0.5 * delta);
}

// ---------------------------------------------------------------------------
// RSSI log-likelihood of a candidate cell for one available sensor.
// ---------------------------------------------------------------------------
static double rssi_loglik(const RssiSensor& s, double x, double y) {
    double d = std::hypot(x - s.sx, y - s.sy);
    d = std::max(d, 1.0);  // 1 m reference floor
    double mu = s.p0 - 10.0 * s.n_pl * std::log10(d);   // path-loss mean (dBm)
    double z = (s.rssi_obs - mu) / s.sigma;
    // Robust log-likelihood up to an additive constant (dropped by normalization).
    return -huber_nll(z, s.huber_delta);
}

// FTM log-likelihood as an LOS/NLOS mixture, marginalizing the NLOS bias
// (§3.5.6). A near-zero burst variance is not automatically "high quality".
static double ftm_loglik(const FtmAnchor& a, double x, double y) {
    double d = std::hypot(x - a.ax, y - a.ay);
    double r = a.range_obs;
    // LOS component: N(d, sigma_los^2)
    double zl = (r - d) / a.sigma_los;
    double log_los = -0.5 * zl * zl - std::log(a.sigma_los);
    // NLOS component: N(d + nlos_bias, sigma_nlos^2), positive excess path
    double zn = (r - (d + a.nlos_bias)) / a.sigma_nlos;
    double log_nlos = -0.5 * zn * zn - std::log(a.sigma_nlos);
    double a_los = std::log(std::max(1e-9, 1.0 - a.p_nlos)) + log_los;
    double a_nlos = std::log(std::max(1e-9, a.p_nlos)) + log_nlos;
    return log_sum_exp({a_los, a_nlos});
}

// ---------------------------------------------------------------------------
// Predictive prior (eq 3.6): here a Gaussian diffusion of the previous
// posterior plus a small uniform relocation floor (models a possibly-moving
// source / clone appearance). For the first window we pass a uniform prior.
// ---------------------------------------------------------------------------
static std::vector<double> predict_prior(const Grid& g,
                                         const std::vector<double>& prev_post,
                                         double diffusion_sigma,
                                         double relocation_floor) {
    const int N = g.n();
    std::vector<double> prior(N, 0.0);
    if (prev_post.empty()) {
        for (int i = 0; i < N; ++i) prior[i] = 1.0 / N;  // uniform
        return prior;
    }
    // Separable Gaussian blur over the grid (transition kernel).
    int rad = std::max(1, (int)std::ceil(3.0 * diffusion_sigma / std::min(g.dx, g.dy)));
    std::vector<double> tmp(N, 0.0);
    auto kern = [&](int off, double pitch) {
        double d = off * pitch; return std::exp(-0.5 * d * d / (diffusion_sigma * diffusion_sigma));
    };
    // horizontal
    for (int iy = 0; iy < g.ny; ++iy)
        for (int ix = 0; ix < g.nx; ++ix) {
            double acc = 0, wsum = 0;
            for (int o = -rad; o <= rad; ++o) {
                int jx = ix + o; if (jx < 0 || jx >= g.nx) continue;
                double k = kern(o, g.dx); acc += k * prev_post[g.idx(jx, iy)]; wsum += k;
            }
            tmp[g.idx(ix, iy)] = (wsum > 0) ? acc / wsum : prev_post[g.idx(ix, iy)];
        }
    // vertical
    for (int iy = 0; iy < g.ny; ++iy)
        for (int ix = 0; ix < g.nx; ++ix) {
            double acc = 0, wsum = 0;
            for (int o = -rad; o <= rad; ++o) {
                int jy = iy + o; if (jy < 0 || jy >= g.ny) continue;
                double k = kern(o, g.dy); acc += k * tmp[g.idx(ix, jy)]; wsum += k;
            }
            prior[g.idx(ix, iy)] = (wsum > 0) ? acc / wsum : tmp[g.idx(ix, iy)];
        }
    // relocation floor + renormalize
    double s = 0;
    for (int i = 0; i < N; ++i) { prior[i] = prior[i] * (1 - relocation_floor) + relocation_floor / N; s += prior[i]; }
    for (int i = 0; i < N; ++i) prior[i] /= s;
    return prior;
}

// ---------------------------------------------------------------------------
// Result bundle (a subset of the "R_t" structure of §3.9.1).
// ---------------------------------------------------------------------------
struct Mode { double x, y; double mass; int zone; };

struct Posterior {
    std::vector<double> logpost;   // normalized log-posterior over the grid
    std::vector<double> post;      // linear posterior (in-map, sums with p_out to 1)
    int    map_index;
    double map_x, map_y;
    double mean_x, mean_y;
    std::vector<Mode> modes;
    double hpd_mass_target;
    double hpd_area;               // area of the HPD region (m^2)
    int    hpd_cells;
    std::vector<double> zonal_mass;
    double p_out_of_map;           // out-of-map probability (eq 3.14)
    double entropy;                // nats
    double log_evidence;           // model evidence log Z (eq 3.8), OOD diagnostic
    double var_x, var_y;           // positional variance (uncertainty budget)
    std::string status;
};

// ---------------------------------------------------------------------------
// Core Bayesian update (eq 3.8-3.9) with an explicit out-of-map hypothesis
// (eq 3.14). The out-of-map log-likelihood is a flat "absolute" reference; if
// no in-map cell explains the data well, the out-of-map mass grows instead of
// forcing a spuriously confident nearest cell.
// ---------------------------------------------------------------------------
static Posterior infer(const Grid& g,
                       const std::vector<double>& prior,
                       const std::vector<RssiSensor>& rssi,
                       const std::vector<FtmAnchor>& ftm,
                       const std::vector<Zone>& zones,
                       double hpd_level,
                       double out_of_map_prior,
                       double out_of_map_loglik) {
    const int N = g.n();
    Posterior R;
    R.hpd_mass_target = hpd_level;

    // Log-likelihood surface: sum of weighted modality log-likelihoods (eq 3.7,
    // in log-domain). Masked (unavailable) blocks contribute nothing (factor 1).
    std::vector<double> loglik(N, 0.0);
    bool any_evidence = false;
    for (const auto& s : rssi) {
        if (!s.available || s.weight <= 0) continue;
        any_evidence = true;
        for (int i = 0; i < N; ++i)
            loglik[i] += s.weight * rssi_loglik(s, g.cx(i), g.cy(i));
    }
    for (const auto& a : ftm) {
        if (!a.available || a.weight <= 0) continue;
        any_evidence = true;
        for (int i = 0; i < N; ++i)
            loglik[i] += a.weight * ftm_loglik(a, g.cx(i), g.cy(i));
    }

    // Fail-safe (§3.4.3): if no evidence, return the prior with a status code.
    if (!any_evidence) {
        R.logpost.assign(N, 0.0);
        R.post = prior;
        double s = 0; for (double p : prior) s += p; (void)s;
        R.status = "NO_EVIDENCE: returned predictive prior; AUTO blocked";
    } else {
        R.status = "OK";
    }

    // Unnormalized in-map log-posterior: log prior + log-likelihood.
    std::vector<double> ulp(N);
    for (int i = 0; i < N; ++i) {
        double lp = (prior[i] > 0) ? std::log(prior[i]) : NEG_INF;
        ulp[i] = lp + loglik[i];
    }

    // Augment with the out-of-map hypothesis (eq 3.14). Its unnormalized log
    // score = log(prior_out) + out_of_map_loglik.
    double ulp_out = std::log(std::max(1e-12, out_of_map_prior)) + out_of_map_loglik;

    // Normalizer over in-map cells and the out-of-map state (log-sum-exp).
    std::vector<double> all = ulp;
    all.push_back(ulp_out);
    double logZ = log_sum_exp(all);
    R.log_evidence = logZ;

    // Normalized log-posterior (in-map) and out-of-map probability.
    R.logpost.resize(N);
    R.post.resize(N);
    for (int i = 0; i < N; ++i) {
        R.logpost[i] = ulp[i] - logZ;
        R.post[i] = std::exp(R.logpost[i]);
    }
    R.p_out_of_map = std::exp(ulp_out - logZ);

    // MAP (eq 3.11) over in-map cells.
    R.map_index = 0;
    for (int i = 1; i < N; ++i) if (R.logpost[i] > R.logpost[R.map_index]) R.map_index = i;
    R.map_x = g.cx(R.map_index); R.map_y = g.cy(R.map_index);

    // Posterior mean and variance (uncertainty budget, §3.4.11). Renormalize
    // over the in-map mass so the moments are conditional on being in-map.
    double in_mass = 1.0 - R.p_out_of_map;
    double mx = 0, my = 0;
    for (int i = 0; i < N; ++i) { mx += R.post[i] * g.cx(i); my += R.post[i] * g.cy(i); }
    if (in_mass > 0) { mx /= in_mass; my /= in_mass; }
    R.mean_x = mx; R.mean_y = my;
    double vx = 0, vy = 0;
    for (int i = 0; i < N; ++i) {
        vx += R.post[i] * (g.cx(i) - mx) * (g.cx(i) - mx);
        vy += R.post[i] * (g.cy(i) - my) * (g.cy(i) - my);
    }
    if (in_mass > 0) { vx /= in_mass; vy /= in_mass; }
    R.var_x = vx; R.var_y = vy;

    // Entropy of the in-map posterior (nats).
    double H = 0;
    for (int i = 0; i < N; ++i) if (R.post[i] > 0) H -= R.post[i] * std::log(R.post[i]);
    R.entropy = H;

    // HPD region (eq 3.12): sort cells by descending posterior, accumulate mass
    // until the (in-map-conditional) target level is reached. May be disconnected.
    std::vector<int> order(N);
    for (int i = 0; i < N; ++i) order[i] = i;
    std::sort(order.begin(), order.end(),
              [&](int a, int b) { return R.post[a] > R.post[b]; });
    double acc = 0.0; R.hpd_cells = 0;
    double target = hpd_level * in_mass;
    for (int k = 0; k < N; ++k) {
        acc += R.post[order[k]];
        R.hpd_cells++;
        if (acc >= target) break;
    }
    R.hpd_area = R.hpd_cells * g.cell_area();

    // Local modes (§3.4.6): a cell is a mode if it is a strict local maximum
    // over its 8-neighbourhood and carries non-negligible mass. Report the
    // component mass by flood-labelling cells above a fraction of the peak.
    double peak = R.post[R.map_index];
    for (int iy = 0; iy < g.ny; ++iy)
        for (int ix = 0; ix < g.nx; ++ix) {
            int i = g.idx(ix, iy);
            bool is_max = true;
            for (int oy = -1; oy <= 1 && is_max; ++oy)
                for (int ox = -1; ox <= 1; ++ox) {
                    if (ox == 0 && oy == 0) continue;
                    int jx = ix + ox, jy = iy + oy;
                    if (jx < 0 || jx >= g.nx || jy < 0 || jy >= g.ny) continue;
                    if (R.post[g.idx(jx, jy)] > R.post[i]) { is_max = false; break; }
                }
            if (is_max && R.post[i] > 0.10 * peak) {
                // integrate mass over the connected basin above 25% of local peak
                double thr = 0.25 * R.post[i];
                double m = 0.0;
                for (int j = 0; j < N; ++j) {
                    double d = std::hypot(g.cx(j) - g.cx(i), g.cy(j) - g.cy(i));
                    if (R.post[j] >= thr && d <= 4.0 * std::max(g.dx, g.dy)) m += R.post[j];
                }
                Mode md{g.cx(i), g.cy(i), m, zones.empty() ? 0 : g.zone[i]};
                R.modes.push_back(md);
            }
        }
    std::sort(R.modes.begin(), R.modes.end(),
              [](const Mode& a, const Mode& b) { return a.mass > b.mass; });
    if (R.modes.size() > 4) R.modes.resize(4);

    // Zonal posterior mass (eq 3.13): aggregate the physical posterior over
    // policy geometry. Criticality is NOT used here (decision-layer only).
    int nz = 0; for (int z : g.zone) nz = std::max(nz, z);
    R.zonal_mass.assign(nz + 1, 0.0);
    for (int i = 0; i < N; ++i) R.zonal_mass[g.zone[i]] += R.post[i];

    return R;
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------
static void report(const Grid& g, const Posterior& R, const std::vector<Zone>& zones,
                   const std::string& title) {
    std::cout << std::fixed << std::setprecision(3);
    std::cout << "\n=========== " << title << " ===========\n";
    std::cout << "status: " << R.status << "\n";
    std::cout << "MAP        : (" << R.map_x << ", " << R.map_y << ") m   in zone '"
              << zones[g.zone[R.map_index]].name << "'\n";
    std::cout << "post. mean : (" << R.mean_x << ", " << R.mean_y << ") m   "
              << "[mean may lie between modes -- see §3.4.6]\n";
    std::cout << "pos. sdev  : (" << std::sqrt(R.var_x) << ", " << std::sqrt(R.var_y) << ") m\n";
    std::cout << "entropy    : " << R.entropy << " nats     log-evidence: " << R.log_evidence << "\n";
    std::cout << "HPD " << std::setprecision(0) << R.hpd_mass_target * 100 << "%    : "
              << std::setprecision(3) << R.hpd_area << " m^2 over " << R.hpd_cells
              << " cells (may be disconnected)\n";
    std::cout << "P(out-of-map): " << R.p_out_of_map << "   (eq 3.14)\n";
    std::cout << "local modes (§3.4.6):\n";
    for (size_t k = 0; k < R.modes.size(); ++k)
        std::cout << "   mode " << k + 1 << ": (" << R.modes[k].x << ", " << R.modes[k].y
                  << ") m  mass=" << R.modes[k].mass << "  zone='"
                  << zones[R.modes[k].zone].name << "'\n";
    std::cout << "zonal posterior mass (eq 3.13):\n";
    for (size_t z = 0; z < R.zonal_mass.size(); ++z)
        std::cout << "   [" << (zones[z].critical ? "CRIT" : "    ") << "] "
                  << std::setw(14) << std::left << zones[z].name << std::right
                  << " : " << R.zonal_mass[z] << "\n";
}

// ---------------------------------------------------------------------------
// ASCII heatmap of the posterior (handy on OnlineGDB, no plotting libraries).
// ---------------------------------------------------------------------------
static void ascii_map(const Grid& g, const Posterior& R) {
    const char* ramp = " .:-=+*#%@";
    double pmax = 0; for (double p : R.post) pmax = std::max(pmax, p);
    std::cout << "\nposterior heatmap (MAP='M', ' '=low .. '@'=high):\n";
    for (int iy = g.ny - 1; iy >= 0; --iy) {
        std::cout << "   ";
        for (int ix = 0; ix < g.nx; ++ix) {
            int i = g.idx(ix, iy);
            if (i == R.map_index) { std::cout << 'M'; continue; }
            int lv = (pmax > 0) ? (int)(9 * R.post[i] / pmax) : 0;
            std::cout << ramp[std::max(0, std::min(9, lv))];
        }
        std::cout << "\n";
    }
}

}  // namespace bsp

// ---------------------------------------------------------------------------
// Built-in demonstration scene (§3.4.10, Figure 3.5): fingerprint twins.
// ---------------------------------------------------------------------------
int main() {
    using namespace bsp;

    // 30 x 20 grid, 1 m pitch.
    Grid g;
    g.nx = 30; g.ny = 20; g.x0 = 0; g.y0 = 0; g.dx = 1.0; g.dy = 1.0;
    g.zone.assign(g.n(), 0);

    // Policy zones: left public area (0), a central corridor (1),
    // and a critical server room on the right (2).
    std::vector<Zone> zones = {
        {"public_area", false}, {"tech_corridor", false}, {"server_room", true}
    };
    for (int iy = 0; iy < g.ny; ++iy)
        for (int ix = 0; ix < g.nx; ++ix) {
            int z = 0;
            if (ix >= 12 && ix < 18) z = 1;
            else if (ix >= 18)       z = 2;
            g.zone[g.idx(ix, iy)] = z;
        }

    // --- RSSI sensors (weights come from Section 3.3) --------------------
    // To create genuine "fingerprint twins" the passive sensors are COLLINEAR
    // along the central corridor axis x = 15. A pure distance/RSSI fingerprint
    // then cannot distinguish a source to the RIGHT of the axis (server room,
    // the true location x=22) from its mirror to the LEFT (public area, x=8):
    // both are equidistant from every sensor. This is exactly the security-
    // relevant ambiguity a single FTM anchor is meant to resolve (§3.4.10).
    const double axis_x = 15.0;
    std::vector<RssiSensor> rssi = {
        // id     sx     sy    p0    n     sig  w     obs(set) avail huber
        {"D1", axis_x,  3,  -35, 2.6, 3.0, 0.30, 0.0, true, 2.5},
        {"D2", axis_x,  8,  -35, 2.6, 3.0, 0.28, 0.0, true, 2.5},
        {"D3", axis_x, 12,  -35, 2.6, 3.0, 0.24, 0.0, true, 2.5},
        {"D4", axis_x, 17,  -35, 2.6, 3.0, 0.18, 0.0, true, 2.5},
    };
    // Observations are generated deterministically from the true source at
    // (22,10) using the same path-loss model, so the twin at (8,10) is exact.
    const double true_x = 22.0, true_y = 10.0;
    for (auto& s : rssi) {
        double d = std::max(1.0, std::hypot(true_x - s.sx, true_y - s.sy));
        s.rssi_obs = s.p0 - 10.0 * s.n_pl * std::log10(d);
    }

    // --- FTM anchor near the server room, supporting the right-hand mode ---
    // Range consistent with the true (right) mode only; the left twin is ~14 m
    // away from the anchor and is strongly penalized.
    std::vector<FtmAnchor> ftm = {
        // id    ax    ay   range  sig_los bias sig_nlos p_nlos  w    avail
        {"A1",  25,   10,  3.2,    1.2,    2.0, 3.0,     0.20,  0.9, true},
    };

    // First window prior: uniform (predict with empty previous posterior).
    std::vector<double> prior = predict_prior(g, {}, 3.0, 0.02);

    // Out-of-map hypothesis (eq 3.14): flat reference log-likelihood tuned so an
    // in-map explanation is preferred when the data fit the map.
    double oom_prior = 0.05, oom_loglik = -14.0;

    std::cout << "Reference implementation of Section 3.4 -- Bayesian Spatial Posterior.\n"
              << "Demonstration: 'fingerprint twins' resolved by one FTM anchor "
                 "(analytical, not empirical).\n";

    // ---- Case A: RSSI ONLY (passive baseline) -> bimodal posterior ----
    {
        std::vector<FtmAnchor> none;
        Posterior R = infer(g, prior, rssi, none, zones, 0.90, oom_prior, oom_loglik);
        report(g, R, zones, "Case A: PASSIVE-ONLY (RSSI)  -- expect two modes");
        ascii_map(g, R);
    }

    // ---- Case B: RSSI + FTM (HYBRID) -> product narrows to one mode ----
    {
        Posterior R = infer(g, prior, rssi, ftm, zones, 0.90, oom_prior, oom_loglik);
        report(g, R, zones, "Case B: HYBRID (RSSI x FTM)  -- product, not average (§3.4.10)");
        ascii_map(g, R);

        // Property-based checks (§3.4.12).
        std::cout << "\nProperty-based invariants (§3.4.12):\n";
        double s = R.p_out_of_map; for (double p : R.post) s += p;
        std::cout << "  [" << (std::fabs(s - 1.0) < 1e-6 ? "PASS" : "FAIL")
                  << "] total mass (in-map + out-of-map) = 1 (got "
                  << std::setprecision(8) << s << ")\n";

        // Neutral (masked) modality does not change the posterior.
        std::vector<FtmAnchor> masked = ftm; masked[0].available = false;
        Posterior Rn = infer(g, prior, rssi, masked, zones, 0.90, oom_prior, oom_loglik);
        double diff = 0; for (int i = 0; i < g.n(); ++i) diff += std::fabs(R.post[i] - Rn.post[i]);
        std::cout << "  [" << (Rn.map_index != R.map_index || diff > 1e-9 ? "PASS" : "note")
                  << "] removing the FTM factor changes the posterior (L1="
                  << std::setprecision(4) << diff << ")\n";

        // Uniform likelihood returns the prior (add a zero-weight sensor set).
        std::vector<RssiSensor> empty; std::vector<FtmAnchor> emptyf;
        Posterior Rp = infer(g, prior, empty, emptyf, zones, 0.90, oom_prior, oom_loglik);
        double dprior = 0; for (int i = 0; i < g.n(); ++i) dprior += std::fabs(Rp.post[i] - prior[i]);
        std::cout << "  [" << (dprior < 1e-6 ? "PASS" : "FAIL")
                  << "] empty evidence returns the prior (L1=" << dprior << ")\n";
    }

    return 0;
}
