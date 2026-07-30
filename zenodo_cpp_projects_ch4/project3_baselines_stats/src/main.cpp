// =============================================================================
//  Baseline Localizers and Paired Statistical Comparison
//  Reference implementation of Section 4.3 ("Baseline-методи, абляції та
//  статистичний план порівняння"), subsections 4.3.2-4.3.5 (baselines) and
//  4.3.8 (parameter selection, repeats, statistical analysis).
//
//  Single-translation-unit C++17, no external dependencies, self-contained
//  synthetic radiomap. Runs as-is on OnlineGDB, g++/clang++ (>= C++17) or MSVC.
//
//  A synthetic statistical radiomap (M access points, log-distance path loss) is
//  surveyed on a reference-point grid; a frozen set of test points is localized
//  by four methods evaluated on the SAME inputs and compute budget (§4.3.1):
//
//    §4.3.2  RSSI path-loss trilateration (linear least squares)
//    §4.3.3  WKNN fingerprinting (inverse signal-distance weights)
//    §4.3.4  probabilistic RSSI baseline (Horus/Roos-style Gaussian likelihood)
//    proposed  robust WKNN over a denser survey (the method under test)
//
//  Paired errors (same test points, grouped in session/site BLOCKS) then feed
//  the statistical plan of §4.3.8:
//
//    block bootstrap 95% CI of MAE and of the paired MAE difference   [104]
//    Wilcoxon signed-rank test + Hodges-Lehmann median difference     [107]
//    McNemar test on paired zonal-correct proportions                 [106]
//    Cliff's delta nonparametric effect size                          [121]
//    Holm-Bonferroni multiplicity control across the comparison family
//    Friedman statistic + Nemenyi critical difference over all methods [108]
//
//  Synthetic illustration; numbers are NOT dissertation results. Operating
//  points remain to_be_validated. License: MIT.
// =============================================================================

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

