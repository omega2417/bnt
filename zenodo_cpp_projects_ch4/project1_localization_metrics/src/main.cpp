// =============================================================================
//  Localization-Quality Evaluation for Spatial Attribution
//  Reference implementation of Section 4.4 ("Оцінювання локалізаційної якості
//  та меж застосовності").
//
//  Single-translation-unit C++17, no external dependencies, self-contained
//  synthetic evaluation set. Compiles and runs as-is on OnlineGDB, g++/clang++
//  (>= C++17) or MSVC.
//
//  Given a set of localization episodes -- each with a point error, an
//  availability flag, true/predicted policy zone, a per-episode posterior
//  uncertainty radius and the true radial offset -- the program computes the
//  full localization-quality panel of Section 4.4:
//
//    §4.4.2  central error: MAE, median, RMSE, MAD, 20% trimmed mean
//    §4.4.3  tail: empirical CDF / CCDF, P50/P75/P90/P95/P99
//    §4.4.4  zonal correctness (overall + per zone)
//    §4.4.5  availability, time-to-localize (conditional vs unconditional)
//    §4.4.8  HPD coverage at 50/80/90/95 %, area, sharpness | coverage,
//            zonal Brier score, NLL
//    §4.3.8  block bootstrap 95% CIs (resample session/site BLOCKS, not frames)
//    §4.4.2  trajectory-aware aggregation (within-trajectory, then between)
//
//  Two arms (a weak baseline and the proposed method) are evaluated on the same
//  frozen episodes so the panel is legible; the paired statistical COMPARISON
//  of arms is the subject of the companion project (Section 4.3). Point error
//  is reported only for episodes with coordinate ground truth (§4.4.2).
//
//  Synthetic illustration; numbers are NOT dissertation results. Operating
//  points remain to_be_validated. License: MIT.
// =============================================================================

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace lq {

// ---------------------------------------------------------------------------
// Deterministic RNG (no <random>, no Date/rand): reproducible on OnlineGDB.
// SplitMix64 -> uniform, plus Box-Muller normal and a Rayleigh radial draw.
// ---------------------------------------------------------------------------
struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed) {}
    uint64_t next() {
        uint64_t z = (s += 0x9E3779B97F4A7C15ULL);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
    double u01() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
    double normal() {
        double u1 = std::max(1e-12, u01()), u2 = u01();
        return std::sqrt(-2.0 * std::log(u1)) * std::cos(2.0 * M_PI * u2);
    }
};

// ---------------------------------------------------------------------------
// One evaluation episode (the unit of analysis, §4.2.1 / §4.4.1).
// ---------------------------------------------------------------------------
struct Episode {
    bool   available;     // was a fix produced at all? (§4.4.5)
    double error_m;       // point (MAP) error in metres; valid iff available
    double sigma_m;       // reported 1-sigma posterior radius (2-D isotropic)
    double radial_m;      // true radial offset of ground truth from the estimate
    int    zone_true;     // ground-truth policy zone
    int    zone_pred;     // predicted (MAP) zone
    double zbrier;        // zonal Brier score for this episode (§4.4.8)
    double nll;           // per-episode negative log-likelihood (§4.4.8)
    double ttl_s;         // time-to-localize (seconds), valid iff available
    int    block_id;      // session/site block for block bootstrap (§4.3.8)
    int    traj_id;       // trajectory id for trajectory-aware aggregation
};

// ---------------------------------------------------------------------------
// Quantile of a sorted vector by linear interpolation (type-7).
// ---------------------------------------------------------------------------
static double quantile_sorted(const std::vector<double>& v, double p) {
    if (v.empty()) return std::nan("");
    if (v.size() == 1) return v[0];
    double h = (v.size() - 1) * p;
    size_t lo = (size_t)std::floor(h);
    double frac = h - lo;
    if (lo + 1 >= v.size()) return v.back();
    return v[lo] * (1 - frac) + v[lo + 1] * frac;
}

// ---------------------------------------------------------------------------
// §4.4.2 Central-tendency error metrics over available episodes.
// ---------------------------------------------------------------------------
struct Central { double mae, median, rmse, mad, trimmed20; int n; };

