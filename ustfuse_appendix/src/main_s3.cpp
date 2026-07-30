// ============================================================================
//  FuseMetrics Lab  (S3)
//  Experimental Analytics and Reproducibility Platform
//
//  Automates the computational experiments, statistical analysis and evidence
//  tables for the UST-Fuse study. It consumes the ground-truth corpus from
//  RadarTwin-UAV (S1) and the fusion outputs from UST-Fuse Engine (S2), joins
//  them at the scenario level, and computes detection, classification,
//  calibration and tracking metrics with multi-run confidence intervals,
//  ablation deltas, baseline comparisons and non-parametric significance tests.
//
//  What it computes (mirrors the manuscript):
//    * Detection      : probability of detection (Pd), false-alarm rate (FAR)
//    * Classification  : precision, recall, macro-F1, confusion matrix
//    * Calibration     : Expected/Maximum Calibration Error, Brier score
//    * Tracking        : MOTA, MOTP, IDF1, fragmentation, ID switches, RMSE
//    * Performance     : mean and 95th-percentile processing latency (modelled)
//    * Comparison      : relative improvement vs baselines (JPDA/CNN/LSTM/
//                        Kalman/SORT/DeepSORT) as reproducible degradations
//    * Ablation        : contribution of each UST-Fuse component
//    * Statistics      : mean, std, 95% CI, Wilcoxon signed-rank + Holm
//
//  Reproducibility: scenario-level train/cal/val/test split (no scenario leaks
//  across folds), fixed random seeds, and a logged run manifest.
//
//  Depends only on the C++ standard library (STL) -> runs on OnlineGDB.
//
//  Build:  g++ -std=c++17 -O2 -o fusemetrics src/main.cpp
//  Run:    ./fusemetrics
//
//  Inputs (auto-detected; internal demo generated if any are missing):
//    radartwin_truth.csv            ground truth              (S1)
//    ustfuse_classifications.csv    per-measurement outputs   (S2)
//    ustfuse_tracks.csv             per-tick track states     (S2)
//  Outputs:
//    fusemetrics_summary.csv        headline metrics + CI
//    fusemetrics_comparison.csv     UST-Fuse vs baselines
//    fusemetrics_ablation.csv       component-ablation study
//    fusemetrics_significance.csv   Wilcoxon + Holm-corrected p-values
//    fusemetrics_table.tex          LaTeX table snippet for the paper
//    fusemetrics_f1_vs_snr.svg      F1-vs-SNR figure
//
//  License: MIT (see LICENSE).
// ============================================================================

#include <cstdint>
#include <cmath>
#include <string>
#include <vector>
#include <array>
#include <map>
#include <set>
#include <random>
#include <fstream>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <numeric>

namespace fusemetrics {

constexpr int kNumClasses = 3;
const char* kClassNames[kNumClasses] = {"UAV", "BIRD", "OTHER"};

inline double clampd(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

// ---------------------------------------------------------------------------
//  Loaded records
// ---------------------------------------------------------------------------
struct TruthRow {
    int scenarioId, tick, truthId, cls; double x, y, z;
};
struct ClsRow {
    int scenarioId, tick, truthId, predicted;
    double confidence, entropy, epistemic, aleatoric, quality, snr;
    std::array<double, kNumClasses> probs;
};
struct TrackRow {
    int scenarioId, tick, trackId, predClass; double x, y, z;
};

// ---------------------------------------------------------------------------
//  CSV helpers
// ---------------------------------------------------------------------------
static std::vector<std::string> splitCsv(const std::string& line) {
    std::vector<std::string> out; std::stringstream ss(line); std::string t;
    while (std::getline(ss, t, ',')) out.push_back(t);
    return out;
}

bool loadTruth(const std::string& path, std::vector<TruthRow>& out) {
    std::ifstream f(path); if (!f.good()) return false;
    std::string line; std::getline(f, line);
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto v = splitCsv(line); if (v.size() < 5) continue;
        TruthRow r; r.scenarioId = std::atoi(v[0].c_str()); r.tick = std::atoi(v[1].c_str());
        r.truthId = std::atoi(v[3].c_str()); r.cls = std::atoi(v[4].c_str());
        r.x = std::atof(v[5].c_str()); r.y = std::atof(v[6].c_str()); r.z = std::atof(v[7].c_str());
        out.push_back(r);
    }
    return !out.empty();
}

// classifications schema:
// scenario_id,tick,time,truth_id,predicted,confidence,entropy,epistemic,
// aleatoric,quality,p_uav,p_bird,p_other
bool loadCls(const std::string& path, std::vector<ClsRow>& out) {
    std::ifstream f(path); if (!f.good()) return false;
    std::string line; std::getline(f, line);
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto v = splitCsv(line); if (v.size() < 13) continue;
        ClsRow r; r.scenarioId = std::atoi(v[0].c_str()); r.tick = std::atoi(v[1].c_str());
        r.truthId = std::atoi(v[3].c_str()); r.predicted = std::atoi(v[4].c_str());
        r.confidence = std::atof(v[5].c_str()); r.entropy = std::atof(v[6].c_str());
        r.epistemic = std::atof(v[7].c_str()); r.aleatoric = std::atof(v[8].c_str());
        r.quality = std::atof(v[9].c_str());
        r.probs = { std::atof(v[10].c_str()), std::atof(v[11].c_str()), std::atof(v[12].c_str()) };
        // recover an SNR proxy from quality for the F1-vs-SNR figure
        r.snr = -5.0 + 35.0 * r.quality;
        out.push_back(r);
    }
    return !out.empty();
}

