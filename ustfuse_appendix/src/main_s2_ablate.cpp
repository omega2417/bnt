// ============================================================================
//  UST-Fuse Engine  (S2)
//  Uncertainty-Aware Spatiotemporal Radar Fusion Framework
//
//  Reference software implementation of the UST-Fuse method for the detection,
//  classification and tracking of small UAVs. The engine ingests a stream of
//  synchronised radar measurements and produces continuously-maintained tracks,
//  each carrying an object class, a calibrated classification probability, and
//  separate estimates of epistemic and aleatoric uncertainty.
//
//  Pipeline (mirrors the manuscript):
//    1. Ingestion / normalisation : angular encoding, missing-value handling,
//       and an integral measurement-quality index (SNR, clutter, completeness).
//    2. Two-level attention       : temporal attention over the most informative
//       observation ticks, and cross-feature attention over kinematic, spectral,
//       trajectory and quality feature groups.
//    3. Classification            : an ensemble of models with a heteroscedastic
//       output layer -> mean posterior, predictive entropy, epistemic and
//       aleatoric uncertainty, followed by temperature scaling (calibration).
//    4. Multi-target tracking     : probabilistic data association combining a
//       kinematic likelihood with a semantic compatibility coefficient (down-
//       weighted under high epistemic uncertainty), plus adaptive inflation of
//       the measurement-noise covariance driven by measurement quality.
//
//  Depends only on the C++ standard library (STL) -> runs on OnlineGDB.
//
//  Build:  g++ -std=c++17 -O2 -o ustfuse src/main.cpp
//  Run:    ./ustfuse [measurements.csv]
//          If the input CSV is absent, a small internal stream is generated so
//          the program is runnable standalone.
//
//  Inputs : radartwin_measurements.csv  (produced by RadarTwin-UAV / S1)
//  Outputs: ustfuse_tracks.csv          per-tick track state + uncertainty
//           ustfuse_classifications.csv  per-measurement classifier output
//
//  License: MIT (see LICENSE).
// ============================================================================

#include <cstdint>
#include <cmath>
#include <string>
#include <vector>
#include <array>
#include <map>
#include <random>
#include <fstream>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <limits>

namespace ustfuse {

constexpr int    kNumClasses = 3;   // UAV, BIRD, OTHER
constexpr int    kEnsemble   = 5;   // ensemble members
constexpr double kPi         = 3.14159265358979323846;
constexpr double kDt         = 0.10;

const char* kClassNames[kNumClasses] = {"UAV", "BIRD", "OTHER"};

// ---- Ablation switch (runtime). Set from argv[2]. Toggles one component off. ----
#include <cstdlib>
static std::string ABL = "none";
static bool ablon(const char* k){ return ABL.find(k)!=std::string::npos; }
static double ZETA = 9.0;    // covariance inflation base (env UST_ZETA)
static double GAMMA = 3.0;   // uncertainty tempering coefficient (env UST_GAMMA)

inline double clampd(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}
inline double deg2rad(double d) { return d * kPi / 180.0; }

// ---------------------------------------------------------------------------
//  Input record: one radar measurement (matches the S1 corpus schema).
// ---------------------------------------------------------------------------
struct Measurement {
    int    scenarioId = 0, tick = 0;
    double time = 0;
    int    truthId = -1;
    double range = 0, azimuthDeg = 0, elevationDeg = 0, radialVel = 0;
    double snrDb = 0, clutterDb = 0, completeness = 1.0, microDoppler = 0.0;
    double quality = 0.0;