namespace bs {

// Deterministic RNG (no <random>): reproducible on OnlineGDB.
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

// Standard normal / chi-square(1) tail via erfc.
static double normal_two_sided_p(double z) { return std::erfc(std::fabs(z) / std::sqrt(2.0)); }
static double chi2_1_p(double x) { return std::erfc(std::sqrt(std::max(0.0, x) / 2.0)); }

struct Pt { double x, y; };
static double dist(const Pt& a, const Pt& b) { return std::hypot(a.x - b.x, a.y - b.y); }

// ---------------------------------------------------------------------------
// Radiomap: AP positions + log-distance path loss. Fingerprint = RSSI vector.
// ---------------------------------------------------------------------------
struct Radiomap {
    std::vector<Pt> ap;
    double p0 = -35, n_pl = 2.8, sigma = 3.0;
    std::vector<double> fingerprint(const Pt& p, Rng* noise) const {
        std::vector<double> f(ap.size());
        for (size_t i = 0; i < ap.size(); ++i) {
            double d = std::max(1.0, dist(p, ap[i]));
            f[i] = p0 - 10 * n_pl * std::log10(d);
            if (noise) f[i] += noise->normal() * sigma;
        }
        return f;
    }
};

// A surveyed reference point: location + (noisy) fingerprint + zone.
struct RP { Pt loc; std::vector<double> fp; int zone; };

static int zone_of(const Pt& p) {          // 3 vertical zones on a 30 m span
    if (p.x < 10) return 0;
    if (p.x < 20) return 1;
    return 2;
}

// ---------------------------------------------------------------------------
// Baseline localizers. Each returns an estimated Pt for a test fingerprint.
// ---------------------------------------------------------------------------

// §4.3.2 RSSI path-loss trilateration via linear least squares.
static Pt trilaterate(const Radiomap& m, const std::vector<double>& fp) {
    // invert path loss to ranges
    int M = (int)m.ap.size();
    std::vector<double> r(M);
    for (int i = 0; i < M; ++i)
        r[i] = std::pow(10.0, (m.p0 - fp[i]) / (10 * m.n_pl));
    // linearize around the last anchor: 2*(x_i - x_M) x + 2*(y_i - y_M) y = b_i
    int ref = M - 1;
    double A00 = 0, A01 = 0, A11 = 0, b0 = 0, b1 = 0;
    for (int i = 0; i < ref; ++i) {
        double ax = 2 * (m.ap[i].x - m.ap[ref].x);
        double ay = 2 * (m.ap[i].y - m.ap[ref].y);
        double bi = (r[ref] * r[ref] - r[i] * r[i])
                  + (m.ap[i].x * m.ap[i].x - m.ap[ref].x * m.ap[ref].x)
                  + (m.ap[i].y * m.ap[i].y - m.ap[ref].y * m.ap[ref].y);
        A00 += ax * ax; A01 += ax * ay; A11 += ay * ay;
        b0 += ax * bi;  b1 += ay * bi;
    }
    double det = A00 * A11 - A01 * A01;
    if (std::fabs(det) < 1e-9) return {15, 10};
    return {(A11 * b0 - A01 * b1) / det, (-A01 * b0 + A00 * b1) / det};
}

// §4.3.3 WKNN fingerprinting: k nearest RPs in signal space, inverse-distance weights.
static Pt wknn(const std::vector<RP>& db, const std::vector<double>& fp, int k, bool robust) {
    std::vector<std::pair<double, int>> ds;
    for (size_t i = 0; i < db.size(); ++i) {
        double s = 0;
        for (size_t j = 0; j < fp.size(); ++j) {
            double diff = fp[j] - db[i].fp[j];
            s += robust ? std::fabs(diff) : diff * diff;   // L1 (robust) vs L2
        }
        ds.push_back({robust ? s : std::sqrt(s), (int)i});
    }
    std::partial_sort(ds.begin(), ds.begin() + std::min((size_t)k, ds.size()), ds.end());
    double wx = 0, wy = 0, ws = 0;
    for (int i = 0; i < k && i < (int)ds.size(); ++i) {
        double w = 1.0 / (ds[i].first + 1e-3);
        wx += w * db[ds[i].second].loc.x; wy += w * db[ds[i].second].loc.y; ws += w;
    }
    return {wx / ws, wy / ws};
}

// §4.3.4 Probabilistic Horus/Roos-style: Gaussian likelihood per RP, posterior
// (softmax over negative squared signal distance) weighted centroid.
static Pt probabilistic(const std::vector<RP>& db, const std::vector<double>& fp, double sigma) {
    double best = -1e300;
    std::vector<double> logl(db.size());
    for (size_t i = 0; i < db.size(); ++i) {
        double s = 0;
        for (size_t j = 0; j < fp.size(); ++j) {
            double d = fp[j] - db[i].fp[j];
            s += -0.5 * d * d / (sigma * sigma);
        }
        logl[i] = s; best = std::max(best, s);
    }
    double wx = 0, wy = 0, ws = 0;
    for (size_t i = 0; i < db.size(); ++i) {
        double w = std::exp(logl[i] - best);
        wx += w * db[i].loc.x; wy += w * db[i].loc.y; ws += w;
    }
    return {wx / ws, wy / ws};
}

// ---------------------------------------------------------------------------
// Statistics (§4.3.8)
// ---------------------------------------------------------------------------
static double mae(const std::vector<double>& e) {
    return e.empty() ? std::nan("") : std::accumulate(e.begin(), e.end(), 0.0) / e.size();
}

// Block bootstrap CI of a paired-difference statistic (resample blocks).
static void block_bootstrap_diff_ci(const std::vector<double>& ea, const std::vector<double>& eb,
                                    const std::vector<int>& block, int B, Rng& rng,
                                    double& lo, double& hi) {
    int maxb = 0; for (int b : block) maxb = std::max(maxb, b);
    std::vector<std::vector<int>> idx(maxb + 1);
    for (int i = 0; i < (int)block.size(); ++i) idx[block[i]].push_back(i);
    std::vector<int> present; for (int b = 0; b <= maxb; ++b) if (!idx[b].empty()) present.push_back(b);
    std::vector<double> stats;
    for (int b = 0; b < B; ++b) {
        double s = 0; int n = 0;
        for (size_t k = 0; k < present.size(); ++k) {
            int pick = present[(size_t)(rng.u01() * present.size()) % present.size()];
            for (int i : idx[pick]) { s += (ea[i] - eb[i]); ++n; }
        }
        stats.push_back(n ? s / n : 0);
    }
    std::sort(stats.begin(), stats.end());
    auto q = [&](double p) { double h = (stats.size() - 1) * p; size_t l = (size_t)h;
        return l + 1 < stats.size() ? stats[l] * (1 - (h - l)) + stats[l + 1] * (h - l) : stats.back(); };
    lo = q(0.025); hi = q(0.975);
}

// Wilcoxon signed-rank test (paired), normal approximation with tie handling.
struct Wilcox { double W_plus, z, p; int n; };
static Wilcox wilcoxon_signed_rank(const std::vector<double>& a, const std::vector<double>& b) {
    std::vector<double> d;
    for (size_t i = 0; i < a.size(); ++i) { double x = a[i] - b[i]; if (std::fabs(x) > 1e-12) d.push_back(x); }
    int n = (int)d.size();
    std::vector<std::pair<double, int>> ad(n);
    for (int i = 0; i < n; ++i) ad[i] = {std::fabs(d[i]), i};
    std::sort(ad.begin(), ad.end());
    std::vector<double> rank(n);
    for (int i = 0; i < n;) {                      // average ranks for ties
        int j = i; while (j < n && ad[j].first == ad[i].first) ++j;
        double r = (i + j + 1) / 2.0;
        for (int t = i; t < j; ++t) rank[ad[t].second] = r;
        i = j;
    }
    double Wp = 0; for (int i = 0; i < n; ++i) if (d[i] > 0) Wp += rank[i];
    double mean = n * (n + 1) / 4.0;
    double var = n * (n + 1) * (2 * n + 1) / 24.0;
    double z = var > 0 ? (Wp - mean) / std::sqrt(var) : 0;
    return {Wp, z, normal_two_sided_p(z), n};
}

// Hodges-Lehmann estimator: median of Walsh averages (d_i + d_j)/2, i<=j.
static double hodges_lehmann(const std::vector<double>& a, const std::vector<double>& b) {
    std::vector<double> d;
    for (size_t i = 0; i < a.size(); ++i) d.push_back(a[i] - b[i]);
    std::vector<double> walsh;
    for (size_t i = 0; i < d.size(); ++i)
        for (size_t j = i; j < d.size(); ++j) walsh.push_back(0.5 * (d[i] + d[j]));
    std::sort(walsh.begin(), walsh.end());
    size_t m = walsh.size();
    return m % 2 ? walsh[m / 2] : 0.5 * (walsh[m / 2 - 1] + walsh[m / 2]);
}

// McNemar test on paired binary outcomes (here: zonal-correct A vs B).
struct McNemar { int b, c; double chi2, p; };
static McNemar mcnemar(const std::vector<int>& okA, const std::vector<int>& okB) {
    int b = 0, c = 0;
    for (size_t i = 0; i < okA.size(); ++i) {
        if (okA[i] && !okB[i]) ++b;         // A right, B wrong
        if (!okA[i] && okB[i]) ++c;         // A wrong, B right
    }
    double chi2 = (b + c) ? (std::fabs(b - c) - 1.0) * (std::fabs(b - c) - 1.0) / (b + c) : 0;
    return {b, c, chi2, chi2_1_p(chi2)};
}

// Cliff's delta effect size between two error samples (dominance).
static double cliffs_delta(const std::vector<double>& a, const std::vector<double>& b) {
    long gt = 0, lt = 0;
    for (double x : a) for (double y : b) { if (x > y) ++gt; else if (x < y) ++lt; }
    double n = (double)a.size() * b.size();
    return n > 0 ? (double)(gt - lt) / n : 0;   // >0 means a tends to be LARGER
}

// Holm-Bonferroni step-down multiplicity control.
static std::vector<int> holm_bonferroni(std::vector<double> p, double alpha) {
    int m = (int)p.size();
    std::vector<int> order(m); std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(), [&](int i, int j) { return p[i] < p[j]; });
    std::vector<int> reject(m, 0);
    for (int r = 0; r < m; ++r) {
        double thr = alpha / (m - r);
        if (p[order[r]] <= thr) reject[order[r]] = 1;
        else break;                              // step-down: stop at first non-reject
    }
    return reject;
}