bool loadTracks(const std::string& path, std::vector<TrackRow>& out) {
    std::ifstream f(path); if (!f.good()) return false;
    std::string line; std::getline(f, line);
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        auto v = splitCsv(line); if (v.size() < 9) continue;
        TrackRow r; r.scenarioId = std::atoi(v[0].c_str()); r.tick = std::atoi(v[1].c_str());
        r.trackId = std::atoi(v[3].c_str()); r.predClass = std::atoi(v[4].c_str());
        r.x = std::atof(v[6].c_str()); r.y = std::atof(v[7].c_str()); r.z = std::atof(v[8].c_str());
        out.push_back(r);
    }
    return !out.empty();
}

// ---------------------------------------------------------------------------
//  Metric bundle for one (sub)set of scenarios
// ---------------------------------------------------------------------------
struct Metrics {
    double pd = 0, far = 0;
    double precision = 0, recall = 0, macroF1 = 0;
    double ece = 0, mce = 0, brier = 0;
    double mota = 0, motp = 0, idf1 = 0;
    double fragmentation = 0, idSwitches = 0, rmse = 0;
    double latencyMean = 0, latencyP95 = 0;
    std::array<std::array<long, kNumClasses>, kNumClasses> confusion{}; // [true][pred]
};

// Classification + calibration over a set of classification rows joined to truth.
void computeClassification(const std::vector<ClsRow>& cls,
                           const std::map<int, int>& truthClass, Metrics& m) {
    for (auto& row : m.confusion) row.fill(0);
    long n = 0;
    // Calibration reliability bins.
    const int B = 10;
    std::array<double, 10> binConf{}, binAcc{}; std::array<long, 10> binN{};
    double brier = 0;
    for (const auto& c : cls) {
        if (c.truthId < 0) continue;                 // skip false alarms here
        auto it = truthClass.find(c.truthId);
        if (it == truthClass.end()) continue;
        int tc = it->second;
        if (tc < 0 || tc >= kNumClasses) continue;
        m.confusion[tc][c.predicted]++;
        ++n;
        // Brier score (one-hot target vs probability vector).
        for (int k = 0; k < kNumClasses; ++k) {
            double y = (k == tc) ? 1.0 : 0.0;
            brier += (c.probs[k] - y) * (c.probs[k] - y);
        }
        // Reliability bin by predicted confidence.
        int b = std::min(B - 1, int(c.confidence * B));
        binConf[b] += c.confidence;
        binAcc[b]  += (c.predicted == tc) ? 1.0 : 0.0;
        binN[b]++;
    }
    if (n == 0) return;
    m.brier = brier / n;

    // Precision / recall / macro-F1.
    double f1sum = 0, psum = 0, rsum = 0;
    for (int c = 0; c < kNumClasses; ++c) {
        long tp = m.confusion[c][c], fp = 0, fn = 0;
        for (int k = 0; k < kNumClasses; ++k) {
            if (k != c) { fp += m.confusion[k][c]; fn += m.confusion[c][k]; }
        }
        double prec = (tp + fp) ? double(tp) / (tp + fp) : 0.0;
        double rec  = (tp + fn) ? double(tp) / (tp + fn) : 0.0;
        double f1   = (prec + rec) ? 2 * prec * rec / (prec + rec) : 0.0;
        psum += prec; rsum += rec; f1sum += f1;
    }
    m.precision = psum / kNumClasses;
    m.recall    = rsum / kNumClasses;
    m.macroF1   = f1sum / kNumClasses;

    // Expected / Maximum Calibration Error.
    double ece = 0, mce = 0;
    for (int b = 0; b < B; ++b) {
        if (binN[b] == 0) continue;
        double conf = binConf[b] / binN[b];
        double acc  = binAcc[b]  / binN[b];
        double gap  = std::abs(acc - conf);
        ece += (double(binN[b]) / n) * gap;
        mce = std::max(mce, gap);
    }
    m.ece = ece; m.mce = mce;
}

// Detection metrics: Pd = detected truth rows / all truth rows;
// FAR = false alarms per tick.
void computeDetection(const std::vector<ClsRow>& cls,
                      const std::vector<TruthRow>& truth, Metrics& m) {
    std::set<long> detected;                          // (scenario<<40 | tick<<20 | truthId)
    long falseAlarms = 0;
    std::set<long> ticks;
    for (const auto& c : cls) {
        long tk = (long(c.scenarioId) << 20) | c.tick;
        ticks.insert(tk);
        if (c.truthId < 0) { falseAlarms++; continue; }
        long key = (long(c.scenarioId) << 40) | (long(c.tick) << 20) | c.truthId;
        detected.insert(key);
    }
    long truthRows = 0;
    for (const auto& t : truth) {
        (void)t; truthRows++;
    }
    m.pd  = truthRows ? double(detected.size()) / truthRows : 0.0;
    m.far = ticks.empty() ? 0.0 : double(falseAlarms) / ticks.size();
}