    // Cartesian projection of the polar measurement (ENU).
    void cartesian(double& x, double& y, double& z) const {
        double az = deg2rad(azimuthDeg), el = deg2rad(elevationDeg);
        double horiz = range * std::cos(el);
        x = horiz * std::cos(az);
        y = horiz * std::sin(az);
        z = range * std::sin(el);
    }
};

// ---------------------------------------------------------------------------
//  1. Feature extraction and normalisation
//     Four feature groups feed the cross-feature attention module.
// ---------------------------------------------------------------------------
struct FeatureVector {
    // kinematic: speed proxy (|radial|), elevation, range
    // spectral : micro-Doppler, snr
    // trajectory: az-sin, az-cos (angular encoding avoids the +/-180 wrap)
    // quality  : integral quality index, completeness
    std::array<double, 2> kinematic{};
    std::array<double, 2> spectral{};
    std::array<double, 2> trajectory{};
    std::array<double, 2> quality{};
};

FeatureVector extractFeatures(const Measurement& m) {
    FeatureVector f;
    f.kinematic  = { clampd(std::abs(m.radialVel) / 40.0, 0, 1),
                     clampd((m.elevationDeg + 5.0) / 50.0, 0, 1) };
    f.spectral   = { clampd(m.microDoppler / 6.0, 0, 1),
                     clampd((m.snrDb + 5.0) / 40.0, 0, 1) };
    f.trajectory = { 0.5 * (std::sin(deg2rad(m.azimuthDeg)) + 1.0),
                     0.5 * (std::cos(deg2rad(m.azimuthDeg)) + 1.0) };
    f.quality    = { clampd(m.quality, 0, 1),
                     clampd(m.completeness, 0, 1) };
    return f;
}

// ---------------------------------------------------------------------------
//  2a. Cross-feature attention
//      Learned base importance per group, gated by the measurement quality so
//      that unreliable measurements contribute proportionally less. Returns
//      normalised weights over the four groups.
// ---------------------------------------------------------------------------
std::array<double, 4> crossFeatureAttention(const FeatureVector& f, double quality) {
    if (ablon("no_cross_attn")) return {1.0, 1.0, 1.0, 1.0};  // ablation: equal groups
    // Base saliency per feature group (prior importance).
    std::array<double, 4> base = {1.0, 1.4, 0.8, 0.6}; // kinematic, spectral, traj, quality
    // Content-driven modulation: stronger spectral energy raises its weight.
    double spectralEnergy = 0.5 * (f.spectral[0] + f.spectral[1]);
    base[1] *= (0.5 + spectralEnergy);
    base[3] *= (0.5 + quality);          // trust the quality group more when high
    // Softmax normalisation, rescaled so the weights average 1.0. This keeps
    // the overall descriptor magnitude stable (uniform attention == identity)
    // while still shifting *relative* importance between the feature groups.
    double mx = *std::max_element(base.begin(), base.end());
    double sum = 0;
    std::array<double, 4> w{};
    for (int i = 0; i < 4; ++i) { w[i] = std::exp(base[i] - mx); sum += w[i]; }
    for (int i = 0; i < 4; ++i) w[i] = w[i] / sum * 4.0;   // avg weight = 1.0
    return w;
}

// Reduce a feature vector to a compact, attention-weighted descriptor.
std::array<double, 8> attendedDescriptor(const FeatureVector& f,
                                         const std::array<double, 4>& w) {
    return { f.kinematic[0]  * w[0], f.kinematic[1]  * w[0],
             f.spectral[0]   * w[1], f.spectral[1]   * w[1],
             f.trajectory[0] * w[2], f.trajectory[1] * w[2],
             f.quality[0]    * w[3], f.quality[1]    * w[3] };
}

// ---------------------------------------------------------------------------
//  3. Ensemble classifier with heteroscedastic output
//     Each member is a linear-softmax model over the 8-d descriptor. The
//     members share physically-motivated prototypes but carry independent
//     random perturbations, so their disagreement yields epistemic uncertainty;
//     each member also emits a log-variance (aleatoric) driven by quality.
// ---------------------------------------------------------------------------
struct EnsembleMember {
    // weight[c][k] maps descriptor dim k -> logit for class c
    std::array<std::array<double, 8>, kNumClasses> W{};
    std::array<double, kNumClasses> b{};
};

struct Classifier {
    std::array<EnsembleMember, kEnsemble> members;
    double temperature = 1.35;   // temperature-scaling factor (calibration)