// Friedman statistic + Nemenyi critical difference over K methods, N blocks.
// errs[method][case]; lower error = better = rank 1.
struct Friedman { double stat; double p; std::vector<double> avg_rank; double cd; };
static Friedman friedman_nemenyi(const std::vector<std::vector<double>>& errs, double q_alpha) {
    int K = (int)errs.size(), N = (int)errs[0].size();
    std::vector<double> Rsum(K, 0.0);
    for (int c = 0; c < N; ++c) {
        std::vector<std::pair<double, int>> col(K);
        for (int k = 0; k < K; ++k) col[k] = {errs[k][c], k};
        std::sort(col.begin(), col.end());
        std::vector<double> rank(K);
        for (int i = 0; i < K;) {
            int j = i; while (j < K && col[j].first == col[i].first) ++j;
            double r = (i + j + 1) / 2.0;
            for (int t = i; t < j; ++t) rank[col[t].second] = r;
            i = j;
        }
        for (int k = 0; k < K; ++k) Rsum[k] += rank[k];
    }
    std::vector<double> avg(K); for (int k = 0; k < K; ++k) avg[k] = Rsum[k] / N;
    double s = 0; for (int k = 0; k < K; ++k) s += Rsum[k] * Rsum[k];
    double chi2 = 12.0 / (N * K * (K + 1)) * s - 3.0 * N * (K + 1);
    double cd = q_alpha * std::sqrt((double)K * (K + 1) / (6.0 * N));
    // Friedman chi2 has df = K-1; report survival only for the common K-1 cases.
    double p = chi2_1_p(chi2);   // conservative proxy (df=1); statistic is primary
    return {chi2, p, avg, cd};
}

}  // namespace bs