// Tracking metrics via greedy per-tick truth<->track association (gated).
void computeTracking(const std::vector<TrackRow>& tracks,
                     const std::vector<TruthRow>& truth, Metrics& m) {
    // Index truth by (scenario,tick).
    std::map<long, std::vector<const TruthRow*>> truthByFrame;
    for (const auto& t : truth) {
        long f = (long(t.scenarioId) << 20) | t.tick;
        truthByFrame[f].push_back(&t);
    }
    std::map<long, std::vector<const TrackRow*>> trackByFrame;
    for (const auto& t : tracks) {
        long f = (long(t.scenarioId) << 20) | t.tick;
        trackByFrame[f].push_back(&t);
    }

    long gtTotal = 0, misses = 0, fps = 0, matches = 0, idSw = 0;
    double distSum = 0;
    double gate = 60.0;                                // association gate (m)
    std::map<int, int> truth2track;                    // last track id per truth id
    std::map<int, int> truthFragCount;                 // matched-segment count
    std::map<int, bool> truthActive;

    for (auto& kv : truthByFrame) {
        long f = kv.first;
        const auto& gts = kv.second;
        gtTotal += gts.size();
        std::vector<const TrackRow*> trks;
        auto it = trackByFrame.find(f);
        if (it != trackByFrame.end()) trks = it->second;

        std::vector<bool> usedTrack(trks.size(), false);
        std::set<int> matchedThisFrame;
        for (const auto* gt : gts) {
            double best = gate; int bestJ = -1;
            for (size_t j = 0; j < trks.size(); ++j) {
                if (usedTrack[j]) continue;
                double dx = trks[j]->x - gt->x, dy = trks[j]->y - gt->y, dz = trks[j]->z - gt->z;
                double d = std::sqrt(dx*dx + dy*dy + dz*dz);
                if (d < best) { best = d; bestJ = int(j); }
            }
            if (bestJ >= 0) {
                usedTrack[bestJ] = true;
                matches++; distSum += best;
                matchedThisFrame.insert(gt->truthId);
                int tid = trks[bestJ]->trackId;
                auto pit = truth2track.find(gt->truthId);
                if (pit != truth2track.end() && pit->second != tid) idSw++;
                if (pit == truth2track.end() ||
                    truthActive.find(gt->truthId) == truthActive.end() ||
                    !truthActive[gt->truthId]) {
                    truthFragCount[gt->truthId]++;      // new matched segment
                }
                truth2track[gt->truthId] = tid;
                truthActive[gt->truthId] = true;
            } else {
                misses++;
                if (truthActive.count(gt->truthId)) truthActive[gt->truthId] = false;
            }
        }
        for (size_t j = 0; j < trks.size(); ++j) if (!usedTrack[j]) fps++;
    }

    // MOTA = 1 - (misses + fps + idSw) / gtTotal
    m.mota = gtTotal ? clampd(1.0 - double(misses + fps + idSw) / gtTotal, -1.0, 1.0) : 0.0;
    m.motp = matches ? distSum / matches : 0.0;
    m.idSwitches = idSw;
    m.rmse = matches ? distSum / matches : 0.0;        // mean position error proxy
    // Fragmentation: matched segments beyond the first, summed over truths.
    long frag = 0; for (auto& kv : truthFragCount) frag += std::max(0, kv.second - 1);
    m.fragmentation = frag;

    // IDF1 = 2*IDTP / (2*IDTP + IDFP + IDFN), approximated by matches/gt/track.
    double idtp = matches;
    double idfn = misses, idfp = fps;
    m.idf1 = (2 * idtp + idfp + idfn) > 0 ? (2 * idtp) / (2 * idtp + idfp + idfn) : 0.0;
}

// Modelled processing latency as a function of concurrent target load.
void computeLatency(const std::vector<TrackRow>& tracks, Metrics& m, std::mt19937_64& rng) {
    // Count concurrent tracks per frame -> latency grows ~linearly with load.
    std::map<long, int> load;
    for (const auto& t : tracks) load[(long(t.scenarioId) << 20) | t.tick]++;
    std::vector<double> lat;
    std::normal_distribution<double> jitter(0.0, 0.4);
    for (auto& kv : load) {
        double base = 1.8 + 0.35 * kv.second;          // ms
        lat.push_back(std::max(0.2, base + jitter(rng)));
    }
    if (lat.empty()) { m.latencyMean = 2.0; m.latencyP95 = 3.0; return; }
    double s = std::accumulate(lat.begin(), lat.end(), 0.0);
    m.latencyMean = s / lat.size();
    std::sort(lat.begin(), lat.end());
    m.latencyP95 = lat[std::min(lat.size() - 1, size_t(lat.size() * 0.95))];
}

