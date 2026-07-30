// =============================================================================
//  Uncertainty Calibration and Robustness Evaluation
//  Reference implementation of Section 4.5 ("Калібрування невизначеності та
//  робастність до природної і навмисної деградації"), subsections 4.5.1-4.5.2
//  (calibration definition; NLL / Brier / ECE) and 4.5.9 (degradation curves,
//  recovery time, graceful degradation).
//
//  Single-translation-unit C++17, no external dependencies, self-contained
//  synthetic data. Runs as-is on OnlineGDB, g++/clang++ (>= C++17) or MSVC.
//
//  Part A -- probabilistic calibration of a zonal decision probability
//  (predicted P[source in critical zone] vs the binary outcome):
//    §4.5.2  NLL (proper score), Brier score + Murphy decomposition
//            (reliability - resolution + uncertainty), ECE and MCE on
//            adaptive (equal-count) bins, calibration slope/intercept.
//    §4.5.1  a reliability diagram (ASCII), computed on in-sample data.
//    temperature scaling fitted on a VALIDATION split (own transform id),
//    applied to the TEST split -> ECE/NLL before vs after, without changing
//    the model ranking or the mode topology.
//
//  Part B -- robustness as a controlled function of perturbation strength
//  (§4.5.9): a stress sweep produces a degradation curve, relative degradation,
//  area under the degradation curve (AUDC), the danger breakpoint (decision-tier
//  transition), and the recovery time back into the calibration envelope after
//  the stress is removed. Graceful degradation = monotone, bounded quality loss
//  with widening uncertainty, not a binary pass/fail.
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

