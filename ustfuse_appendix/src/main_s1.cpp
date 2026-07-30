// ============================================================================
//  RadarTwin-UAV  (S1)
//  Synthetic Radar Scenario and Digital Twin Generator for small-UAV detection
//
//  Reference software implementation accompanying the manuscript
//  "Uncertainty-Aware Spatiotemporal Radar Fusion (UST-Fuse)".
//
//  This program is a self-contained C++17 digital twin of a monitored volume
//  of airspace. It models the motion of small UAVs, birds and other aerial
//  objects, the operation of a radar sensor, clutter, missed detections and
//  measurement errors, and it emits a fully-labelled, reproducible corpus.
//
//  Design goals:
//   * Depends only on the C++ standard library (STL) -> runs on OnlineGDB.
//   * Deterministic given a seed (std::mt19937_64).
//   * Emits CSV + JSON + a run manifest so results are reproducible.
//
//  Build:   g++ -std=c++17 -O2 -o radartwin src/main.cpp
//  Run:     ./radartwin  [seed]  [num_scenarios]
//
//  Outputs (written to the current working directory):
//   * radartwin_measurements.csv   sensor-level detections (with false alarms)
//   * radartwin_truth.csv          per-tick ground-truth object states
//   * radartwin_scenarios.json     scenario configuration + metadata + seed
//
//  License: MIT (see LICENSE).
// ============================================================================

#include <cstdint>
#include <cmath>
#include <string>
#include <vector>
#include <array>
#include <random>
#include <fstream>
#include <sstream>
#include <iostream>
#include <iomanip>
#include <algorithm>