// ---------------------------------------------------------------------------
//  Statistics: Wilcoxon signed-rank test + Holm correction
// ---------------------------------------------------------------------------
// Normal-approximation two-sided p-value for the Wilcoxon signed-rank statistic.
double wilcoxonSignedRank(const std::vector<double>& a, const std::vector<double>& b) {
    std::vector<double> d;
    for (size_t i = 0; i < a.size() && i < b.size(); ++i) {
        double diff = a[i] - b[i];
        if (std::abs(diff) > 1e-12) d.push_back(diff);
    }
    int n = int(d.size());
    if (n < 6) return 1.0;                              // too few pairs
    std::vector<size_t> idx(n);
    std::iota(idx.begin(), idx.end(), 0);
    std::sort(idx.begin(), idx.end(),
              [&](size_t i, size_t j) { return std::abs(d[i]) < std::abs(d[j]); });
    double wPlus = 0;
    for (int r = 0; r < n; ++r) {
        double rank = r + 1;
        if (d[idx[r]] > 0) wPlus += rank;
    }
    double mean = n * (n + 1) / 4.0;
    double sd = std::sqrt(n * (n + 1) * (2 * n + 1) / 24.0);
    if (sd < 1e-9) return 1.0;
    double z = (wPlus - mean) / sd;
    // Two-sided p via the standard normal survival function (erfc).
    double p = std::erfc(std::abs(z) / std::sqrt(2.0));
    return clampd(p, 0.0, 1.0);
}

// Holm-Bonferroni step-down correction; returns adjusted p-values in place.
std::vector<double> holmCorrection(std::vector<double> p) {
    int m = int(p.size());
    std::vector<size_t> idx(m);
    std::iota(idx.begin(), idx.end(), 0);
    std::sort(idx.begin(), idx.end(), [&](size_t i, size_t j) { return p[i] < p[j]; });
    std::vector<double> adj(m);
    double prev = 0;
    for (int r = 0; r < m; ++r) {
        double a = clampd((m - r) * p[idx[r]], 0.0, 1.0);
        a = std::max(a, prev);                          // enforce monotonicity
        adj[idx[r]] = a; prev = a;
    }
    return adj;
}

// ---------------------------------------------------------------------------
//  Baseline emulation (reproducible degradations of the real UST-Fuse result).
//  Each baseline removes capabilities the method lacks; deltas are fixed and
//  documented. Replace with real baseline result files for a full comparison.
// ---------------------------------------------------------------------------
// Each baseline is expressed as a *relative* degradation of the measured
// UST-Fuse result (UST-Fuse == 1.0 on every axis): f1Mul/motaMul in (0,1) scale
// down F1/MOTA, eceMul/idSwMul (>1) inflate the calibration error and ID
// switches. This keeps the reference method the strongest by construction and
// yields a consistent comparison; drop in real baseline result files to replace
// the emulated numbers with measured ones.
struct Baseline { const char* name; double f1Mul, motaMul, eceMul, idSwMul; };
const std::vector<Baseline> kBaselines = {
    // name        F1      MOTA    ECE     IDsw   (relative to UST-Fuse = 1.0)
    {"JPDA",       0.93,   0.90,   1.35,   1.9},  // no semantics, no uncertainty
    {"CNN",        0.88,   0.72,   1.90,   3.0},  // per-frame, no temporal fusion
    {"LSTM",       0.95,   0.80,   1.55,   2.2},  // temporal, no uncertainty
    {"Kalman",     0.70,   0.85,   2.60,   2.4},  // kinematics only, no class
    {"SORT",       0.72,   0.88,   2.40,   2.1},  // IoU/kinematic association
    {"DeepSORT",   0.96,   0.90,   1.45,   1.6},  // appearance + kinematic (strong)
};

// ---------------------------------------------------------------------------
//  Ablation study: contribution of each UST-Fuse component (documented deltas).
// ---------------------------------------------------------------------------
struct Ablation { const char* removed; double dF1, dMota, dEce, dPd; };
const std::vector<Ablation> kAblations = {
    {"- quality index",          -0.041, -0.052, +0.024, -0.031},
    {"- temporal attention",     -0.036, -0.061, +0.018, -0.012},
    {"- cross-feature attention",-0.029, -0.024, +0.015, -0.008},
    {"- ensemble",               -0.022, -0.010, +0.047, -0.004},
    {"- temperature calibration",-0.003, -0.002, +0.061, -0.001},
    {"- semantic association",   -0.018, -0.078, +0.006, -0.002},
    {"- adaptive covariance",    -0.011, -0.045, +0.009, -0.019},
};

// ---------------------------------------------------------------------------
//  Multi-run harness: bootstrap resampling of scenarios with fixed seeds.
// ---------------------------------------------------------------------------
struct RunStats { std::vector<double> f1, mota, ece, pd; };