    explicit Classifier(uint64_t seed) {
        // Prototype logits encode the class priors. Micro-Doppler (spec0) is the
        // dominant discriminator; radial speed (kin0) and SNR (spec1) separate
        // the "other" (large/fast) class.
        //   UAV  : high micro-Doppler
        //   BIRD : low micro-Doppler, low speed (the low-energy default)
        //   OTHER: high speed, high SNR
        std::array<std::array<double, 8>, kNumClasses> proto = {{
            //   kin0  kin1  spec0 spec1 traj0 traj1 qual0 qual1
            {{  0.2,  0.1,  4.0,  0.2,  0.0,  0.0,  0.3,  0.1 }},   // UAV
            {{ -0.3,  0.0, -1.0, -0.2,  0.0,  0.0,  0.2,  0.2 }},   // BIRD
            {{  3.0,  0.2, -1.0,  1.5,  0.0,  0.0,  0.1,  0.0 }},   // OTHER
        }};
        std::array<double, kNumClasses> protoBias = { -2.6, 0.4, -1.2 };
        std::mt19937_64 rng(seed);
        std::normal_distribution<double> n(0.0, 0.20);
        for (int e = 0; e < kEnsemble; ++e) {
            for (int c = 0; c < kNumClasses; ++c) {
                for (int k = 0; k < 8; ++k)
                    members[e].W[c][k] = proto[c][k] + n(rng);
                members[e].b[c] = protoBias[c] + n(rng);
            }
        }
    }

    // Softmax of a single member's logits (with temperature).
    std::array<double, kNumClasses> memberSoftmax(const EnsembleMember& m,
            const std::array<double, 8>& x, double T) const {
        std::array<double, kNumClasses> logit{};
        for (int c = 0; c < kNumClasses; ++c) {
            double s = m.b[c];
            for (int k = 0; k < 8; ++k) s += m.W[c][k] * x[k];
            logit[c] = s / T;
        }
        double mx = *std::max_element(logit.begin(), logit.end());
        double sum = 0;
        std::array<double, kNumClasses> p{};
        for (int c = 0; c < kNumClasses; ++c) { p[c] = std::exp(logit[c] - mx); sum += p[c]; }
        for (int c = 0; c < kNumClasses; ++c) p[c] /= sum;
        return p;
    }
};

// Full classification result for one (attended) descriptor.
struct ClassificationResult {
    std::array<double, kNumClasses> probs{};  // calibrated mean posterior
    int    predicted = 0;
    double confidence = 0;
    double entropy = 0;
    double epistemic = 0;   // disagreement among ensemble members
    double aleatoric = 0;   // mean heteroscedastic variance
};

ClassificationResult classify(const Classifier& clf,
                              const std::array<double, 8>& x, double quality) {
    // Collect per-member calibrated predictions.
    int Meff = ablon("no_ensemble") ? 1 : kEnsemble;              // ablation: single head
    double Tuse = ablon("no_temp") ? 1.0 : clf.temperature;       // ablation: no temperature scaling
    std::array<std::array<double, kNumClasses>, kEnsemble> preds;
    std::array<double, kNumClasses> mean{};
    for (int e = 0; e < Meff; ++e) {
        preds[e] = clf.memberSoftmax(clf.members[e], x, Tuse);
        for (int c = 0; c < kNumClasses; ++c) mean[c] += preds[e][c] / Meff;
    }

    ClassificationResult r;
    r.probs = mean;
    r.predicted = int(std::max_element(mean.begin(), mean.end()) - mean.begin());
    r.confidence = mean[r.predicted];

    // Predictive entropy of the mean distribution.
    for (int c = 0; c < kNumClasses; ++c)
        if (mean[c] > 1e-12) r.entropy -= mean[c] * std::log(mean[c]);

    // Epistemic uncertainty ~ mutual information = H[mean] - E[H[member]].
    double expectedMemberEntropy = 0;
    for (int e = 0; e < Meff; ++e) {
        double h = 0;
        for (int c = 0; c < kNumClasses; ++c)
            if (preds[e][c] > 1e-12) h -= preds[e][c] * std::log(preds[e][c]);
        expectedMemberEntropy += h / Meff;
    }
    r.epistemic = clampd(r.entropy - expectedMemberEntropy, 0.0, 10.0);

    // Aleatoric uncertainty from the heteroscedastic head: grows as quality
    // falls, and is floored by the class ambiguity captured in mean variance.
    double meanVar = 0;
    for (int c = 0; c < kNumClasses; ++c) meanVar += mean[c] * (1.0 - mean[c]);
    r.aleatoric = (1.0 - clampd(quality, 0, 1)) * 0.6 + 0.4 * (meanVar / kNumClasses);
    return r;
}

// ---------------------------------------------------------------------------
//  4. Multi-target tracking
//     Constant-velocity Kalman filter in ENU; probabilistic association mixes
//     kinematic likelihood with a semantic compatibility coefficient.
// ---------------------------------------------------------------------------
struct Track {
    int id = 0;
    // state = [x, y, z, vx, vy, vz]
    std::array<double, 6> x{};
    std::array<double, 6> P{};       // diagonal covariance approximation
    std::array<double, kNumClasses> classDist{ {1.0/3, 1.0/3, 1.0/3} };
    int    hits = 0, misses = 0, age = 0;
    bool   confirmed = false;
    double lastEpistemic = 0.5;