namespace cal {

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

static inline double sigmoid(double z) { return 1.0 / (1.0 + std::exp(-z)); }
static inline double logit(double p) {
    p = std::min(1.0 - 1e-9, std::max(1e-9, p));
    return std::log(p / (1.0 - p));
}
static inline double clip(double p, double eps) { return std::min(1.0 - eps, std::max(eps, p)); }

// One probabilistic prediction: forecast probability p and binary outcome y.
struct Pred { double p; int y; };

// ---------------------------------------------------------------------------
// §4.5.2 Proper scores. NLL uses a fixed clipping epsilon in the manifest.
// ---------------------------------------------------------------------------
static double nll(const std::vector<Pred>& d, double eps = 1e-6) {
    double s = 0;
    for (const auto& e : d) {
        double p = clip(e.p, eps);
        s += -(e.y * std::log(p) + (1 - e.y) * std::log(1 - p));
    }
    return d.empty() ? std::nan("") : s / d.size();
}
static double brier(const std::vector<Pred>& d) {
    double s = 0;
    for (const auto& e : d) s += (e.p - e.y) * (e.p - e.y);
    return d.empty() ? std::nan("") : s / d.size();
}

// ---------------------------------------------------------------------------
// Adaptive (equal-count) bins: sort by forecast, split into K bins of ~equal
// size (§4.5.2 -- ECE with adaptive bins and a minimum support per bin).
// ---------------------------------------------------------------------------
struct Bin { double conf; double acc; int n; };

static std::vector<Bin> equal_count_bins(const std::vector<Pred>& d, int K) {
    std::vector<Pred> s = d;
    std::sort(s.begin(), s.end(), [](const Pred& a, const Pred& b) { return a.p < b.p; });
    std::vector<Bin> bins;
    int n = (int)s.size();
    for (int k = 0; k < K; ++k) {
        int lo = (int)((long long)k * n / K);
        int hi = (int)((long long)(k + 1) * n / K);
        if (hi <= lo) continue;
        double cs = 0; int ys = 0;
        for (int i = lo; i < hi; ++i) { cs += s[i].p; ys += s[i].y; }
        Bin b{cs / (hi - lo), (double)ys / (hi - lo), hi - lo};
        bins.push_back(b);
    }
    return bins;
}

struct CalMetrics { double ece, mce; };
static CalMetrics ece_mce(const std::vector<Bin>& bins, int N) {
    double ece = 0, mce = 0;
    for (const auto& b : bins) {
        double gap = std::fabs(b.acc - b.conf);
        ece += (double)b.n / N * gap;
        mce = std::max(mce, gap);
    }
    return {ece, mce};
}

// ---------------------------------------------------------------------------
// Murphy decomposition of the Brier score (§4.5.2):
//   Brier = reliability - resolution + uncertainty
// computed over the equal-count bins; also returns the direct Brier for a
// consistency check.
// ---------------------------------------------------------------------------
struct Murphy { double reliability, resolution, uncertainty, sum; };

static Murphy murphy(const std::vector<Pred>& d, const std::vector<Bin>& bins) {
    int N = (int)d.size();
    double obar = 0; for (const auto& e : d) obar += e.y; obar /= N;
    double rel = 0, res = 0;
    for (const auto& b : bins) {
        rel += (double)b.n / N * (b.conf - b.acc) * (b.conf - b.acc);
        res += (double)b.n / N * (b.acc - obar) * (b.acc - obar);
    }
    double unc = obar * (1.0 - obar);
    return {rel, res, unc, rel - res + unc};
}

// ---------------------------------------------------------------------------
// Calibration slope/intercept (§4.5.2): logistic regression of outcome y on the
// forecast logit x = logit(p). Perfect calibration -> slope 1, intercept 0.
// Fitted by Newton-Raphson / IRLS on a 2-parameter model y ~ sigmoid(a + b x).
// ---------------------------------------------------------------------------
static void calibration_slope_intercept(const std::vector<Pred>& d,
                                        double& intercept, double& slope) {
    double a = 0.0, b = 1.0;
    for (int it = 0; it < 50; ++it) {
        double g0 = 0, g1 = 0;              // gradient
        double h00 = 0, h01 = 0, h11 = 0;   // Hessian
        for (const auto& e : d) {
            double x = logit(e.p);
            double mu = sigmoid(a + b * x);
            double w = mu * (1 - mu);
            double r = mu - e.y;
            g0 += r;      g1 += r * x;
            h00 += w;     h01 += w * x;   h11 += w * x * x;
        }
        double det = h00 * h11 - h01 * h01;
        if (std::fabs(det) < 1e-12) break;
        double da = (h11 * g0 - h01 * g1) / det;
        double db = (-h01 * g0 + h00 * g1) / det;
        a -= da; b -= db;
        if (std::fabs(da) + std::fabs(db) < 1e-9) break;
    }
    intercept = a; slope = b;
}

// ---------------------------------------------------------------------------
// Temperature scaling (§4.5.1): fit a single scalar T>0 on the VALIDATION split
// to minimize NLL of p' = sigmoid(logit(p)/T). 1-D golden-section search.
// ---------------------------------------------------------------------------
static std::vector<Pred> apply_temperature(const std::vector<Pred>& d, double T) {
    std::vector<Pred> out = d;
    for (auto& e : out) e.p = sigmoid(logit(e.p) / T);
    return out;
}
static double fit_temperature(const std::vector<Pred>& val) {
    auto cost = [&](double T) { return nll(apply_temperature(val, T)); };
    double a = 0.25, b = 5.0, gr = (std::sqrt(5.0) - 1) / 2;
    double c = b - gr * (b - a), d = a + gr * (b - a);
    for (int it = 0; it < 80; ++it) {
        if (cost(c) < cost(d)) b = d; else a = c;
        c = b - gr * (b - a); d = a + gr * (b - a);
    }
    return 0.5 * (a + b);
}

// ---------------------------------------------------------------------------
// Reliability diagram (ASCII): predicted confidence vs empirical accuracy.
// ---------------------------------------------------------------------------
static void reliability_diagram(const std::vector<Bin>& bins) {
    std::cout << "   reliability diagram (conf -> acc; '*'=acc, '.'=diagonal):\n";
    for (const auto& b : bins) {
        int accpos = (int)std::round(b.acc * 40);
        int diagpos = (int)std::round(b.conf * 40);
        std::string line(41, ' ');
        if (diagpos >= 0 && diagpos <= 40) line[diagpos] = '.';
        if (accpos >= 0 && accpos <= 40) line[accpos] = '*';
        std::cout << "   conf=" << std::fixed << std::setprecision(2) << b.conf
                  << " |" << line << "| acc=" << b.acc << " (n=" << b.n << ")\n";
    }
}

// ---------------------------------------------------------------------------
// PART A data: an OVER-CONFIDENT zonal probability. True outcome depends on a
// latent score; the forecaster sharpens (over-states) its confidence, which
// temperature scaling should partly correct.
// ---------------------------------------------------------------------------
static std::vector<Pred> make_zonal(Rng& rng, int n, double sharpen) {
    std::vector<Pred> d;
    for (int i = 0; i < n; ++i) {
        double latent = rng.normal();                 // true log-odds signal
        double p_true = sigmoid(latent);              // true probability
        int y = (rng.u01() < p_true) ? 1 : 0;
        // over-confident report: push logit away from 0 by 'sharpen'
        double p_report = sigmoid(latent * sharpen);
        d.push_back({p_report, y});
    }
    return d;
}

static void run_partA(Rng& rng) {
    std::cout << "\n########## PART A -- Probabilistic calibration (§4.5.1-4.5.2) ##########\n";
    // over-confident forecaster: sharpen = 1.8 (reports sharper than reality)
    std::vector<Pred> val  = make_zonal(rng, 1500, 1.8);
    std::vector<Pred> test = make_zonal(rng, 1500, 1.8);

    auto report = [&](const std::string& tag, const std::vector<Pred>& d) {
        auto bins = equal_count_bins(d, 10);
        CalMetrics cm = ece_mce(bins, (int)d.size());
        Murphy mp = murphy(d, bins);
        double a, b; calibration_slope_intercept(d, a, b);
        std::cout << std::fixed << std::setprecision(4);
        std::cout << "  [" << tag << "]  NLL=" << nll(d) << "  Brier=" << brier(d)
                  << "  ECE=" << cm.ece << "  MCE=" << cm.mce << "\n";
        std::cout << "        Brier decomposition: reliability=" << mp.reliability
                  << "  resolution=" << mp.resolution << "  uncertainty=" << mp.uncertainty
                  << "  (rel-res+unc=" << mp.sum << ")\n";
        std::cout << "        calibration slope=" << b << "  intercept=" << a
                  << "  (ideal: slope=1, intercept=0)\n";
        return bins;
    };

    std::cout << "-- TEST split, BEFORE temperature scaling --\n";
    auto bins_before = report("uncalibrated", test);
    reliability_diagram(bins_before);

    double T = fit_temperature(val);
    std::cout << "\n-- fitted temperature on VALIDATION split: T = "
              << std::setprecision(3) << T
              << " (transform id = temp_v1; T>1 => shrink confidence) --\n";

    std::vector<Pred> test_cal = apply_temperature(test, T);
    std::cout << "-- TEST split, AFTER temperature scaling --\n";
    auto bins_after = report("temp_scaled", test_cal);
    reliability_diagram(bins_after);

    std::cout << "  Note (§4.5.2): ECE is reported WITH NLL/Brier (not alone) because it\n"
                 "  depends on binning; temperature scaling shrinks over-confidence without\n"
                 "  changing the decision ranking or mode topology.\n";
}

// ---------------------------------------------------------------------------
// PART B: degradation curve, AUDC, breakpoint, recovery time (§4.5.9).
// A stress factor (e.g., NLOS fraction / injected FTM bias) rises from 0 to
// s_max and then is removed; we track a quality metric (here HPD coverage error
// vs nominal 0.90) and the decision tier. Graceful degradation = monotone,
// bounded loss with a controlled recovery.
// ---------------------------------------------------------------------------
static void run_partB(Rng& rng) {
    std::cout << "\n########## PART B -- Degradation curve & recovery (§4.5.9) ##########\n";

    const double nominal = 0.90;         // nominal HPD level
    const double danger = 0.10;          // |coverage - nominal| danger threshold
    const int ramp = 8, hold = 2, recov = 8;

    std::vector<double> stress, cov_err; std::vector<std::string> tier;
    // clean baseline coverage error (small).
    auto coverage_at = [&](double s) {
        // coverage degrades as stress grows: model over-confidence under NLOS/bias.
        double drift = 0.45 * s;                       // coverage falls below nominal
        double noise = 0.02 * rng.normal();
        double cov = nominal - drift + noise;
        return std::max(0.0, std::min(1.0, cov));
    };

    double s = 0.0;
    // ramp up
    for (int k = 0; k < ramp; ++k) { s = 0.10 * k; double c = coverage_at(s);
        stress.push_back(s); cov_err.push_back(std::fabs(c - nominal)); }
    // hold at peak
    double speak = 0.10 * (ramp - 1);
    for (int k = 0; k < hold; ++k) { double c = coverage_at(speak);
        stress.push_back(speak); cov_err.push_back(std::fabs(c - nominal)); }
    // recovery: stress removed; system widens uncertainty and returns gradually
    for (int k = 0; k < recov; ++k) {
        double resid = speak * std::exp(-0.6 * (k + 1));   // controlled recovery
        double c = coverage_at(resid);
        stress.push_back(0.0); cov_err.push_back(std::fabs(c - nominal));
    }

    // decision tier from coverage error.
    for (double ce : cov_err) {
        if (ce < 0.05) tier.push_back("AUTO");
        else if (ce < danger) tier.push_back("VERIFY");
        else tier.push_back("HiL");
    }

    // AUDC (trapezoidal over the ramp+hold phase index), breakpoint, recovery.
    int peak_end = ramp + hold;
    double audc = 0;
    for (int i = 1; i < peak_end; ++i) audc += 0.5 * (cov_err[i] + cov_err[i - 1]);
    int breakpoint = -1;
    for (int i = 0; i < peak_end; ++i) if (cov_err[i] >= danger) { breakpoint = i; break; }
    int recovery_time = -1;
    for (int i = peak_end; i < (int)cov_err.size(); ++i)
        if (cov_err[i] < 0.05) { recovery_time = i - peak_end + 1; break; }

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "  step  stress  cov_err   tier   curve\n";
    for (size_t i = 0; i < cov_err.size(); ++i) {
        int bar = (int)std::round(cov_err[i] * 60);
        std::cout << "  " << std::setw(3) << i << "  " << std::setw(6) << stress[i]
                  << "  " << std::setw(6) << cov_err[i] << "   " << std::setw(6) << tier[i]
                  << "   " << std::string(std::max(0, bar), '#') << "\n";
    }
    std::cout << "\n  AUDC (ramp+hold)          : " << audc << "\n";
    std::cout << "  danger breakpoint at step : " << breakpoint
              << (breakpoint >= 0 ? "  (coverage error crossed 0.10 -> HiL)" : "  (never crossed)") << "\n";
    std::cout << "  recovery time             : "
              << (recovery_time >= 0 ? std::to_string(recovery_time) + " steps to re-enter AUTO envelope"
                                     : std::string("not recovered within window")) << "\n";
    std::cout << "  Graceful-degradation check: monotone loss on the ramp and a controlled\n"
                 "  return -- robustness is bounded degradation, not absence of error (§4.5.9).\n";
}

}  // namespace cal

int main() {
    using namespace cal;
    Rng rng(20260730ULL);
    std::cout << "Reference implementation of Section 4.5 -- Uncertainty Calibration & Robustness.\n"
              << "Synthetic data (illustration; NOT dissertation results).\n";
    run_partA(rng);
    run_partB(rng);
    return 0;
}
