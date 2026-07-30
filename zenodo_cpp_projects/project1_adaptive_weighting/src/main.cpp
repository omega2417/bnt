// =============================================================================
//  Adaptive Sensor Weighting for Tactical Spatial Attribution
//  Reference implementation of Section 3.3 ("Адаптивне зважування сенсорів")
//
//  This single-translation-unit C++17 program is designed to compile and run
//  as-is on OnlineGDB (https://www.onlinegdb.com), any g++/clang++ >= C++17,
//  or MSVC. It has NO external dependencies (standard library only) and ships
//  with a built-in demonstration scene, so it produces output with no input.
//
//  It implements the decomposed, auditable adaptive weight of a sensor block
//  in an incident window w_t, exactly as formalized in Chapter 3:
//
//      w~_s = m_s * pi_s * gamma_s * kappa_s * rho_s              (eq. 3.1, raw)
//      w_s^base = w~_s / sum_j w~_j                               (eq. 3.1, norm)
//
//  followed by projection onto the policy-admissible set (eq. 3.5): trust-domain
//  caps, a rate limiter and hysteresis (§3.3.7-3.3.8), and emergency exclusion.
//  The four canonical quality components are:
//
//      pi_s     provenance / base trust           (§3.3.2)  -- geometric mean, floor
//      gamma_s  geometric informativeness         (§3.3.3)  -- log-det FIM increment
//      kappa_s  calibration validity              (§3.3.4)  -- compat * exp(-age/tau)
//      rho_s    completeness / freshness / N_eff  (§3.3.5)  -- geometric mean
//
//  Every stage of the weight trace and a machine-readable reason code per
//  sensor are retained (§3.3.6, §3.3.11) so that "the weight was lowered" can
//  always be traced to provenance, geometry, calibration, completeness, a
//  domain cap, the rate limiter, or an emergency exclusion.
//
//  The program is an analytical illustration of the algorithm's structure; the
//  concrete operating points (caps, tau, hysteresis, rate delta) are declared
//  to_be_validated and must be fixed on training/validation splits (Chapter 4).
//
//  Author: generated for the dissertation software supplement (Zenodo).
//  License: MIT (see LICENSE).
// =============================================================================

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace saw {  // spatial adaptive weighting

// ---------------------------------------------------------------------------
// Small numeric helpers
// ---------------------------------------------------------------------------
static inline double clamp01(double x) {
    if (x < 0.0) return 0.0;
    if (x > 1.0) return 1.0;
    return x;
}

// Geometric mean with a policy floor. The geometric mean keeps sensitivity to
// the weakest link (§3.3.2): full transport integrity cannot compensate a
// missing agent attestation.
static double geo_mean(const std::vector<double>& v, double floor_val) {
    if (v.empty()) return floor_val;
    double acc = 0.0;
    for (double x : v) acc += std::log(std::max(x, 1e-12));
    double g = std::exp(acc / static_cast<double>(v.size()));
    return std::max(g, floor_val);
}

// ---------------------------------------------------------------------------
// Trust domains (§3.3.7): sensors that share a common lowest source of
// dependence (same agent/host, same uplink, same vendor firmware batch, ...).
// A single domain must not dominate the total information mass.
// ---------------------------------------------------------------------------
struct DomainPolicy {
    double cap;             // maximum total weight mass a single domain may hold
    std::string action;     // action tier this cap applies to (OBSERVE / AUTO ...)
};

// ---------------------------------------------------------------------------
// Raw quality inputs for one sensor block in the current window.
// These are the sub-components that feed the four canonical quality scores.
// ---------------------------------------------------------------------------
struct SensorInput {
    std::string id;
    int         domain;             // trust-domain index (§3.3.7)
    bool        active;             // binary mask m_s (§3.3.1)

    // --- provenance sub-components pi (§3.3.2), each in [0,1] --------------
    double attestation;             // agent integrity / secure boot attestation
    double key_material;            // certificate / key validity
    double transport_integrity;     // signed, integrity-checked transport
    double counter_monotonic;       // replay counter monotonicity
    double inventory;               // belongs to approved inventory

    // --- calibration kappa (§3.3.4) ---------------------------------------
    bool    calib_compatible;       // key config (chipset/channel/bw/firmware) matches
    double  calib_age_days;         // profile age
    double  calib_uncertainty;      // estimated calibration uncertainty in [0,1]

    // --- completeness rho (§3.3.5) ----------------------------------------
    double  n_eff;                  // effective (autocorrelation-aware) sample count
    double  freshness;              // age of data vs. window reference time, in [0,1]
    double  channel_coverage;       // dwell time on the relevant channel, in [0,1]
    double  field_completeness;     // fraction of mandatory fields present, in [0,1]

    // --- geometry gamma (§3.3.3) ------------------------------------------
    // Bearing (radians) from the candidate source to this sensor/anchor, used
    // to build a 2-D Fisher information matrix and score the log-det increment.
    double  bearing;
    double  local_precision;        // per-measurement information magnitude (>=0)

    // --- emergency exclusion (§3.3.8): a signed, machine-checkable reason ---
    bool         emergency_excluded;
    std::string  emergency_reason;

    // --- history for rate limiter / hysteresis (§3.3.8) -------------------
    double  prev_weight;            // final weight in the previous window
    bool    prev_low_trust;         // was the sensor in the low-trust state?
};

// ---------------------------------------------------------------------------
// Per-sensor weight trace (§3.3.6, §3.3.11): every non-commutative stage is
// retained so the ordering of constraints is itself reproducible.
// ---------------------------------------------------------------------------
struct WeightTrace {
    std::string id;
    int         domain;
    double      pi, gamma, kappa, rho;   // canonical components
    double      w_raw;                   // m * pi * gamma * kappa * rho    (eq 3.1)
    double      w_base;                   // after normalization             (eq 3.1)
    double      w_domain_capped;          // after trust-domain caps         (eq 3.5)
    double      w_rate_limited;           // after rate limiter              (§3.3.8)
    double      w_final;                  // final normalized weight
    std::string reason;                   // dominant reason code
    bool        low_trust;                // low-trust state after hysteresis
};

// ---------------------------------------------------------------------------
// Full weighting output (§3.3.10): the vector plus governance diagnostics.
// The subsystem returns weights only; it does NOT return a coordinate or an
// attack class -- those belong to §3.4 and §3.7 respectively.
// ---------------------------------------------------------------------------
struct WeightingResult {
    std::vector<WeightTrace> traces;
    double effective_domains;             // effective number of independent domains
    bool   insufficient_evidence;         // all blocks inactive -> prior + code
    std::string status;
};

// ---------------------------------------------------------------------------
// Configuration (all to_be_validated; NOT universal norms).
// ---------------------------------------------------------------------------
struct Config {
    double provenance_floor  = 0.05;   // policy lower bound on pi
    double calib_tau_days    = 45.0;   // calibration ageing scale tau (eq 3.3)
    double calib_floor       = 0.10;
    double geometry_scale    = 1.0;    // s0 in the log-det utility (eq 3.2)
    double geometry_reg      = 0.25;   // epsilon regularizing degenerate geometry
    double rate_delta        = 0.20;   // max |w_s - w_s_prev| per window
    double hyst_enter        = 0.08;   // enter low-trust when w_base < enter
    double hyst_exit         = 0.15;   // leave low-trust only when w_base > exit
    int    projection_iters  = 40;     // iterations of the constrained projection
    std::vector<DomainPolicy> domains; // per-domain caps
};

// ---------------------------------------------------------------------------
// gamma_s: geometric informativeness via the log-det increment of a
// regularized 2-D information matrix (eq. 3.2). We build the Fisher information
// of all active blocks, then measure the normalized gain contributed by s:
//
//      gamma_s = clip( (1/s0) * [ logdet(F + eps I) - logdet(F_-s + eps I) ] )
//
// Two collinear sensors both have high local precision yet barely shrink an
// elongated HPD region -- exactly what log-det penalizes.
// ---------------------------------------------------------------------------
static void det2x2(double a, double b, double c, double d, double& det) {
    det = a * d - b * c;
}

static double logdet_fim(const std::vector<const SensorInput*>& blocks,
                         int skip_index, double reg) {
    // Accumulate rank-1 contributions  local_precision * u u^T with
    // u = (cos bearing, sin bearing).
    double Fxx = reg, Fxy = 0.0, Fyy = reg;
    for (size_t i = 0; i < blocks.size(); ++i) {
        if (static_cast<int>(i) == skip_index) continue;
        const SensorInput* s = blocks[i];
        double c = std::cos(s->bearing), sn = std::sin(s->bearing);
        double p = std::max(s->local_precision, 0.0);
        Fxx += p * c * c;
        Fxy += p * c * sn;
        Fyy += p * sn * sn;
    }
    double det;
    det2x2(Fxx, Fxy, Fxy, Fyy, det);
    return std::log(std::max(det, 1e-12));
}

// ---------------------------------------------------------------------------
// Compute the four canonical quality components for one sensor.
// ---------------------------------------------------------------------------
static void compute_components(const SensorInput& s, const Config& cfg,
                               const std::vector<const SensorInput*>& active_blocks,
                               int active_index,
                               double& pi, double& gamma,
                               double& kappa, double& rho) {
    // pi (§3.3.2): geometric mean of provenance sub-components with a floor.
    pi = geo_mean({s.attestation, s.key_material, s.transport_integrity,
                   s.counter_monotonic, s.inventory}, cfg.provenance_floor);

    // kappa (§3.3.4, eq 3.3): compat indicator * exponential ageing * (1-uncert).
    double compat = s.calib_compatible ? 1.0 : 0.0;
    double ageing = std::exp(-std::max(s.calib_age_days, 0.0) / cfg.calib_tau_days);
    double uncert = 1.0 - clamp01(s.calib_uncertainty);
    kappa = compat * ageing * uncert;
    if (s.calib_compatible) kappa = std::max(kappa, cfg.calib_floor);

    // rho (§3.3.5, eq 3.4): geometric mean of completeness sub-components.
    // n_eff enters through a saturating transform: independent evidence, not
    // raw packet count, drives completeness.
    double neff_score = 1.0 - std::exp(-std::max(s.n_eff, 0.0) / 3.0);
    rho = geo_mean({neff_score, clamp01(s.freshness),
                    clamp01(s.channel_coverage), clamp01(s.field_completeness)},
                   0.0);

    // gamma (§3.3.3, eq 3.2): normalized log-det increment, clipped to [0,1].
    double full   = logdet_fim(active_blocks, -1, cfg.geometry_reg);
    double without = logdet_fim(active_blocks, active_index, cfg.geometry_reg);
    double gain = (full - without) / cfg.geometry_scale;
    gamma = clamp01(gain);
}

// ---------------------------------------------------------------------------
// Dominant reason code (§3.3.6): the single most limiting factor. This turns
// weighting from a hidden heuristic into a controllable metrological layer.
// ---------------------------------------------------------------------------
static std::string dominant_reason(double pi, double gamma, double kappa,
                                   double rho, bool emergency) {
    if (emergency) return "emergency_exclusion";
    struct { const char* name; double val; } comps[4] = {
        {"low_provenance",   pi},
        {"weak_geometry",    gamma},
        {"stale_calibration",kappa},
        {"low_completeness", rho},
    };
    int worst = 0;
    for (int i = 1; i < 4; ++i)
        if (comps[i].val < comps[worst].val) worst = i;
    if (comps[worst].val > 0.75) return "nominal";
    return comps[worst].name;
}

// ---------------------------------------------------------------------------
// Constrained projection onto the policy-admissible set (eq. 3.5):
//   (1) sum of active weights = 1        -- preserves total information scale
//   (2) w_s >= 0                          -- no negative weights
//   (3) sum over a domain <= cap          -- bounded group dominance (§3.3.7)
//   (4) |w_s - w_s_prev| <= rate_delta    -- rate limiter (§3.3.8)
// Implemented as an auditable iterative projection (water-filling on domains
// followed by a rate clamp), then renormalized. If constraints are infeasible
// the caller is expected to fall back to degraded mode with a conservative
// prior rather than silently relaxing them.
// ---------------------------------------------------------------------------
static void project_admissible(std::vector<double>& w,
                               const std::vector<int>& domain,
                               const std::vector<double>& prev,
                               const Config& cfg,
                               double domain_cap) {
    const size_t n = w.size();
    auto renorm = [&]() {
        double s = 0.0;
        for (double x : w) s += x;
        if (s <= 0.0) return;
        for (double& x : w) x /= s;
    };
    renorm();

    for (int it = 0; it < cfg.projection_iters; ++it) {
        // (3) domain caps: scale down any domain over the cap, spilling the
        // excess to under-cap domains proportionally to their headroom.
        int max_dom = 0;
        for (int d : domain) max_dom = std::max(max_dom, d);
        std::vector<double> dmass(max_dom + 1, 0.0);
        for (size_t i = 0; i < n; ++i) dmass[domain[i]] += w[i];

        double spilled = 0.0, headroom = 0.0;
        for (int d = 0; d <= max_dom; ++d) {
            if (dmass[d] > domain_cap && dmass[d] > 0.0) {
                double scale = domain_cap / dmass[d];
                for (size_t i = 0; i < n; ++i)
                    if (domain[i] == d) {
                        double reduced = w[i] * scale;
                        spilled += w[i] - reduced;
                        w[i] = reduced;
                    }
                dmass[d] = domain_cap;
            }
        }
        for (int d = 0; d <= max_dom; ++d)
            headroom += std::max(0.0, domain_cap - dmass[d]);

        if (spilled > 1e-12 && headroom > 1e-12) {
            for (size_t i = 0; i < n; ++i) {
                double dh = std::max(0.0, domain_cap - dmass[domain[i]]);
                if (dh > 0.0)
                    w[i] += spilled * (dh / headroom) *
                            (dmass[domain[i]] > 0 ? w[i] / dmass[domain[i]] : 0.0);
            }
        }

        // (4) rate limiter: clamp deviation from the previous window.
        for (size_t i = 0; i < n; ++i) {
            double lo = prev[i] - cfg.rate_delta;
            double hi = prev[i] + cfg.rate_delta;
            if (prev[i] > 0.0) {  // only limit sensors that existed before
                if (w[i] < lo) w[i] = std::max(0.0, lo);
                if (w[i] > hi) w[i] = hi;
            }
        }
        renorm();
    }
}

// ---------------------------------------------------------------------------
// Main weighting routine.
// ---------------------------------------------------------------------------
static WeightingResult compute_weights(const std::vector<SensorInput>& sensors,
                                       const Config& cfg,
                                       const std::string& action_tier) {
    WeightingResult res;
    res.insufficient_evidence = false;

    // Select the applicable domain cap for this action tier.
    double domain_cap = 1.0;
    for (const auto& dp : cfg.domains)
        if (dp.action == action_tier) domain_cap = dp.cap;

    // Active blocks (mask m_s = 1 and not emergency-excluded).
    std::vector<const SensorInput*> active;
    std::vector<int> active_idx_map;  // index into sensors[]
    for (size_t i = 0; i < sensors.size(); ++i) {
        const SensorInput& s = sensors[i];
        if (s.active && !s.emergency_excluded) {
            active.push_back(&s);
            active_idx_map.push_back(static_cast<int>(i));
        }
    }

    // Raw and base weights (eq 3.1).
    std::vector<WeightTrace> traces(sensors.size());
    double sum_raw = 0.0;
    for (size_t i = 0; i < sensors.size(); ++i) {
        const SensorInput& s = sensors[i];
        WeightTrace& t = traces[i];
        t.id = s.id; t.domain = s.domain;

        if (!s.active || s.emergency_excluded) {
            t.pi = t.gamma = t.kappa = t.rho = 0.0;
            t.w_raw = 0.0;
            t.reason = s.emergency_excluded ? ("emergency:" + s.emergency_reason)
                                            : "inactive_mask";
            continue;
        }
        // find this sensor's position in the active list
        int aidx = -1;
        for (size_t k = 0; k < active_idx_map.size(); ++k)
            if (active_idx_map[k] == static_cast<int>(i)) { aidx = static_cast<int>(k); break; }

        compute_components(s, cfg, active, aidx, t.pi, t.gamma, t.kappa, t.rho);
        // Product form (eq 3.1): a critically low component is NOT compensated.
        t.w_raw = t.pi * t.gamma * t.kappa * t.rho;
        sum_raw += t.w_raw;
        t.reason = dominant_reason(t.pi, t.gamma, t.kappa, t.rho, false);
    }

    // Insufficient evidence: denominator is zero (§3.3.1) -> predictive prior.
    if (sum_raw <= 1e-15) {
        res.insufficient_evidence = true;
        res.status = "INSUFFICIENT_EVIDENCE: no active block carries information; "
                     "return predictive prior, block high-risk automation";
        res.effective_domains = 0.0;
        for (auto& t : traces) {
            t.w_base = t.w_domain_capped = t.w_rate_limited = t.w_final = 0.0;
            if (t.reason.empty()) t.reason = "no_information";
        }
        res.traces = traces;
        return res;
    }

    for (auto& t : traces) t.w_base = (sum_raw > 0) ? t.w_raw / sum_raw : 0.0;

    // Constrained projection (eq 3.5) over active sensors.
    std::vector<double> w, prev; std::vector<int> dom;
    std::vector<int> back;  // active position -> sensors index
    for (size_t i = 0; i < sensors.size(); ++i) {
        if (traces[i].w_base > 0.0 || (sensors[i].active && !sensors[i].emergency_excluded)) {
            w.push_back(traces[i].w_base);
            prev.push_back(sensors[i].prev_weight);
            dom.push_back(sensors[i].domain);
            back.push_back(static_cast<int>(i));
        }
    }
    // Record domain-cap-only stage first (for the trace) by running a copy.
    std::vector<double> w_capstage = w;
    {
        std::vector<double> zero_prev(prev.size(), 0.0);
        Config tmp = cfg; tmp.projection_iters = 12;
        project_admissible(w_capstage, dom, zero_prev, tmp, domain_cap);
    }
    for (size_t k = 0; k < back.size(); ++k)
        traces[back[k]].w_domain_capped = w_capstage[k];

    // Full projection with rate limiter.
    project_admissible(w, dom, prev, cfg, domain_cap);
    for (size_t k = 0; k < back.size(); ++k) {
        traces[back[k]].w_rate_limited = w[k];
        traces[back[k]].w_final = w[k];
    }
    // Inactive sensors keep zero across all stages.
    for (auto& t : traces) {
        if (t.w_raw == 0.0) {
            t.w_base = t.w_domain_capped = t.w_rate_limited = t.w_final = 0.0;
        }
    }

    // Hysteresis / low-trust state (§3.3.8): asymmetric enter/exit thresholds.
    // Only an ACTIVE, non-excluded block can be "low trust"; an inactive mask or
    // an emergency exclusion is a neutral absence, not low trust (§3.3.5-3.3.6).
    for (auto& t : traces) {
        if (t.w_raw == 0.0) { t.low_trust = false; continue; }
        bool was_low = false;
        for (const auto& s : sensors) if (s.id == t.id) { was_low = s.prev_low_trust; break; }
        if (was_low) t.low_trust = (t.w_base < cfg.hyst_exit);      // stay low until > exit
        else         t.low_trust = (t.w_base < cfg.hyst_enter);     // enter only below enter
        if (t.low_trust && t.reason == "nominal") t.reason = "low_trust_hysteresis";
    }

    // Effective number of independent domains (§3.3.10): inverse Simpson index
    // over per-domain weight mass. Duplicating a stream must not increase it.
    int max_dom = 0; for (const auto& t : traces) max_dom = std::max(max_dom, t.domain);
    std::vector<double> dmass(max_dom + 1, 0.0);
    for (const auto& t : traces) dmass[t.domain] += t.w_final;
    double denom = 0.0; for (double m : dmass) denom += m * m;
    res.effective_domains = (denom > 0) ? 1.0 / denom : 0.0;

    res.traces = traces;
    res.status = "OK";
    return res;
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------
static void print_report(const WeightingResult& r, const std::string& tier) {
    std::cout << std::fixed << std::setprecision(4);
    std::cout << "\n================ ADAPTIVE SENSOR WEIGHTING (Section 3.3) ================\n";
    std::cout << "Action tier: " << tier << "   |   Status: " << r.status << "\n";
    std::cout << "------------------------------------------------------------------------\n";
    std::cout << " sensor  dom |   pi    gamma  kappa   rho  |  w_base  w_cap  w_rate  w_FIN | reason\n";
    std::cout << "------------------------------------------------------------------------\n";
    for (const auto& t : r.traces) {
        std::cout << std::setw(6) << t.id << "  " << std::setw(3) << t.domain << " | "
                  << std::setw(6) << t.pi << " " << std::setw(6) << t.gamma << " "
                  << std::setw(6) << t.kappa << " " << std::setw(5) << t.rho << " | "
                  << std::setw(7) << t.w_base << " " << std::setw(6) << t.w_domain_capped << " "
                  << std::setw(7) << t.w_rate_limited << " " << std::setw(6) << t.w_final
                  << " | " << t.reason << (t.low_trust ? " [LOW-TRUST]" : "") << "\n";
    }
    std::cout << "------------------------------------------------------------------------\n";
    double s = 0.0; for (const auto& t : r.traces) s += t.w_final;
    std::cout << "sum(active weights) = " << s
              << "   effective independent domains = " << r.effective_domains << "\n";
    std::cout << "========================================================================\n";
}

// ---------------------------------------------------------------------------
// Built-in demonstration scene (§3.3 illustrative; not empirical data).
//
//   D1  fully trusted, well-calibrated, informative geometry
//   D2  co-located with D1 in the SAME trust domain and nearly collinear
//       bearing -> weak marginal geometry + capped by the domain (duplication
//       must not increase a domain's mass, §3.3.11)
//   D3  independent domain, good geometry, but STALE calibration
//   D4  independent domain, low provenance (expired key / unknown agent)
//   D5  emergency-excluded (revoked certificate) -> mask forced to 0, bypasses
//       the rate limiter with a signed reason (§3.3.8)
//   D6  inactive mask (scanned wrong channel) -> neutral absence, not low trust
// ---------------------------------------------------------------------------
static std::vector<SensorInput> demo_scene() {
    std::vector<SensorInput> s(6);

    s[0] = {"D1", 0, true, 0.98,0.99,0.99,1.0,1.0, true, 5.0, 0.05,
            8.0, 0.95, 0.90, 1.0, 0.30, 1.0, false, "", 0.34, false};
    s[1] = {"D2", 0, true, 0.97,0.98,0.99,1.0,1.0, true, 6.0, 0.06,
            7.0, 0.92, 0.88, 1.0, 0.34, 1.0, false, "", 0.30, false};
    s[2] = {"D3", 1, true, 0.96,0.97,0.98,1.0,1.0, true, 70.0, 0.20,
            6.0, 0.80, 0.85, 0.95, 1.80, 1.0, false, "", 0.20, false};
    s[3] = {"D4", 2, true, 0.20,0.30,0.90,1.0,0.5, true, 10.0, 0.10,
            4.0, 0.70, 0.60, 0.90, 2.60, 1.0, false, "", 0.10, true};
    s[4] = {"D5", 3, true, 0.99,0.10,0.99,1.0,1.0, true, 3.0, 0.05,
            9.0, 0.99, 0.95, 1.0, 4.10, 1.0, true, "revoked_certificate", 0.06, false};
    s[5] = {"D6", 4, false,0.95,0.95,0.95,1.0,1.0, true, 8.0, 0.08,
            0.0, 0.0, 0.0, 0.0, 5.50, 0.0, false, "", 0.00, false};
    return s;
}

}  // namespace saw

int main() {
    using namespace saw;

    Config cfg;
    // Trust-domain caps by action tier (§3.3.7): a single domain may hold at
    // most 55% of the mass for passive OBSERVE, and only 40% for AUTO, where an
    // independent confirmation is required. Values are to_be_validated.
    cfg.domains = { {0.55, "OBSERVE"}, {0.40, "AUTO"} };

    std::vector<SensorInput> sensors = demo_scene();

    std::cout << "Reference implementation of Section 3.3 -- Adaptive Sensor Weighting.\n"
              << "Demonstration scene (analytical illustration, not empirical data).\n";

    // Same evidence, two action tiers -> different admissible caps (§3.3.7).
    for (const std::string& tier : {std::string("OBSERVE"), std::string("AUTO")}) {
        WeightingResult r = compute_weights(sensors, cfg, tier);
        print_report(r, tier);
    }

    // Completeness criteria check (§3.3.10): sum of active weights == 1,
    // zero weight for inactive/excluded blocks, every drop has a reason code.
    std::cout << "\nCompleteness invariants (Section 3.3.10):\n";
    WeightingResult r = compute_weights(sensors, cfg, "OBSERVE");
    double sum = 0.0; bool zero_ok = true, reason_ok = true;
    for (const auto& t : r.traces) {
        sum += t.w_final;
        if ((t.reason == "inactive_mask" || t.reason.rfind("emergency:",0)==0)
            && t.w_final != 0.0) zero_ok = false;
        if (t.reason.empty()) reason_ok = false;
    }
    std::cout << "  [" << (std::abs(sum-1.0) < 1e-6 ? "PASS" : "FAIL")
              << "] active weights sum to 1 (got " << std::setprecision(8) << sum << ")\n";
    std::cout << "  [" << (zero_ok ? "PASS" : "FAIL")
              << "] inactive / excluded blocks carry zero weight\n";
    std::cout << "  [" << (reason_ok ? "PASS" : "FAIL")
              << "] every weight has a machine-readable reason code\n";

    return 0;
}