namespace radartwin {

// ---------------------------------------------------------------------------
//  Constants and small helpers
// ---------------------------------------------------------------------------
constexpr double kPi = 3.14159265358979323846;
constexpr double kDt = 0.10;   // sensor revisit interval, seconds (10 Hz)

inline double deg2rad(double d) { return d * kPi / 180.0; }
inline double rad2deg(double r) { return r * 180.0 / kPi; }
inline double clampd(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

// Object taxonomy used in the corpus.
enum class ObjectClass { UAV = 0, Bird = 1, Other = 2 };

const char* classToString(ObjectClass c) {
    switch (c) {
        case ObjectClass::UAV:   return "UAV";
        case ObjectClass::Bird:  return "BIRD";
        case ObjectClass::Other: return "OTHER";
    }
    return "OTHER";
}

// Manoeuvre archetypes drive the acceleration model.
enum class Maneuver { Straight = 0, Weaving = 1, Hover = 2, Diving = 3 };

const char* maneuverToString(Maneuver m) {
    switch (m) {
        case Maneuver::Straight: return "STRAIGHT";
        case Maneuver::Weaving:  return "WEAVING";
        case Maneuver::Hover:    return "HOVER";
        case Maneuver::Diving:   return "DIVING";
    }
    return "STRAIGHT";
}

// Scenario multiplicity archetypes required by the methodology.
enum class ScenarioKind { Individual = 0, Simultaneous = 1, Sequential = 2, Combined = 3 };

const char* scenarioKindToString(ScenarioKind k) {
    switch (k) {
        case ScenarioKind::Individual:   return "INDIVIDUAL";
        case ScenarioKind::Simultaneous: return "SIMULTANEOUS";
        case ScenarioKind::Sequential:   return "SEQUENTIAL";
        case ScenarioKind::Combined:     return "COMBINED";
    }
    return "INDIVIDUAL";
}

// ---------------------------------------------------------------------------
//  Radar sensor model
// ---------------------------------------------------------------------------
struct RadarSensor {
    // The sensor sits at the origin of a local East-North-Up (ENU) frame.
    double maxRange      = 3000.0;  // m
    double rangeSigma    = 4.0;     // m,   range measurement noise (1 sigma)
    double azimuthSigma  = 0.6;     // deg, azimuth noise
    double elevationSigma= 0.8;     // deg, elevation noise
    double dopplerSigma  = 0.15;    // m/s, radial-velocity noise
    double clutterLambda = 0.8;     // mean Poisson count of false alarms / tick
    double refSnrDb      = 34.0;    // reference SNR for a 0 dBsm target at 1 km
};

// ---------------------------------------------------------------------------
//  Object (target) description and instantaneous kinematic state
// ---------------------------------------------------------------------------
struct ObjectState {
    // ENU position (m) and velocity (m/s).
    double x = 0, y = 0, z = 0;
    double vx = 0, vy = 0, vz = 0;
};

struct ObjectSpec {
    int          id = 0;
    ObjectClass  cls = ObjectClass::UAV;
    Maneuver     maneuver = Maneuver::Straight;
    double       rcsDbsm = -10.0;   // effective radar cross section, dBsm
    double       speed = 12.0;      // nominal speed, m/s
    double       headingDeg = 0.0;  // approach direction in the XY plane
    double       cruiseAlt = 80.0;  // nominal altitude, m
    int          birthTick = 0;     // first tick the object exists
    int          deathTick = 200;   // last tick the object exists
    ObjectState  state;             // mutable, advanced by the motion model
    double       maneuverPhase = 0.0;
};

// Per-object nominal parameters sampled by class, capturing the physical
// differences that a downstream classifier is expected to exploit.
void sampleClassParameters(ObjectSpec& o, std::mt19937_64& rng) {
    std::uniform_real_distribution<double> u(0.0, 1.0);
    switch (o.cls) {
        case ObjectClass::UAV:
            o.speed     = 6.0 + 18.0 * u(rng);      // 6..24 m/s
            o.rcsDbsm   = -22.0 + 8.0 * u(rng);     // small, low RCS
            o.cruiseAlt = 30.0 + 120.0 * u(rng);
            o.maneuver  = static_cast<Maneuver>(1 + int(3 * u(rng))); // agile
            break;
        case ObjectClass::Bird:
            o.speed     = 4.0 + 12.0 * u(rng);
            o.rcsDbsm   = -30.0 + 6.0 * u(rng);     // very small
            o.cruiseAlt = 20.0 + 80.0 * u(rng);
            o.maneuver  = (u(rng) < 0.6) ? Maneuver::Weaving : Maneuver::Straight;
            break;
        case ObjectClass::Other:
            o.speed     = 20.0 + 60.0 * u(rng);     // fast / large
            o.rcsDbsm   = -5.0 + 15.0 * u(rng);
            o.cruiseAlt = 100.0 + 300.0 * u(rng);
            o.maneuver  = Maneuver::Straight;
            break;
    }
    o.headingDeg = 360.0 * u(rng);
}

// Initialise ENU kinematic state from the sampled nominal parameters.
void initState(ObjectSpec& o, std::mt19937_64& rng) {
    std::uniform_real_distribution<double> u(0.0, 1.0);
    // Enter the volume from a random bearing near the maximum range.
    double bearing = 360.0 * u(rng);
    double r0 = 600.0 + 1100.0 * u(rng);
    o.state.x = r0 * std::cos(deg2rad(bearing));
    o.state.y = r0 * std::sin(deg2rad(bearing));
    o.state.z = o.cruiseAlt;
    double h = deg2rad(o.headingDeg);
    o.state.vx = o.speed * std::cos(h);
    o.state.vy = o.speed * std::sin(h);
    o.state.vz = 0.0;
}

// Advance the object's kinematic state by one tick using its manoeuvre model.
void advance(ObjectSpec& o, std::mt19937_64& rng) {
    std::normal_distribution<double> n(0.0, 1.0);
    double ax = 0, ay = 0, az = 0;
    o.maneuverPhase += kDt;
    switch (o.maneuver) {
        case Maneuver::Straight:
            ax = 0.2 * n(rng); ay = 0.2 * n(rng);
            break;
        case Maneuver::Weaving: {
            // Sinusoidal lateral acceleration -> characteristic micro-Doppler.
            double w = 2.0 * kPi * 0.25;                  // 0.25 Hz weave
            double perp = std::atan2(o.state.vy, o.state.vx) + kPi / 2.0;
            double amp = 6.0 * std::sin(w * o.maneuverPhase);
            ax = amp * std::cos(perp); ay = amp * std::sin(perp);
            break;
        }
        case Maneuver::Hover:
            // Near-stationary with small buffeting.
            o.state.vx *= 0.85; o.state.vy *= 0.85;
            ax = 0.5 * n(rng); ay = 0.5 * n(rng); az = 0.3 * n(rng);
            break;
        case Maneuver::Diving:
            az = -4.0;                                    // descend
            ax = 0.3 * n(rng); ay = 0.3 * n(rng);
            break;
    }
    o.state.vx += ax * kDt; o.state.vy += ay * kDt; o.state.vz += az * kDt;
    o.state.x  += o.state.vx * kDt;
    o.state.y  += o.state.vy * kDt;
    o.state.z   = clampd(o.state.z + o.state.vz * kDt, 5.0, 600.0);
}

// ---------------------------------------------------------------------------
//  A single radar detection (measurement) row of the corpus.
// ---------------------------------------------------------------------------
struct Measurement {
    int    scenarioId = 0;
    int    tick = 0;
    double time = 0.0;
    int    truthId = -1;        // -1 => false alarm / clutter
    // Polar measurement in the sensor frame.
    double range = 0, azimuthDeg = 0, elevationDeg = 0, radialVel = 0;
    double snrDb = 0, clutterDb = 0, completeness = 1.0;
    double microDoppler = 0.0;  // spectral spread descriptor
    double quality = 0.0;       // integral measurement-quality index [0,1]
};

// Ground-truth row (used by S3 to score S2).
struct TruthRow {
    int    scenarioId = 0;
    int    tick = 0;
    double time = 0.0;
    int    truthId = 0;
    int    cls = 0;
    double x = 0, y = 0, z = 0, vx = 0, vy = 0, vz = 0;
    int    exists = 1;
};

// ---------------------------------------------------------------------------
//  Sensor simulation: convert a true object state into a noisy detection,
//  or return "not detected" (missed observation).
// ---------------------------------------------------------------------------
struct Detector {
    RadarSensor sensor;
    std::mt19937_64 rng;

    explicit Detector(uint64_t seed) : rng(seed) {}

    // Free-space SNR falls off as 1/R^4 (radar equation), scaled by RCS.
    double snrDb(double range, double rcsDbsm) const {
        double rkm = std::max(range, 1.0) / 1000.0;
        return sensor.refSnrDb + rcsDbsm - 40.0 * std::log10(rkm);
    }

    // Detection probability from an SNR-driven logistic (Swerling-like).
    double detectionProbability(double snr) const {
        return 1.0 / (1.0 + std::exp(-(snr - 8.0) / 3.0));
    }

    // Integral quality index combines SNR, residual clutter and completeness.
    static double qualityIndex(double snrDb, double clutterDb, double completeness) {
        double snrTerm      = clampd((snrDb + 5.0) / 30.0, 0.0, 1.0);
        double clutterTerm  = clampd(1.0 - (clutterDb + 10.0) / 25.0, 0.0, 1.0);
        double q = 0.5 * snrTerm + 0.3 * clutterTerm + 0.2 * completeness;
        return clampd(q, 0.0, 1.0);
    }

    // Produce a measurement for a true object; returns false if missed.
    bool observe(const ObjectSpec& o, int scenarioId, int tick, Measurement& out) {
        double R = std::sqrt(o.state.x*o.state.x + o.state.y*o.state.y + o.state.z*o.state.z);
        if (R > sensor.maxRange) return false;

        double snr = snrDb(R, o.rcsDbsm);
        double pd  = detectionProbability(snr);
        std::uniform_real_distribution<double> u(0.0, 1.0);
        // Completeness models partial occlusion / beam dwell fraction.
        double completeness = clampd(0.7 + 0.3 * u(rng), 0.0, 1.0);
        if (u(rng) > pd * completeness) return false;   // missed observation

        std::normal_distribution<double> n(0.0, 1.0);
        double azimuth   = rad2deg(std::atan2(o.state.y, o.state.x));
        double horiz     = std::sqrt(o.state.x*o.state.x + o.state.y*o.state.y);
        double elevation = rad2deg(std::atan2(o.state.z, horiz));
        // Radial velocity = projection of velocity onto the line of sight.
        double radial = (o.state.x*o.state.vx + o.state.y*o.state.vy + o.state.z*o.state.vz) / std::max(R, 1e-6);

        out.scenarioId   = scenarioId;
        out.tick         = tick;
        out.time         = tick * kDt;
        out.truthId      = o.id;
        out.range        = R + sensor.rangeSigma * n(rng);
        out.azimuthDeg   = azimuth + sensor.azimuthSigma * n(rng);
        out.elevationDeg = elevation + sensor.elevationSigma * n(rng);
        out.radialVel    = radial + sensor.dopplerSigma * n(rng);
        double clutterDb = -10.0 + 8.0 * u(rng);
        out.snrDb        = snr + 1.0 * n(rng);
        out.clutterDb    = clutterDb;
        out.completeness = completeness;
        // Micro-Doppler spread: rotor/wing modulation, class-dependent.
        double base = (o.cls == ObjectClass::UAV) ? 3.5 :
                      (o.cls == ObjectClass::Bird) ? 1.5 : 0.4;
        out.microDoppler = std::abs(base + 0.6 * n(rng)
                          + ((o.maneuver == Maneuver::Weaving) ? 1.2 : 0.0));
        out.quality      = qualityIndex(out.snrDb, out.clutterDb, out.completeness);
        return true;
    }

    // Poisson-distributed clutter detections not associated with any object.
    void generateClutter(int scenarioId, int tick, std::vector<Measurement>& sink) {
        std::poisson_distribution<int> pois(sensor.clutterLambda);
        std::uniform_real_distribution<double> u(0.0, 1.0);
        std::normal_distribution<double> n(0.0, 1.0);
        int nfa = pois(rng);
        for (int i = 0; i < nfa; ++i) {
            Measurement m;
            m.scenarioId   = scenarioId;
            m.tick         = tick;
            m.time         = tick * kDt;
            m.truthId      = -1;                       // false alarm
            m.range        = sensor.maxRange * u(rng);
            m.azimuthDeg   = -180.0 + 360.0 * u(rng);
            m.elevationDeg = -5.0 + 45.0 * u(rng);
            m.radialVel    = -30.0 + 60.0 * u(rng);
            m.snrDb        = -2.0 + 6.0 * u(rng);
            m.clutterDb    = -5.0 + 10.0 * u(rng);
            m.completeness = 0.4 + 0.3 * u(rng);
            m.microDoppler = std::abs(0.5 * n(rng));
            m.quality      = qualityIndex(m.snrDb, m.clutterDb, m.completeness);
            sink.push_back(m);
        }
    }
};

// ---------------------------------------------------------------------------
//  Scenario: a set of objects observed over a common time window.
// ---------------------------------------------------------------------------
struct Scenario {
    int         id = 0;
    ScenarioKind kind = ScenarioKind::Individual;
    int         numTicks = 200;
    std::vector<ObjectSpec> objects;
};

// Build one scenario of the requested multiplicity archetype.
Scenario buildScenario(int id, ScenarioKind kind, std::mt19937_64& rng) {
    Scenario s;
    s.id = id;
    s.kind = kind;
    std::uniform_real_distribution<double> u(0.0, 1.0);
    s.numTicks = 150 + int(150 * u(rng));

    int nObj = 1;
    switch (kind) {
        case ScenarioKind::Individual:   nObj = 1; break;
        case ScenarioKind::Simultaneous: nObj = 2 + int(4 * u(rng)); break; // 2..5
        case ScenarioKind::Sequential:   nObj = 2 + int(2 * u(rng)); break; // 2..3
        case ScenarioKind::Combined:     nObj = 3 + int(4 * u(rng)); break; // 3..6
    }

    for (int i = 0; i < nObj; ++i) {
        ObjectSpec o;
        o.id  = id * 100 + i;               // globally-unique target id
        double r = u(rng);
        o.cls = (r < 0.6) ? ObjectClass::UAV : (r < 0.85 ? ObjectClass::Bird : ObjectClass::Other);
        sampleClassParameters(o, rng);
        initState(o, rng);

        if (kind == ScenarioKind::Sequential) {
            // Objects appear one after another with staggered birth/death.
            o.birthTick = i * (s.numTicks / std::max(nObj, 1));
            o.deathTick = o.birthTick + s.numTicks / std::max(nObj, 1) + 20;
        } else if (kind == ScenarioKind::Combined) {
            // Mixed staggering: some overlap, some sequential.
            o.birthTick = int(0.4 * i * (s.numTicks / std::max(nObj, 1)) * u(rng));
            o.deathTick = s.numTicks;
        } else {
            o.birthTick = 0;
            o.deathTick = s.numTicks;
        }
        o.deathTick = std::min(o.deathTick, s.numTicks);
        s.objects.push_back(o);
    }
    return s;
}

// ---------------------------------------------------------------------------
//  CSV / JSON writers
// ---------------------------------------------------------------------------
void writeMeasurements(const std::string& path, const std::vector<Measurement>& rows) {
    std::ofstream f(path);
    f << "scenario_id,tick,time,truth_id,range_m,azimuth_deg,elevation_deg,"
         "radial_vel_mps,snr_db,clutter_db,completeness,micro_doppler,quality\n";
    f << std::fixed << std::setprecision(4);
    for (const auto& m : rows) {
        f << m.scenarioId << ',' << m.tick << ',' << m.time << ',' << m.truthId << ','
          << m.range << ',' << m.azimuthDeg << ',' << m.elevationDeg << ','
          << m.radialVel << ',' << m.snrDb << ',' << m.clutterDb << ','
          << m.completeness << ',' << m.microDoppler << ',' << m.quality << '\n';
    }
}

void writeTruth(const std::string& path, const std::vector<TruthRow>& rows) {
    std::ofstream f(path);
    f << "scenario_id,tick,time,truth_id,class,x,y,z,vx,vy,vz,exists\n";
    f << std::fixed << std::setprecision(4);
    for (const auto& t : rows) {
        f << t.scenarioId << ',' << t.tick << ',' << t.time << ',' << t.truthId << ','
          << t.cls << ',' << t.x << ',' << t.y << ',' << t.z << ','
          << t.vx << ',' << t.vy << ',' << t.vz << ',' << t.exists << '\n';
    }
}

void writeScenarioJson(const std::string& path, const std::vector<Scenario>& scenarios,
                       uint64_t seed, const std::string& createdBy) {
    std::ofstream f(path);
    f << std::fixed << std::setprecision(3);
    f << "{\n";
    f << "  \"generator\": \"RadarTwin-UAV\",\n";
    f << "  \"software_id\": \"S1\",\n";
    f << "  \"version\": \"1.0.0\",\n";
    f << "  \"created_by\": \"" << createdBy << "\",\n";
    f << "  \"random_seed\": " << seed << ",\n";
    f << "  \"sensor_dt_s\": " << kDt << ",\n";
    f << "  \"num_scenarios\": " << scenarios.size() << ",\n";
    f << "  \"scenarios\": [\n";
    for (size_t si = 0; si < scenarios.size(); ++si) {
        const Scenario& s = scenarios[si];
        f << "    {\n";
        f << "      \"id\": " << s.id << ",\n";
        f << "      \"kind\": \"" << scenarioKindToString(s.kind) << "\",\n";
        f << "      \"num_ticks\": " << s.numTicks << ",\n";
        f << "      \"objects\": [\n";
        for (size_t oi = 0; oi < s.objects.size(); ++oi) {
            const ObjectSpec& o = s.objects[oi];
            f << "        {\"id\": " << o.id
              << ", \"class\": \"" << classToString(o.cls) << "\""
              << ", \"maneuver\": \"" << maneuverToString(o.maneuver) << "\""
              << ", \"speed_mps\": " << o.speed
              << ", \"rcs_dbsm\": " << o.rcsDbsm
              << ", \"cruise_alt_m\": " << o.cruiseAlt
              << ", \"heading_deg\": " << o.headingDeg
              << ", \"birth_tick\": " << o.birthTick
              << ", \"death_tick\": " << o.deathTick << "}";
            f << (oi + 1 < s.objects.size() ? ",\n" : "\n");
        }
        f << "      ]\n";
        f << (si + 1 < scenarios.size() ? "    },\n" : "    }\n");
    }
    f << "  ]\n";
    f << "}\n";
}

// ---------------------------------------------------------------------------
//  Simulation driver
// ---------------------------------------------------------------------------
struct Corpus {
    std::vector<Measurement> measurements;
    std::vector<TruthRow>    truth;
    std::vector<Scenario>    scenarios;
};

Corpus simulate(uint64_t seed, int numScenarios) {
    Corpus corpus;
    std::mt19937_64 rng(seed);
    Detector detector(seed ^ 0x9E3779B97F4A7C15ull);

    for (int sIdx = 0; sIdx < numScenarios; ++sIdx) {
        ScenarioKind kind = static_cast<ScenarioKind>(sIdx % 4);
        Scenario s = buildScenario(sIdx, kind, rng);

        for (int tick = 0; tick < s.numTicks; ++tick) {
            for (auto& o : s.objects) {
                bool alive = (tick >= o.birthTick && tick < o.deathTick);
                if (tick > o.birthTick) advance(o, rng);   // advance only once born

                // Ground truth is logged whenever the object exists.
                if (alive) {
                    TruthRow tr;
                    tr.scenarioId = s.id; tr.tick = tick; tr.time = tick * kDt;
                    tr.truthId = o.id; tr.cls = static_cast<int>(o.cls);
                    tr.x = o.state.x; tr.y = o.state.y; tr.z = o.state.z;
                    tr.vx = o.state.vx; tr.vy = o.state.vy; tr.vz = o.state.vz;
                    tr.exists = 1;
                    corpus.truth.push_back(tr);

                    Measurement m;
                    if (detector.observe(o, s.id, tick, m))
                        corpus.measurements.push_back(m);
                }
            }
            detector.generateClutter(s.id, tick, corpus.measurements);
        }
        corpus.scenarios.push_back(s);
    }
    return corpus;
}

// Small self-check summary printed to stdout.
void printSummary(const Corpus& c, uint64_t seed) {
    long det = 0, fa = 0;
    for (const auto& m : c.measurements) (m.truthId >= 0 ? det : fa)++;
    double qsum = 0;
    for (const auto& m : c.measurements) qsum += m.quality;

    std::cout << "======================================================\n";
    std::cout << " RadarTwin-UAV (S1) - Synthetic Radar Corpus Generator\n";
    std::cout << "======================================================\n";
    std::cout << " random seed        : " << seed << "\n";
    std::cout << " scenarios          : " << c.scenarios.size() << "\n";
    std::cout << " ground-truth rows  : " << c.truth.size() << "\n";
    std::cout << " measurements       : " << c.measurements.size() << "\n";
    std::cout << "   - true detections: " << det << "\n";
    std::cout << "   - false alarms   : " << fa << "\n";
    if (!c.measurements.empty())
        std::cout << " mean quality index : "
                  << std::fixed << std::setprecision(3)
                  << (qsum / c.measurements.size()) << "\n";
    std::cout << "------------------------------------------------------\n";
    std::cout << " wrote: radartwin_measurements.csv\n";
    std::cout << " wrote: radartwin_truth.csv\n";
    std::cout << " wrote: radartwin_scenarios.json\n";
    std::cout << "======================================================\n";
}

} // namespace radartwin

int main(int argc, char** argv) {
    using namespace radartwin;
    uint64_t seed = 20260730ull;
    int numScenarios = 8;
    if (argc > 1) seed = std::strtoull(argv[1], nullptr, 10);
    if (argc > 2) numScenarios = std::max(1, std::atoi(argv[2]));

    Corpus corpus = simulate(seed, numScenarios);

    writeMeasurements("radartwin_measurements.csv", corpus.measurements);
    writeTruth("radartwin_truth.csv", corpus.truth);
    writeScenarioJson("radartwin_scenarios.json", corpus.scenarios, seed, "RadarTwin-UAV/1.0.0");

    printSummary(corpus, seed);
    return 0;
}