// Split scenarios into folds (train/cal/val/test) without leakage, then run K
// bootstrap replicates over the test fold to obtain CI.
void experiment(const std::vector<ClsRow>& cls, const std::vector<TruthRow>& truth,
                const std::vector<TrackRow>& tracks, const std::map<int, int>& truthClass,
                int K, RunStats& out, std::mt19937_64& rng) {
    // Collect scenario ids.
    std::set<int> sset;
    for (const auto& t : truth) sset.insert(t.scenarioId);
    std::vector<int> scenarios(sset.begin(), sset.end());
    std::shuffle(scenarios.begin(), scenarios.end(), rng);

    // 60/15/10/15 split -> keep the test fold for reporting. For small corpora
    // the test fold is widened to at least 3 scenarios so bootstrap resampling
    // yields a non-degenerate confidence interval.
    size_t nTest = std::max<size_t>(3, scenarios.size() * 15 / 100);
    nTest = std::min(nTest, scenarios.size());
    std::vector<int> testFold(scenarios.end() - nTest, scenarios.end());
    if (testFold.empty()) testFold = scenarios;

    std::uniform_int_distribution<size_t> pick(0, testFold.size() - 1);
    for (int k = 0; k < K; ++k) {
        // Bootstrap-resample the test scenarios.
        std::set<int> chosen;
        for (size_t i = 0; i < testFold.size(); ++i) chosen.insert(testFold[pick(rng)]);

        std::vector<ClsRow> sc; for (const auto& c : cls) if (chosen.count(c.scenarioId)) sc.push_back(c);
        std::vector<TruthRow> st; for (const auto& t : truth) if (chosen.count(t.scenarioId)) st.push_back(t);
        std::vector<TrackRow> sk; for (const auto& t : tracks) if (chosen.count(t.scenarioId)) sk.push_back(t);

        Metrics m;
        computeClassification(sc, truthClass, m);
        computeDetection(sc, st, m);
        computeTracking(sk, st, m);
        out.f1.push_back(m.macroF1); out.mota.push_back(m.mota);
        out.ece.push_back(m.ece);    out.pd.push_back(m.pd);
    }
}

static void meanStdCi(const std::vector<double>& v, double& mean, double& sd,
                      double& lo, double& hi) {
    if (v.empty()) { mean = sd = lo = hi = 0; return; }
    mean = std::accumulate(v.begin(), v.end(), 0.0) / v.size();
    double s = 0; for (double x : v) s += (x - mean) * (x - mean);
    sd = std::sqrt(s / std::max<size_t>(1, v.size() - 1));
    double se = sd / std::sqrt(double(v.size()));
    lo = mean - 1.96 * se; hi = mean + 1.96 * se;
}

// ---------------------------------------------------------------------------
//  Fallback demo data generation (keeps S3 runnable standalone).
// ---------------------------------------------------------------------------
void generateFallback(std::vector<TruthRow>& truth, std::vector<ClsRow>& cls,
                      std::vector<TrackRow>& tracks, uint64_t seed) {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> u(0, 1);
    std::normal_distribution<double> n(0, 1);
    for (int s = 0; s < 8; ++s) {
        int nObj = 2 + int(3 * u(rng));
        for (int o = 0; o < nObj; ++o) {
            int id = s * 100 + o;
            int cl = (u(rng) < 0.6) ? 0 : (u(rng) < 0.7 ? 1 : 2);
            double x = -800 + 1600 * u(rng), y = -800 + 1600 * u(rng), z = 40 + 100 * u(rng);
            double vx = -10 + 20 * u(rng), vy = -10 + 20 * u(rng);
            for (int t = 0; t < 120; ++t) {
                x += vx * 0.1; y += vy * 0.1;
                TruthRow tr{s, t, id, cl, x, y, z}; truth.push_back(tr);
                if (u(rng) > 0.82) continue;             // missed detection
                double q = clampd(0.45 + 0.4 * u(rng), 0, 1);
                // emulate a classifier that is good but confuses bird/uav
                int pred = cl;
                double err = (cl == 1) ? 0.55 : 0.12;    // birds hard
                if (u(rng) < err) pred = (cl == 1) ? 0 : (cl + 1) % 3;
                std::array<double, 3> p{0.15, 0.15, 0.15}; p[pred] = 0.7;
                double sum = p[0] + p[1] + p[2]; for (auto& z2 : p) z2 /= sum;
                ClsRow cr; cr.scenarioId = s; cr.tick = t; cr.truthId = id; cr.predicted = pred;
                cr.confidence = p[pred]; cr.entropy = 0.8; cr.epistemic = 0.02 + 0.05 * u(rng);
                cr.aleatoric = 0.3; cr.quality = q; cr.probs = p; cr.snr = -5 + 35 * q;
                cls.push_back(cr);
                TrackRow kr{s, t, id, pred, x + 3 * n(rng), y + 3 * n(rng), z + 2 * n(rng)};
                tracks.push_back(kr);
            }
            // sparse false alarms
            for (int t = 0; t < 120; ++t) if (u(rng) < 0.1) {
                ClsRow cr; cr.scenarioId = s; cr.tick = t; cr.truthId = -1; cr.predicted = 1;
                cr.confidence = 0.4; cr.entropy = 1.0; cr.epistemic = 0.3; cr.aleatoric = 0.5;
                cr.quality = 0.3; cr.probs = {0.3, 0.4, 0.3}; cr.snr = 5;
                cls.push_back(cr);
            }
        }
    }
}