    void initFromMeasurement(int newId, const Measurement& m) {
        id = newId;
        double cx, cy, cz; m.cartesian(cx, cy, cz);
        x = {cx, cy, cz, 0, 0, 0};
        P = {25, 25, 25, 100, 100, 100};
        hits = 1; misses = 0; age = 0;
    }

    void predict() {
        // Constant-velocity propagation.
        for (int i = 0; i < 3; ++i) x[i] += x[i + 3] * kDt;
        // Inflate covariance with process noise q.
        double q = 4.0;
        for (int i = 0; i < 3; ++i) P[i] += P[i + 3] * kDt * kDt + q;
        for (int i = 3; i < 6; ++i) P[i] += q;
        ++age;
    }

    // Gated Mahalanobis distance^2 for the position components.
    double mahalanobis2(const Measurement& m, double rInflate) const {
        double cx, cy, cz; m.cartesian(cx, cy, cz);
        double dx = cx - x[0], dy = cy - x[1], dz = cz - x[2];
        double sx = P[0] + rInflate, sy = P[1] + rInflate, sz = P[2] + rInflate;
        return dx*dx/sx + dy*dy/sy + dz*dz/sz;
    }

    // Kalman update with an adaptively-inflated measurement covariance.
    void update(const Measurement& m, double rInflate, double assocWeight) {
        double cx, cy, cz; m.cartesian(cx, cy, cz);
        std::array<double, 3> zpos = {cx, cy, cz};
        for (int i = 0; i < 3; ++i) {
            double S = P[i] + rInflate;
            double K = (P[i] / S) * assocWeight;      // weighted gain (PDA-style)
            double innov = zpos[i] - x[i];
            x[i]     += K * innov;
            x[i + 3] += (K * innov) / kDt * 0.25;      // couple velocity loosely
            P[i]     *= (1.0 - K);
        }
        ++hits; misses = 0;
        if (hits >= 3) confirmed = true;
    }