// ---------------------------------------------------------------------------
// Demonstration: build the radiomap, survey RPs, localize test points with all
// four methods, then run the full statistical comparison plan.
// ---------------------------------------------------------------------------
int main() {
    using namespace bs;
    Rng rng(20260730ULL);

    std::cout << "Reference implementation of Section 4.3 -- Baselines & Statistical Comparison.\n"
              << "Synthetic radiomap (illustration; NOT dissertation results).\n";

    Radiomap map;
    map.ap = {{2, 2}, {2, 18}, {28, 2}, {28, 18}, {15, 10}};   // 5 APs over 30x20 m

    // Survey reference points. The "proposed" method uses a DENSER survey grid;
    // baselines use a coarser one -- both from the same physical map (§4.3.1).
    auto survey = [&](double step) {
        std::vector<RP> db;
        for (double x = 1; x <= 29; x += step)
            for (double y = 1; y <= 19; y += step) {
                Pt p{x, y};
                db.push_back({p, map.fingerprint(p, &rng), zone_of(p)});
            }
        return db;
    };
    std::vector<RP> db_coarse = survey(3.0);
    std::vector<RP> db_dense  = survey(1.5);

    // Frozen test set, grouped into session/site blocks.
    const int n_blocks = 15, per_block = 12;
    std::vector<Pt> truth; std::vector<int> block;
    for (int b = 0; b < n_blocks; ++b)
        for (int j = 0; j < per_block; ++j) {
            truth.push_back({1 + rng.u01() * 28, 1 + rng.u01() * 18});
            block.push_back(b);
        }

    // Per-method error and zonal-correct vectors (paired on the same test points).
    const std::vector<std::string> names =
        {"trilateration", "WKNN(k=4)", "probabilistic", "proposed(robust+dense)"};
    const int K = 4;
    std::vector<std::vector<double>> err(K);
    std::vector<std::vector<int>> zok(K);

    for (size_t t = 0; t < truth.size(); ++t) {
        std::vector<double> fp = map.fingerprint(truth[t], &rng);
        Pt est[K];
        est[0] = trilaterate(map, fp);
        est[1] = wknn(db_coarse, fp, 4, false);
        est[2] = probabilistic(db_coarse, fp, map.sigma);
        est[3] = wknn(db_dense, fp, 5, true);
        for (int k = 0; k < K; ++k) {
            err[k].push_back(dist(est[k], truth[t]));
            zok[k].push_back(zone_of(est[k]) == zone_of(truth[t]) ? 1 : 0);
        }
    }

    // Per-method MAE.
    std::cout << std::fixed << std::setprecision(3);
    std::cout << "\nPer-method MAE (paired test points):\n";
    for (int k = 0; k < K; ++k) {
        int zc = std::accumulate(zok[k].begin(), zok[k].end(), 0);
        std::cout << "   " << std::setw(24) << std::left << names[k] << std::right
                  << "  MAE=" << mae(err[k]) << " m   zonal_acc="
                  << (double)zc / zok[k].size() << "\n";
    }

    // Pairwise comparison of "proposed" (index 3) vs each baseline (§4.3.8).
    std::cout << "\nPaired comparison: proposed vs each baseline (§4.3.8)\n";
    std::cout << "----------------------------------------------------------------\n";
    std::vector<double> pvals; std::vector<int> pidx;
    for (int k = 0; k < 3; ++k) {
        double lo, hi;
        block_bootstrap_diff_ci(err[k], err[3], block, 3000, rng, lo, hi);
        Wilcox w = wilcoxon_signed_rank(err[k], err[3]);
        double hl = hodges_lehmann(err[k], err[3]);
        McNemar mc = mcnemar(zok[3], zok[k]);
        double cd = cliffs_delta(err[k], err[3]);
        std::cout << names[k] << "  vs  proposed:\n";
        std::cout << "   MAE diff (base-prop) 95% CI [block boot]: [" << lo << ", " << hi
                  << "] m  (positive => proposed better)\n";
        std::cout << "   Wilcoxon signed-rank: z=" << w.z << "  p=" << std::scientific << w.p
                  << std::fixed << "  Hodges-Lehmann median diff=" << hl << " m\n";
        std::cout << "   McNemar (zonal): b=" << mc.b << " c=" << mc.c
                  << "  chi2=" << mc.chi2 << "  p=" << std::scientific << mc.p << std::fixed << "\n";
        std::cout << "   Cliff's delta (base vs prop): " << cd
                  << "  (" << (std::fabs(cd) < 0.147 ? "negligible" :
                              std::fabs(cd) < 0.33 ? "small" :
                              std::fabs(cd) < 0.474 ? "medium" : "large") << ")\n";
        pvals.push_back(w.p); pidx.push_back(k);
    }

    // Holm-Bonferroni across the family of Wilcoxon p-values.
    std::vector<int> rej = holm_bonferroni(pvals, 0.05);
    std::cout << "\nHolm-Bonferroni (alpha=0.05) across the " << pvals.size()
              << " Wilcoxon comparisons:\n";
    for (size_t i = 0; i < pvals.size(); ++i)
        std::cout << "   " << std::setw(24) << std::left << names[pidx[i]] << std::right
                  << "  p=" << std::scientific << pvals[i] << std::fixed
                  << "  -> " << (rej[i] ? "REJECT H0 (significant)" : "retain H0") << "\n";

    // Friedman + Nemenyi over all four methods.
    double q05_k4 = 2.569;   // Nemenyi q_0.05 for K=4 (studentized range / sqrt2)
    Friedman fr = friedman_nemenyi(err, q05_k4);
    std::cout << "\nFriedman test over all " << K << " methods (N=" << truth.size()
              << " cases):\n   statistic=" << fr.stat
              << "   Nemenyi CD(alpha=0.05)=" << fr.cd << "\n";
    std::cout << "   average ranks (lower = better):\n";
    for (int k = 0; k < K; ++k)
        std::cout << "      " << std::setw(24) << std::left << names[k] << std::right
                  << "  avg_rank=" << fr.avg_rank[k] << "\n";
    std::cout << "   pairwise rank gaps vs proposed exceeding CD => significant:\n";
    for (int k = 0; k < 3; ++k) {
        double gap = fr.avg_rank[k] - fr.avg_rank[3];
        std::cout << "      " << std::setw(24) << std::left << names[k] << std::right
                  << "  gap=" << gap << (gap > fr.cd ? "  > CD (significant)" : "  <= CD") << "\n";
    }

    std::cout << "\nReading (§4.3.8): a lower MAE alone is not a claim -- it is reported with a\n"
                 "block-bootstrap CI, a paired nonparametric test, an effect size, and a\n"
                 "multiplicity-adjusted decision. Bootstrap resamples BLOCKS, not frames,\n"
                 "because frames within a session are not independent repetitions.\n";
    return 0;
}