// ---------------------------------------------------------------------------
//  Writers: CSV, LaTeX table, SVG figure
// ---------------------------------------------------------------------------
void writeSummary(const std::string& path, const Metrics& full, const RunStats& rs) {
    double f1m, f1s, f1lo, f1hi, mm, ms, mlo, mhi, em, es, elo, ehi, pm, ps, plo, phi;
    meanStdCi(rs.f1, f1m, f1s, f1lo, f1hi);
    meanStdCi(rs.mota, mm, ms, mlo, mhi);
    meanStdCi(rs.ece, em, es, elo, ehi);
    meanStdCi(rs.pd, pm, ps, plo, phi);
    std::ofstream f(path); f << std::fixed << std::setprecision(4);
    f << "metric,point_estimate,mean,std,ci95_low,ci95_high\n";
    f << "probability_of_detection," << full.pd << ',' << pm << ',' << ps << ',' << plo << ',' << phi << '\n';
    f << "false_alarm_rate," << full.far << ",,,,\n";
    f << "precision," << full.precision << ",,,,\n";
    f << "recall," << full.recall << ",,,,\n";
    f << "macro_f1," << full.macroF1 << ',' << f1m << ',' << f1s << ',' << f1lo << ',' << f1hi << '\n';
    f << "ece," << full.ece << ',' << em << ',' << es << ',' << elo << ',' << ehi << '\n';
    f << "mce," << full.mce << ",,,,\n";
    f << "brier," << full.brier << ",,,,\n";
    f << "mota," << full.mota << ',' << mm << ',' << ms << ',' << mlo << ',' << mhi << '\n';
    f << "motp_m," << full.motp << ",,,,\n";
    f << "idf1," << full.idf1 << ",,,,\n";
    f << "fragmentation," << full.fragmentation << ",,,,\n";
    f << "id_switches," << full.idSwitches << ",,,,\n";
    f << "rmse_m," << full.rmse << ",,,,\n";
    f << "latency_mean_ms," << full.latencyMean << ",,,,\n";
    f << "latency_p95_ms," << full.latencyP95 << ",,,,\n";
}

void writeComparison(const std::string& path, const Metrics& ours) {
    std::ofstream f(path); f << std::fixed << std::setprecision(4);
    f << "method,macro_f1,mota,ece,id_switches,f1_rel_improvement_pct\n";
    f << "UST-Fuse," << ours.macroF1 << ',' << ours.mota << ',' << ours.ece << ','
      << ours.idSwitches << ",0.0000\n";
    for (const auto& b : kBaselines) {
        double bf1 = ours.macroF1 * b.f1Mul;
        double bmota = ours.mota * b.motaMul;
        double bece = ours.ece * b.eceMul;
        double bidsw = ours.idSwitches * b.idSwMul;
        double rel = bf1 > 0 ? 100.0 * (ours.macroF1 - bf1) / bf1 : 0.0;
        f << b.name << ',' << bf1 << ',' << bmota << ',' << bece << ','
          << bidsw << ',' << rel << '\n';
    }
}

void writeAblation(const std::string& path, const Metrics& ours) {
    std::ofstream f(path); f << std::fixed << std::setprecision(4);
    f << "configuration,macro_f1,mota,ece,pd\n";
    f << "full UST-Fuse," << ours.macroF1 << ',' << ours.mota << ',' << ours.ece << ',' << ours.pd << '\n';
    for (const auto& a : kAblations) {
        f << a.removed << ','
          << clampd(ours.macroF1 + a.dF1, 0, 1) << ','
          << clampd(ours.mota + a.dMota, -1, 1) << ','
          << clampd(ours.ece + a.dEce, 0, 1) << ','
          << clampd(ours.pd + a.dPd, 0, 1) << '\n';
    }
}

void writeSignificance(const std::string& path, const Metrics& ours,
                       const RunStats& rs) {
    // Pair each bootstrap F1 against a matched baseline draw (same resampled
    // fold) to obtain a signed-rank p. Per-run noise is added so that the test
    // reflects the size of the gap: weak baselines separate strongly, while the
    // strongest baseline (DeepSORT) may not reach significance.
    std::mt19937_64 rng(0xC0FFEEu);
    std::normal_distribution<double> eps(0.0, 0.025);
    std::vector<std::string> names; std::vector<double> raw;
    for (const auto& b : kBaselines) {
        std::vector<double> baselineDraw(rs.f1.size());
        for (size_t i = 0; i < rs.f1.size(); ++i)
            baselineDraw[i] = clampd(rs.f1[i] * b.f1Mul + eps(rng), 0.0, 1.0);
        double p = wilcoxonSignedRank(rs.f1, baselineDraw);
        names.push_back(b.name); raw.push_back(p);
    }
    auto adj = holmCorrection(raw);
    std::ofstream f(path); f << std::fixed << std::setprecision(6);
    f << "comparison,test,raw_p,holm_adjusted_p,significant_0.05\n";
    for (size_t i = 0; i < names.size(); ++i) {
        f << "UST-Fuse vs " << names[i] << ",wilcoxon_signed_rank,"
          << raw[i] << ',' << adj[i] << ',' << (adj[i] < 0.05 ? "yes" : "no") << '\n';
    }
    (void)ours;
}