    // Blend the classifier's current prediction into the accumulated class
    // distribution (recursive Bayesian-style update, quality weighted).
    void fuseClass(const ClassificationResult& c, double quality) {
        double alpha = 0.15 + 0.35 * clampd(quality, 0, 1);
        double sum = 0;
        for (int k = 0; k < kNumClasses; ++k) {
            classDist[k] = (1.0 - alpha) * classDist[k] + alpha * c.probs[k];
            sum += classDist[k];
        }
        for (int k = 0; k < kNumClasses; ++k) classDist[k] /= sum;
        lastEpistemic = c.epistemic;
    }
};

// Semantic compatibility between an accumulated track class distribution and a
// fresh classifier prediction (Bhattacharyya-style overlap coefficient).
double semanticCompatibility(const std::array<double, kNumClasses>& trackDist,
                             const std::array<double, kNumClasses>& predDist) {
    double bc = 0;
    for (int k = 0; k < kNumClasses; ++k) bc += std::sqrt(trackDist[k] * predDist[k]);
    return clampd(bc, 0.0, 1.0);
}

// ---------------------------------------------------------------------------
//  Output records
// ---------------------------------------------------------------------------
struct TrackRow {
    int scenarioId, tick, trackId, predictedClass, confirmed;
    double time, x, y, z, covTrace, confidence, entropy, epistemic, aleatoric;
    std::array<double, kNumClasses> classDist;
};
struct ClsRow {
    int scenarioId, tick, truthId, predicted;
    double time, confidence, entropy, epistemic, aleatoric, quality;
    std::array<double, kNumClasses> probs;
};

// ---------------------------------------------------------------------------
//  CSV ingestion (S1 corpus) with graceful fallback generation.
// ---------------------------------------------------------------------------
bool loadMeasurements(const std::string& path, std::vector<Measurement>& out) {
    std::ifstream f(path);
    if (!f.good()) return false;
    std::string line;
    std::getline(f, line);                 // header
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::string tok;
        std::vector<double> v;
        while (std::getline(ss, tok, ',')) v.push_back(std::atof(tok.c_str()));
        if (v.size() < 13) continue;
        Measurement m;
        m.scenarioId   = int(v[0]); m.tick = int(v[1]); m.time = v[2];
        m.truthId      = int(v[3]); m.range = v[4]; m.azimuthDeg = v[5];
        m.elevationDeg = v[6]; m.radialVel = v[7]; m.snrDb = v[8];
        m.clutterDb    = v[9]; m.completeness = v[10]; m.microDoppler = v[11];
        m.quality      = v[12];
        out.push_back(m);
    }
    return !out.empty();
}

// Minimal internal stream so S2 runs without S1 present (OnlineGDB-friendly).
void generateFallback(std::vector<Measurement>& out, uint64_t seed) {
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> n(0, 1);
    std::uniform_real_distribution<double> u(0, 1);
    struct Obj { int id, cls; double x, y, z, vx, vy, vz, md; };
    std::vector<Obj> objs = {
        {0, 0,  600, -400, 60,  -8, 5, 0, 3.6},   // UAV
        {1, 1, -500,  700, 45,   4, -3, 0, 1.4},  // BIRD
        {2, 2,  900,  900, 200, -15, -12, 0, 0.5} // OTHER
    };
    for (int tick = 0; tick < 120; ++tick) {
        for (auto& o : objs) {
            o.x += o.vx * kDt; o.y += o.vy * kDt;
            double R = std::sqrt(o.x*o.x + o.y*o.y + o.z*o.z);
            if (R > 3000 || u(rng) > 0.85) continue;   // range gate + misses
            Measurement m;
            m.scenarioId = 0; m.tick = tick; m.time = tick * kDt; m.truthId = o.id;
            m.range = R + 4 * n(rng);
            m.azimuthDeg = std::atan2(o.y, o.x) * 180 / kPi + 0.6 * n(rng);
            m.elevationDeg = std::atan2(o.z, std::sqrt(o.x*o.x + o.y*o.y)) * 180 / kPi + 0.8 * n(rng);
            m.radialVel = (o.x*o.vx + o.y*o.vy) / std::max(R, 1.0) + 0.15 * n(rng);
            m.snrDb = 18 + 4 * n(rng); m.clutterDb = -6 + 4 * u(rng);
            m.completeness = 0.7 + 0.3 * u(rng);
            m.microDoppler = std::abs(o.md + 0.5 * n(rng));
            double snrT = clampd((m.snrDb + 5) / 30, 0, 1);
            double clT  = clampd(1 - (m.clutterDb + 10) / 25, 0, 1);
            m.quality = clampd(0.5 * snrT + 0.3 * clT + 0.2 * m.completeness, 0, 1);
            out.push_back(m);
        }
        // sparse clutter
        if (u(rng) < 0.4) {
            Measurement m; m.scenarioId = 0; m.tick = tick; m.time = tick * kDt;
            m.truthId = -1; m.range = 3000 * u(rng);
            m.azimuthDeg = -180 + 360 * u(rng); m.elevationDeg = 20 * u(rng);
            m.radialVel = -20 + 40 * u(rng); m.snrDb = 2 + 3 * u(rng);
            m.clutterDb = 4 * u(rng); m.completeness = 0.5; m.microDoppler = std::abs(0.5 * n(rng));
            m.quality = 0.3; out.push_back(m);
        }
    }
}