static Central central_metrics(const std::vector<double>& err) {
    Central c{}; c.n = (int)err.size();
    if (err.empty()) { c.mae = c.median = c.rmse = c.mad = c.trimmed20 = std::nan(""); return c; }
    std::vector<double> e = err;
    std::sort(e.begin(), e.end());
    double s = 0, s2 = 0;
    for (double x : e) { s += x; s2 += x * x; }
    c.mae = s / e.size();
    c.rmse = std::sqrt(s2 / e.size());
    c.median = quantile_sorted(e, 0.5);
    // MAD about the median.
    std::vector<double> ad(e.size());
    for (size_t i = 0; i < e.size(); ++i) ad[i] = std::fabs(e[i] - c.median);
    std::sort(ad.begin(), ad.end());
    c.mad = quantile_sorted(ad, 0.5);
    // 20% trimmed mean.
    size_t k = (size_t)std::floor(0.20 * e.size());
    double ts = 0; size_t cnt = 0;
    for (size_t i = k; i + k < e.size(); ++i) { ts += e[i]; ++cnt; }
    c.trimmed20 = cnt ? ts / cnt : c.mae;
    return c;
}

// ---------------------------------------------------------------------------
// §4.4.8 HPD coverage & sharpness for a 2-D isotropic Gaussian posterior.
// The radial offset r has CDF 1 - exp(-r^2 / (2 sigma^2)) (Rayleigh), so the
// HPD radius at level alpha is R(alpha) = sigma * sqrt(-2 ln(1-alpha)); coverage
// is the empirical fraction with r <= R(alpha); area = pi R^2 (sharpness).
// ---------------------------------------------------------------------------
struct HpdRow { double level, coverage, mean_area, sharp_given_cov; };

static std::vector<HpdRow> hpd_panel(const std::vector<Episode>& ep) {
    const double levels[4] = {0.50, 0.80, 0.90, 0.95};
    std::vector<HpdRow> rows;
    for (double a : levels) {
        double kR = std::sqrt(-2.0 * std::log(1.0 - a));
        int n = 0, covered = 0; double area_sum = 0, area_cov_sum = 0;
        for (const auto& e : ep) {
            if (!e.available) continue;
            ++n;
            double R = e.sigma_m * kR;
            double area = M_PI * R * R;
            area_sum += area;
            if (e.radial_m <= R) { ++covered; area_cov_sum += area; }
        }
        HpdRow r{a, n ? (double)covered / n : std::nan(""),
                 n ? area_sum / n : std::nan(""),
                 covered ? area_cov_sum / covered : std::nan("")};
        rows.push_back(r);
    }
    return rows;
}

// ---------------------------------------------------------------------------
// §4.3.8 Block bootstrap: resample BLOCKS (sessions/sites) with replacement,
// recompute a statistic, return a percentile 95% CI. Frames within a block are
// NOT independent, so the block is the resampling unit.
// ---------------------------------------------------------------------------
template <class Stat>
static void block_bootstrap_ci(const std::vector<Episode>& ep, Stat stat,
                               int B, Rng& rng, double& lo, double& hi) {
    // group episode indices by block
    int maxb = 0; for (const auto& e : ep) maxb = std::max(maxb, e.block_id);
    std::vector<std::vector<int>> blocks(maxb + 1);
    for (int i = 0; i < (int)ep.size(); ++i) blocks[ep[i].block_id].push_back(i);
    std::vector<int> present;
    for (int b = 0; b <= maxb; ++b) if (!blocks[b].empty()) present.push_back(b);

    std::vector<double> stats; stats.reserve(B);
    for (int b = 0; b < B; ++b) {
        std::vector<Episode> resample;
        for (size_t k = 0; k < present.size(); ++k) {
            int pick = present[(size_t)(rng.u01() * present.size()) % present.size()];
            for (int idx : blocks[pick]) resample.push_back(ep[idx]);
        }
        double v = stat(resample);
        if (std::isfinite(v)) stats.push_back(v);
    }
    std::sort(stats.begin(), stats.end());
    lo = quantile_sorted(stats, 0.025);
    hi = quantile_sorted(stats, 0.975);
}

// Statistic helpers usable by the bootstrap.
static double stat_mae(const std::vector<Episode>& ep) {
    double s = 0; int n = 0;
    for (const auto& e : ep) if (e.available) { s += e.error_m; ++n; }
    return n ? s / n : std::nan("");
}
static double stat_p95(const std::vector<Episode>& ep) {
    std::vector<double> e;
    for (const auto& x : ep) if (x.available) e.push_back(x.error_m);
    std::sort(e.begin(), e.end());
    return quantile_sorted(e, 0.95);
}