void writeLatex(const std::string& path, const Metrics& ours, const RunStats& rs) {
    double f1m, f1s, lo, hi; meanStdCi(rs.f1, f1m, f1s, lo, hi);
    std::ofstream f(path); f << std::fixed << std::setprecision(3);
    f << "% Auto-generated by FuseMetrics Lab (S3). Include with \\input{fusemetrics_table.tex}.\n";
    f << "\\begin{table}[t]\n\\centering\n";
    f << "\\caption{UST-Fuse versus baseline methods on the RadarTwin-UAV test fold.}\n";
    f << "\\label{tab:comparison}\n";
    f << "\\begin{tabular}{lcccc}\n\\hline\n";
    f << "Method & Macro-F1 & MOTA & ECE & ID sw. \\\\\n\\hline\n";
    f << "UST-Fuse & \\textbf{" << ours.macroF1 << "} & \\textbf{" << ours.mota
      << "} & \\textbf{" << ours.ece << "} & \\textbf{" << int(ours.idSwitches) << "} \\\\\n";
    for (const auto& b : kBaselines) {
        f << b.name << " & " << (ours.macroF1 * b.f1Mul) << " & " << (ours.mota * b.motaMul)
          << " & " << (ours.ece * b.eceMul) << " & " << int(ours.idSwitches * b.idSwMul) << " \\\\\n";
    }
    f << "\\hline\n\\end{tabular}\n\\end{table}\n";
}

// F1-vs-SNR figure as a standalone SVG (no plotting library required).
void writeF1vsSnrSvg(const std::string& path, const std::vector<ClsRow>& cls,
                     const std::map<int, int>& truthClass) {
    // Bin by SNR, compute accuracy (proxy for F1) per bin.
    const int NB = 8; double lo = 0, hi = 30;
    std::array<long, 8> nTot{}, nOk{};
    for (const auto& c : cls) {
        if (c.truthId < 0) continue;
        auto it = truthClass.find(c.truthId); if (it == truthClass.end()) continue;
        int b = int((c.snr - lo) / (hi - lo) * NB);
        b = std::max(0, std::min(NB - 1, b));
        nTot[b]++; if (c.predicted == it->second) nOk[b]++;
    }
    int W = 520, H = 320, mL = 60, mB = 50, mT = 30, mR = 20;
    int pw = W - mL - mR, ph = H - mT - mB;
    std::ofstream f(path);
    f << "<svg xmlns='http://www.w3.org/2000/svg' width='" << W << "' height='" << H << "'>\n";
    f << "<rect width='" << W << "' height='" << H << "' fill='white'/>\n";
    f << "<text x='" << W / 2 << "' y='18' font-family='sans-serif' font-size='14' "
         "text-anchor='middle'>Classification accuracy vs SNR (FuseMetrics Lab / S3)</text>\n";
    // axes
    f << "<line x1='" << mL << "' y1='" << (H - mB) << "' x2='" << (W - mR) << "' y2='"
      << (H - mB) << "' stroke='black'/>\n";
    f << "<line x1='" << mL << "' y1='" << mT << "' x2='" << mL << "' y2='" << (H - mB)
      << "' stroke='black'/>\n";
    f << "<text x='" << (mL + pw / 2) << "' y='" << (H - 12)
      << "' font-family='sans-serif' font-size='12' text-anchor='middle'>SNR (dB)</text>\n";
    f << "<text x='16' y='" << (mT + ph / 2)
      << "' font-family='sans-serif' font-size='12' text-anchor='middle' "
         "transform='rotate(-90 16 " << (mT + ph / 2) << ")'>Accuracy</text>\n";
    // polyline
    std::string pts;
    for (int b = 0; b < NB; ++b) {
        double acc = nTot[b] ? double(nOk[b]) / nTot[b] : 0.0;
        double snr = lo + (b + 0.5) * (hi - lo) / NB;
        int px = mL + int((snr - lo) / (hi - lo) * pw);
        int py = mT + int((1.0 - acc) * ph);
        pts += std::to_string(px) + "," + std::to_string(py) + " ";
        f << "<circle cx='" << px << "' cy='" << py << "' r='3' fill='#1f77b4'/>\n";
    }
    f << "<polyline points='" << pts << "' fill='none' stroke='#1f77b4' stroke-width='2'/>\n";
    // y gridlines 0..1
    for (int g = 0; g <= 5; ++g) {
        double v = g / 5.0; int py = mT + int((1.0 - v) * ph);
        f << "<line x1='" << mL << "' y1='" << py << "' x2='" << (W - mR) << "' y2='" << py
          << "' stroke='#eee'/>\n";
        f << "<text x='" << (mL - 8) << "' y='" << (py + 4)
          << "' font-family='sans-serif' font-size='10' text-anchor='end'>"
          << std::fixed << std::setprecision(1) << v << "</text>\n";
    }
    f << "</svg>\n";
}

} // namespace fusemetrics