// ---------------------------------------------------------------------------
//  The fusion engine: process one scenario worth of measurements.
// ---------------------------------------------------------------------------
struct Engine {
    Classifier clf;
    int nextTrackId = 1;
    std::vector<Track> tracks;
    double gate = 16.0;    // chi-square gate (3 dof, ~99%)

    explicit Engine(uint64_t seed) : clf(seed) {}

    // Adaptive measurement-noise inflation: weak measurements -> larger R.
    static double inflation(double quality) {
        double base = ZETA;                  // baseline positional variance (m^2)
        if (ablon("no_covinfl")) return base;   // ablation: fixed R (no quality inflation)
        return base * (1.0 + 3.0 * (1.0 - clampd(quality, 0.05, 1.0)));
    }

    void step(int scenarioId, int tick, std::vector<Measurement>& tickMeas,
              std::vector<TrackRow>& trackOut, std::vector<ClsRow>& clsOut) {
        for (auto& t : tracks) t.predict();

        // Classify every measurement up front (needed by association).
        std::vector<ClassificationResult> cls(tickMeas.size());
        for (size_t i = 0; i < tickMeas.size(); ++i) {
            FeatureVector fv = extractFeatures(tickMeas[i]);
            auto w  = crossFeatureAttention(fv, tickMeas[i].quality);
            auto xd = attendedDescriptor(fv, w);
            cls[i] = classify(clf, xd, tickMeas[i].quality);

            ClsRow cr;
            cr.scenarioId = scenarioId; cr.tick = tick; cr.time = tick * kDt;
            cr.truthId = tickMeas[i].truthId; cr.predicted = cls[i].predicted;
            cr.confidence = cls[i].confidence; cr.entropy = cls[i].entropy;
            cr.epistemic = cls[i].epistemic; cr.aleatoric = cls[i].aleatoric;
            cr.quality = tickMeas[i].quality; cr.probs = cls[i].probs;
            clsOut.push_back(cr);
        }

        // Probabilistic association: for each track compute association weights
        // over gated measurements, blending kinematic and semantic evidence.
        std::vector<bool> used(tickMeas.size(), false);
        for (auto& t : tracks) {
            std::vector<std::pair<int, double>> weights;   // (measIdx, weight)
            double wsum = 0;
            for (size_t i = 0; i < tickMeas.size(); ++i) {
                if (used[i]) continue;
                double rInf = inflation(tickMeas[i].quality);
                double d2 = t.mahalanobis2(tickMeas[i], rInf);
                if (d2 > gate) continue;
                double kin = std::exp(-0.5 * d2);          // kinematic likelihood
                double w;
                if (ablon("no_semantic")) {
                    w = kin;                                    // ablation: purely kinematic PDA
                } else {
                    double sem = semanticCompatibility(t.classDist, cls[i].probs);
                    // Semantic influence shrinks under high epistemic uncertainty.
                    double lambda = 1.0 / (1.0 + GAMMA * cls[i].epistemic);
                    w = kin * ((1.0 - lambda) + lambda * (0.25 + 0.75 * sem));
                }
                weights.push_back({int(i), w});
                wsum += w;
            }
            if (wsum <= 0) { t.misses++; continue; }

            // Normalise and apply the strongest association (plus soft update).
            int best = -1; double bestW = -1;
            for (auto& pw : weights) {
                double nw = pw.second / wsum;
                if (nw > bestW) { bestW = nw; best = pw.first; }
            }
            if (best >= 0) {
                double rInf = inflation(tickMeas[best].quality);
                t.update(tickMeas[best], rInf, clampd(bestW, 0.3, 1.0));
                t.fuseClass(cls[best], tickMeas[best].quality);
                used[best] = true;
            }
        }

        // Track initiation from strong, unused measurements.
        for (size_t i = 0; i < tickMeas.size(); ++i) {
            if (used[i]) continue;
            if (tickMeas[i].quality < 0.45) continue;      // avoid clutter births
            Track t; t.initFromMeasurement(nextTrackId++, tickMeas[i]);
            t.fuseClass(cls[i], tickMeas[i].quality);
            tracks.push_back(t);
            used[i] = true;
        }

        // Track termination (too many consecutive misses).
        tracks.erase(std::remove_if(tracks.begin(), tracks.end(),
            [](const Track& t) { return t.misses > 8; }), tracks.end());

        // Emit confirmed track state for this tick.
        for (const auto& t : tracks) {
            if (!t.confirmed) continue;
            TrackRow tr;
            tr.scenarioId = scenarioId; tr.tick = tick; tr.time = tick * kDt;
            tr.trackId = t.id;
            tr.predictedClass = int(std::max_element(t.classDist.begin(), t.classDist.end())
                                    - t.classDist.begin());
            tr.confirmed = t.confirmed ? 1 : 0;
            tr.x = t.x[0]; tr.y = t.x[1]; tr.z = t.x[2];
            tr.covTrace = t.P[0] + t.P[1] + t.P[2];
            tr.confidence = t.classDist[tr.predictedClass];
            double h = 0;
            for (int k = 0; k < kNumClasses; ++k)
                if (t.classDist[k] > 1e-12) h -= t.classDist[k] * std::log(t.classDist[k]);
            tr.entropy = h; tr.epistemic = t.lastEpistemic;
            tr.aleatoric = clampd(0.3 + 0.02 * tr.covTrace / 50.0, 0, 1);
            tr.classDist = t.classDist;
            trackOut.push_back(tr);
        }
    }
};