// ---------------------------------------------------------------------------
// §4.4.2 Trajectory-aware aggregation: average within each trajectory first,
// then across trajectories, so long records do not dominate short ones.
// ---------------------------------------------------------------------------
static double trajectory_aware_mae(const std::vector<Episode>& ep) {
    int maxt = 0; for (const auto& e : ep) maxt = std::max(maxt, e.traj_id);
    std::vector<double> sum(maxt + 1, 0.0); std::vector<int> cnt(maxt + 1, 0);
    for (const auto& e : ep) if (e.available) { sum[e.traj_id] += e.error_m; cnt[e.traj_id]++; }
    double acc = 0; int nt = 0;
    for (int t = 0; t <= maxt; ++t) if (cnt[t]) { acc += sum[t] / cnt[t]; ++nt; }
    return nt ? acc / nt : std::nan("");
}

// ---------------------------------------------------------------------------
// Reporting helpers
// ---------------------------------------------------------------------------
static void print_arm(const std::string& name, const std::vector<Episode>& ep, Rng& rng) {
    std::cout << std::fixed << std::setprecision(3);
    std::cout << "\n================= ARM: " << name << " =================\n";

    // Availability (§4.4.5).
    int total = (int)ep.size(), avail = 0; double ttl_sum = 0;
    std::vector<double> err;
    for (const auto& e : ep) if (e.available) { ++avail; err.push_back(e.error_m); ttl_sum += e.ttl_s; }
    double availability = total ? (double)avail / total : 0;
    std::cout << "availability (§4.4.5)   : " << availability
              << "  (" << avail << "/" << total << ")   mean TTL = "
              << (avail ? ttl_sum / avail : std::nan("")) << " s\n";

    // Central error (§4.4.2) on available cases.
    Central c = central_metrics(err);
    std::cout << "central error (§4.4.2)  : MAE=" << c.mae << "  median=" << c.median
              << "  RMSE=" << c.rmse << "  MAD=" << c.mad
              << "  trimmed20=" << c.trimmed20 << " m\n";

    // Tail quantiles (§4.4.3).
    std::vector<double> e = err; std::sort(e.begin(), e.end());
    std::cout << "tail quantiles (§4.4.3) : P50=" << quantile_sorted(e, 0.50)
              << "  P75=" << quantile_sorted(e, 0.75)
              << "  P90=" << quantile_sorted(e, 0.90)
              << "  P95=" << quantile_sorted(e, 0.95)
              << "  P99=" << quantile_sorted(e, 0.99) << " m\n";

    // Empirical CDF at a few tolerance thresholds.
    std::cout << "empirical CDF F(d)      : ";
    for (double d : {2.0, 3.0, 5.0, 8.0}) {
        int le = 0; for (double x : e) if (x <= d) ++le;
        std::cout << "F(" << (int)d << "m)=" << (e.empty() ? 0.0 : (double)le / e.size()) << "  ";
    }
    std::cout << "\n";

    // Zonal correctness (§4.4.4).
    int zc = 0; for (const auto& x : ep) if (x.available && x.zone_true == x.zone_pred) ++zc;
    std::cout << "zonal accuracy (§4.4.4) : " << (avail ? (double)zc / avail : std::nan("")) << "\n";

    // Zonal Brier + NLL (§4.4.8).
    double zb = 0, nll = 0; int nn = 0;
    for (const auto& x : ep) if (x.available) { zb += x.zbrier; nll += x.nll; ++nn; }
    std::cout << "zonal Brier / NLL       : Brier=" << (nn ? zb / nn : std::nan(""))
              << "  NLL=" << (nn ? nll / nn : std::nan("")) << "\n";

    // HPD coverage & sharpness (§4.4.8).
    std::cout << "HPD coverage & sharpness (§4.4.8):\n";
    std::cout << "   level  |  coverage  |  mean area (m^2)  |  sharpness|coverage\n";
    for (const auto& r : hpd_panel(ep))
        std::cout << "   " << std::setw(4) << (int)(r.level * 100) << "%  |   "
                  << std::setw(6) << r.coverage << "   |     "
                  << std::setw(9) << r.mean_area << "     |     "
                  << std::setw(9) << r.sharp_given_cov << "\n";

    // Block bootstrap 95% CIs (§4.3.8).
    double lo, hi;
    block_bootstrap_ci(ep, stat_mae, 2000, rng, lo, hi);
    std::cout << "MAE 95% CI (block boot) : [" << lo << ", " << hi << "] m\n";
    block_bootstrap_ci(ep, stat_p95, 2000, rng, lo, hi);
    std::cout << "P95 95% CI (block boot) : [" << lo << ", " << hi << "] m\n";

    // Trajectory-aware MAE (§4.4.2).
    std::cout << "trajectory-aware MAE    : " << trajectory_aware_mae(ep)
              << " m  (within-then-between)\n";
}