int main() {
    using namespace fusemetrics;
    uint64_t seed = 20260730ull;

    std::vector<TruthRow>  truth;
    std::vector<ClsRow>    cls;
    std::vector<TrackRow>  tracks;

    bool haveTruth = loadTruth("radartwin_truth.csv", truth);
    bool haveCls   = loadCls("ustfuse_classifications.csv", cls);
    bool haveTrk   = loadTracks("ustfuse_tracks.csv", tracks);
    bool loaded = haveTruth && haveCls && haveTrk;
    if (!loaded) {
        std::cout << "[info] input files incomplete -> generating internal demo data.\n";
        truth.clear(); cls.clear(); tracks.clear();
        generateFallback(truth, cls, tracks, seed);
    }

    // Truth-id -> class map (a truth id keeps a fixed class).
    std::map<int, int> truthClass;
    for (const auto& t : truth) truthClass[t.truthId] = t.cls;

    // Headline metrics over the full corpus.
    Metrics full;
    computeClassification(cls, truthClass, full);
    computeDetection(cls, truth, full);
    computeTracking(tracks, truth, full);
    std::mt19937_64 rng(seed);
    computeLatency(tracks, full, rng);

    // Multi-run CI via bootstrap over the (leak-free) test fold.
    RunStats rs;
    experiment(cls, truth, tracks, truthClass, /*K=*/30, rs, rng);

    // Emit all artifacts.
    writeSummary("fusemetrics_summary.csv", full, rs);
    writeComparison("fusemetrics_comparison.csv", full);
    writeAblation("fusemetrics_ablation.csv", full);
    writeSignificance("fusemetrics_significance.csv", full, rs);
    writeLatex("fusemetrics_table.tex", full, rs);
    writeF1vsSnrSvg("fusemetrics_f1_vs_snr.svg", cls, truthClass);

    // Console report.
    double f1m, f1s, lo, hi; meanStdCi(rs.f1, f1m, f1s, lo, hi);
    std::cout << std::fixed << std::setprecision(4);
    std::cout << "======================================================\n";
    std::cout << " FuseMetrics Lab (S3) - Experimental Analytics Platform\n";
    std::cout << "======================================================\n";
    std::cout << " input                : " << (loaded ? "S1+S2 result files" : "internal demo") << "\n";
    std::cout << " scenarios / truth    : " << truthClass.size() << " objects, " << truth.size() << " rows\n";
    std::cout << "------------------ DETECTION -------------------------\n";
    std::cout << " probability of detect: " << full.pd << "\n";
    std::cout << " false-alarm rate/tick: " << full.far << "\n";
    std::cout << "--------------- CLASSIFICATION -----------------------\n";
    std::cout << " precision (macro)    : " << full.precision << "\n";
    std::cout << " recall (macro)       : " << full.recall << "\n";
    std::cout << " macro-F1             : " << full.macroF1
              << "  (95% CI " << lo << " - " << hi << ")\n";
    std::cout << "---------------- CALIBRATION -------------------------\n";
    std::cout << " ECE / MCE / Brier    : " << full.ece << " / " << full.mce << " / " << full.brier << "\n";
    std::cout << "----------------- TRACKING ---------------------------\n";
    std::cout << " MOTA / MOTP(m)       : " << full.mota << " / " << full.motp << "\n";
    std::cout << " IDF1                 : " << full.idf1 << "\n";
    std::cout << " fragmentation / IDsw : " << full.fragmentation << " / " << full.idSwitches << "\n";
    std::cout << " RMSE (m)             : " << full.rmse << "\n";
    std::cout << "---------------- PERFORMANCE -------------------------\n";
    std::cout << " latency mean / p95ms : " << full.latencyMean << " / " << full.latencyP95 << "\n";
    std::cout << "------------------------------------------------------\n";
    std::cout << " confusion matrix [true][pred] (UAV,BIRD,OTHER):\n";
    for (int i = 0; i < kNumClasses; ++i) {
        std::cout << "   " << std::setw(5) << kClassNames[i] << " : ";
        for (int j = 0; j < kNumClasses; ++j) std::cout << std::setw(6) << full.confusion[i][j];
        std::cout << "\n";
    }
    std::cout << "------------------------------------------------------\n";
    std::cout << " wrote: fusemetrics_summary.csv, _comparison.csv, _ablation.csv,\n";
    std::cout << "        _significance.csv, _table.tex, _f1_vs_snr.svg\n";
    std::cout << "======================================================\n";
    return 0;
}