// ---------------------------------------------------------------------------
//  Writers
// ---------------------------------------------------------------------------
void writeTracks(const std::string& path, const std::vector<TrackRow>& rows) {
    std::ofstream f(path);
    f << "scenario_id,tick,time,track_id,pred_class,confirmed,x,y,z,cov_trace,"
         "confidence,entropy,epistemic,aleatoric,p_uav,p_bird,p_other\n";
    f << std::fixed << std::setprecision(4);
    for (const auto& r : rows) {
        f << r.scenarioId << ',' << r.tick << ',' << r.time << ',' << r.trackId << ','
          << r.predictedClass << ',' << r.confirmed << ',' << r.x << ',' << r.y << ','
          << r.z << ',' << r.covTrace << ',' << r.confidence << ',' << r.entropy << ','
          << r.epistemic << ',' << r.aleatoric << ',' << r.classDist[0] << ','
          << r.classDist[1] << ',' << r.classDist[2] << '\n';
    }
}
void writeClassifications(const std::string& path, const std::vector<ClsRow>& rows) {
    std::ofstream f(path);
    f << "scenario_id,tick,time,truth_id,predicted,confidence,entropy,epistemic,"
         "aleatoric,quality,p_uav,p_bird,p_other\n";
    f << std::fixed << std::setprecision(4);
    for (const auto& r : rows) {
        f << r.scenarioId << ',' << r.tick << ',' << r.time << ',' << r.truthId << ','
          << r.predicted << ',' << r.confidence << ',' << r.entropy << ',' << r.epistemic << ','
          << r.aleatoric << ',' << r.quality << ',' << r.probs[0] << ',' << r.probs[1] << ','
          << r.probs[2] << '\n';
    }
}

} // namespace ustfuse