// ---------------------------------------------------------------------------
// Synthetic evaluation-set generator.
//   error_m ~ |N(0, base)| + occasional tail; sigma_m reported by the method;
//   radial offset r ~ Rayleigh(sigma_true) with sigma_true tied to calibration.
//   The "proposed" arm is better calibrated (radial ~ sigma) and has a lighter
//   tail; the "baseline" arm is over-confident (sigma too small) with a heavier
//   tail -- so HPD coverage < nominal for the baseline.
// ---------------------------------------------------------------------------
static std::vector<Episode> make_set(Rng& rng, bool proposed) {
    std::vector<Episode> ep;
    const int n_blocks = 12, per_block = 20;
    for (int b = 0; b < n_blocks; ++b) {
        for (int j = 0; j < per_block; ++j) {
            Episode e{};
            e.block_id = b;
            e.traj_id = b * 2 + (j % 2);      // two short trajectories per block
            // availability: proposed slightly higher
            double pa = proposed ? 0.95 : 0.88;
            e.available = rng.u01() < pa;

            double base = proposed ? 2.2 : 3.4;      // metres
            double tailp = proposed ? 0.05 : 0.14;   // heavy-tail probability
            double err = std::fabs(rng.normal()) * base;
            if (rng.u01() < tailp) err += 4.0 + std::fabs(rng.normal()) * (proposed ? 4.0 : 8.0);
            e.error_m = err;

            // Reported posterior sigma. Proposed: honest (sigma ~ true spread).
            // Baseline: overconfident (reports smaller sigma than reality).
            double sigma_true = proposed ? 2.4 : 3.6;
            e.sigma_m = proposed ? sigma_true : sigma_true * 0.6;  // baseline underreports
            // True radial offset drawn from the TRUE spread (Rayleigh via 2 normals).
            double gx = rng.normal() * sigma_true, gy = rng.normal() * sigma_true;
            e.radial_m = std::hypot(gx, gy);

            // Zones: 3 zones; predicted matches truth more often for proposed.
            e.zone_true = (int)(rng.u01() * 3);
            double zacc = proposed ? 0.90 : 0.74;
            e.zone_pred = (rng.u01() < zacc) ? e.zone_true : (e.zone_true + 1) % 3;

            // Zonal Brier & NLL from a predicted zone-probability vector.
            double pmax = proposed ? 0.82 : 0.62;
            double p[3];
            for (int z = 0; z < 3; ++z) p[z] = (z == e.zone_pred) ? pmax : (1 - pmax) / 2;
            double zb = 0; for (int z = 0; z < 3; ++z) { double y = (z == e.zone_true); zb += (p[z] - y) * (p[z] - y); }
            e.zbrier = zb;
            e.nll = -std::log(std::max(1e-9, p[e.zone_true]));

            e.ttl_s = (proposed ? 1.8 : 2.6) + std::fabs(rng.normal()) * 0.5;
            ep.push_back(e);
        }
    }
    return ep;
}

}  // namespace lq

int main() {
    using namespace lq;
    Rng rng(20260730ULL);

    std::cout << "Reference implementation of Section 4.4 -- Localization-Quality Evaluation.\n"
              << "Synthetic frozen evaluation set (illustration; NOT dissertation results).\n";

    std::vector<Episode> baseline = make_set(rng, false);
    std::vector<Episode> proposed = make_set(rng, true);

    print_arm("baseline (RSSI trilateration)", baseline, rng);
    print_arm("proposed (hybrid Bayesian)",  proposed, rng);

    std::cout << "\nReading (Section 4.4): point accuracy (MAE/median/RMSE) is separated from\n"
                 "posterior honesty (HPD coverage) and sharpness. An arm with lower MAE but\n"
                 "HPD coverage below nominal is OVER-CONFIDENT and unsafe for AUTO -- exactly\n"
                 "what the baseline shows here (reported sigma too small => coverage < level).\n";
    return 0;
}