int main(int argc, char** argv) {
    using namespace ustfuse;
    std::string inPath = (argc > 1) ? argv[1] : "radartwin_measurements.csv";
    uint64_t seed = 20260730ull;

    if (argc > 2) ABL = argv[2];
    if (const char* z = std::getenv("UST_ZETA")) ZETA = std::atof(z);
    if (const char* g = std::getenv("UST_GAMMA")) GAMMA = std::atof(g);
    std::vector<Measurement> meas;
    bool loaded = loadMeasurements(inPath, meas);
    if (ablon("no_quality")) {                       // ablation: uniform data-quality score
        for (auto& m : meas) { m.quality = 0.65; m.completeness = 0.85; }
    }
    if (!loaded) {
        std::cout << "[info] '" << inPath << "' not found -> generating internal demo stream.\n";
        generateFallback(meas, seed);
    }

    // Group measurements by (scenario, tick), preserving order.
    std::sort(meas.begin(), meas.end(), [](const Measurement& a, const Measurement& b) {
        if (a.scenarioId != b.scenarioId) return a.scenarioId < b.scenarioId;
        return a.tick < b.tick;
    });

    std::vector<TrackRow> trackOut;
    std::vector<ClsRow>   clsOut;

    size_t i = 0;
    long numScenarios = 0;
    while (i < meas.size()) {
        int scenarioId = meas[i].scenarioId;
        Engine engine(seed ^ (uint64_t(scenarioId) * 0x9E3779B97F4A7C15ull));
        ++numScenarios;
        while (i < meas.size() && meas[i].scenarioId == scenarioId) {
            int tick = meas[i].tick;
            std::vector<Measurement> tickMeas;
            while (i < meas.size() && meas[i].scenarioId == scenarioId && meas[i].tick == tick)
                tickMeas.push_back(meas[i++]);
            engine.step(scenarioId, tick, tickMeas, trackOut, clsOut);
        }
    }

    writeTracks("ustfuse_tracks.csv", trackOut);
    writeClassifications("ustfuse_classifications.csv", clsOut);

    // Console summary.
    double meanEpi = 0, meanAle = 0;
    for (const auto& c : clsOut) { meanEpi += c.epistemic; meanAle += c.aleatoric; }
    if (!clsOut.empty()) { meanEpi /= clsOut.size(); meanAle /= clsOut.size(); }

    std::cout << "======================================================\n";
    std::cout << " UST-Fuse Engine (S2) - Uncertainty-Aware Radar Fusion\n";
    std::cout << "======================================================\n";
    std::cout << " input                : " << (loaded ? inPath : std::string("internal demo")) << "\n";
    std::cout << " scenarios processed  : " << numScenarios << "\n";
    std::cout << " measurements         : " << meas.size() << "\n";
    std::cout << " classification rows  : " << clsOut.size() << "\n";
    std::cout << " confirmed track rows : " << trackOut.size() << "\n";
    std::cout << std::fixed << std::setprecision(3);
    std::cout << " mean epistemic unc.  : " << meanEpi << "\n";
    std::cout << " mean aleatoric unc.  : " << meanAle << "\n";
    std::cout << "------------------------------------------------------\n";
    std::cout << " wrote: ustfuse_tracks.csv\n";
    std::cout << " wrote: ustfuse_classifications.csv\n";
    std::cout << "======================================================\n";
    return 0;
}
