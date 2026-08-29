"""Synthetic field-trial rehearsal corpus.

WHAT THIS IS NOT
----------------
Nothing produced here is a measurement. No number emitted by this module may be
copied into the manuscript's bracketed placeholders. The corpus exists for three
narrow purposes:

1. to exercise every stage of the pipeline end to end before any hardware is
   deployed, so that the first real campaign does not discover schema, clock, or
   packaging defects in the field;
2. to give the validation gates something to *fail*, since a validator that has
   only ever seen clean input is untested;
3. to make the worked numeric examples in the engineering report reproducible
   from a fixed seed.

The generator writes raw stream payloads in the shapes the four real sources
would deliver - JSON Lines for S1/S2/S3, a CSV index plus real media bytes for
S4 - so that the ingest adapters are exercised on realistic input rather than on
tables the pipeline itself constructed.

Injected defects
----------------
Each defect below mirrors a failure mode observed in operational multisource
collection, and each is what a specific validation metric is meant to catch:

* duplicate re-delivery of an upstream warning       -> exact duplicate rate
* re-encoded copies of the same media object         -> near-duplicate grouping
* mobile clocks with gross offsets                   -> Eq. (3) p95 and tolerance rate
* dropped sensor channels                            -> missingness by modality
* clipped, silent, and low-SNR audio                 -> audio quality flags
* blurred and badly exposed frames                   -> visual quality flags
* incidental speech in an audio object               -> privacy gate
* annotator disagreement near the detection limit    -> Krippendorff alpha
* observation reports that contradict ground truth   -> cross-modal consistency
"""

from __future__ import annotations

import json
import math
import struct
import wave
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from . import geometry, timebase as tb
from .config import Config

DAY_NS = 86_400 * tb.NS


# --------------------------------------------------------------------------- #
# Small real media writers (real bytes -> real checksums and quality metrics)
# --------------------------------------------------------------------------- #
def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    """Write mono 16-bit PCM. Values outside [-1, 1] clip, exactly as a recorder does."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(pcm.tobytes())


def write_png_gray(path: Path, img: np.ndarray) -> None:
    """Minimal 8-bit grayscale PNG encoder.

    Written by hand rather than pulled from an imaging library so that the
    release environment needs no image dependency to regenerate the rehearsal
    corpus, and so the produced bytes are byte-for-byte reproducible across
    library versions - which matters because the SHA-256 manifest is part of what
    is being tested.
    """
    a = np.clip(img, 0, 255).astype(np.uint8)
    h, w = a.shape
    raw = b"".join(b"\x00" + a[r].tobytes() for r in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


# --------------------------------------------------------------------------- #
# Trajectory synthesis
# --------------------------------------------------------------------------- #
@dataclass
class Track:
    t_s: np.ndarray
    xy: np.ndarray          # (n, 2) East-North metres
    z_m: np.ndarray
    platform_class: str
    approach_geometry: str
    speed_band: str


def _straight_in(rng, r0: float, speed: float, dur: float, rate: float) -> Tuple[np.ndarray, np.ndarray]:
    t = np.arange(0.0, dur, 1.0 / rate)
    bearing = rng.uniform(0, 2 * math.pi)
    start = np.array([r0 * math.cos(bearing), r0 * math.sin(bearing)])
    direction = -start / np.linalg.norm(start)
    jitter = rng.normal(0, 0.02, size=(t.size, 2)).cumsum(axis=0)
    return t, start + np.outer(t * speed, direction) + jitter


def _oblique(rng, r0, speed, dur, rate):
    t, xy = _straight_in(rng, r0, speed, dur, rate)
    angle = math.radians(rng.uniform(25, 55)) * rng.choice([-1, 1])
    rot = np.array([[math.cos(angle), -math.sin(angle)],
                    [math.sin(angle), math.cos(angle)]])
    return t, xy @ rot.T


def _orbit(rng, r0, speed, dur, rate):
    t = np.arange(0.0, dur, 1.0 / rate)
    omega = speed / max(r0, 1.0)
    phase = rng.uniform(0, 2 * math.pi)
    radius = r0 * (1.0 - 0.12 * t / max(dur, 1e-9))     # slow spiral inwards
    return t, np.stack([radius * np.cos(omega * t + phase),
                        radius * np.sin(omega * t + phase)], axis=1)


def _overflight(rng, r0, speed, dur, rate):
    t = np.arange(0.0, dur, 1.0 / rate)
    bearing = rng.uniform(0, 2 * math.pi)
    d = np.array([math.cos(bearing), math.sin(bearing)])
    perp = np.array([-d[1], d[0]]) * rng.uniform(-250, 250)
    start = -d * r0 + perp
    return t, start + np.outer(t * speed, d)


_GEOMETRY = {"straight_in": _straight_in, "oblique": _oblique,
             "orbit": _orbit, "overflight": _overflight}

_SPEED = {"slow": 8.0, "nominal": 15.0, "fast": 25.0}
_ALT = {"low": (30.0, 60.0), "medium": (60.0, 110.0), "high": (110.0, 180.0)}


def make_track(rng, platform: str, geom: str, speed_band: str, alt_band: str,
               rate: float, sigma_h: float, sigma_v: float) -> Track:
    speed = _SPEED[speed_band] * rng.uniform(0.9, 1.1)
    r0 = rng.uniform(900.0, 2600.0)
    dur = float(np.clip(r0 / speed * rng.uniform(0.8, 1.25), 25.0, 190.0))
    t, xy = _GEOMETRY[geom](rng, r0, speed, dur, rate)
    lo, hi = _ALT[alt_band]
    z = np.linspace(rng.uniform(lo, hi), rng.uniform(lo, hi), t.size)
    xy = xy + rng.normal(0.0, sigma_h, size=xy.shape)     # reference-system noise
    z = z + rng.normal(0.0, sigma_v, size=z.shape)
    return Track(t, xy, z, platform, geom, speed_band)


def make_negative_track(rng, kind: str, rate: float) -> Track:
    """Confounders that a naive detector mistakes for an approaching sUAV."""
    if kind == "bird":
        t = np.arange(0.0, rng.uniform(40, 90), 1.0 / rate)
        speed = rng.uniform(6, 14)
        heading = np.cumsum(rng.normal(0, 0.08, t.size))      # erratic turning
        step = speed / rate
        xy = np.stack([np.cumsum(step * np.cos(heading)),
                       np.cumsum(step * np.sin(heading))], axis=1)
        xy += np.array([rng.uniform(-1400, 1400), rng.uniform(-1400, 1400)])
        z = np.full(t.size, rng.uniform(20, 90))
    elif kind == "helicopter":
        t, xy = _overflight(rng, rng.uniform(2500, 4500), rng.uniform(45, 70),
                            rng.uniform(50, 90), rate)
        z = np.full(t.size, rng.uniform(250, 500))
    elif kind == "ground_vehicle":
        t = np.arange(0.0, rng.uniform(40, 80), 1.0 / rate)
        speed = rng.uniform(8, 20)
        base = np.array([rng.uniform(-2000, 2000), rng.uniform(-2000, 2000)])
        d = np.array([math.cos(rng.uniform(0, 6.28)), math.sin(rng.uniform(0, 6.28))])
        xy = base + np.outer(t * speed, d)
        z = np.zeros(t.size)
    else:  # wind, anthropogenic_noise - acoustic only, no coherent track
        t = np.arange(0.0, rng.uniform(30, 70), 1.0 / rate)
        xy = np.tile(np.array([rng.uniform(-2500, 2500),
                               rng.uniform(-2500, 2500)]), (t.size, 1))
        z = np.zeros(t.size)
    return Track(t, xy, z, "unknown", "none", "slow")


# --------------------------------------------------------------------------- #
# Corpus generator
# --------------------------------------------------------------------------- #
class RehearsalGenerator:
    """Generates the raw stream payloads for a rehearsal release."""

    def __init__(self, cfg: Config, out_dir: Path, seed: int = 20250411,
                 n_controlled: int = 90, n_observational: int = 40,
                 n_negative: int = 50):
        self.cfg = cfg
        self.out = Path(out_dir)
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.n_controlled = n_controlled
        self.n_observational = n_observational
        self.n_negative = n_negative
        self.zone = geometry.WarningZone.from_config(cfg)
        self.t0_ns = tb.rfc3339_to_ns("2025-04-01T00:00:00Z")
        self.sites = [f"SITE-{i:02d}" for i in range(1, 7)]
        self.site_group = {s: f"SG-{(i // 2) + 1}" for i, s in enumerate(self.sites)}
        # Monitoring sites sit on or just outside the zone boundary. Their
        # positions are controlled-tier information; only site_group and the
        # generalized cell ever reach the open tier. They matter here because
        # media quality is governed by the *sensor-to-target slant range*, not by
        # the target-to-boundary distance: an approach that is 2 km from the zone
        # can still be 80 m from a forward sensor, and conflating the two is the
        # commonest way an acoustic channel is written off as useless.
        poly = self.zone.polygon
        self.site_xy = {}
        for i, s in enumerate(self.sites):
            a = poly[i % len(poly)]
            b = poly[(i + 1) % len(poly)]
            f = self.rng.uniform(0.25, 0.75)
            edge = a + f * (b - a)
            outward = edge / (np.linalg.norm(edge) + 1e-9)
            self.site_xy[s] = edge + outward * self.rng.uniform(20.0, 180.0)
        self.contributors = [f"contrib-{i:03d}" for i in range(1, 41)]

    # -- helpers ----------------------------------------------------------- #
    def _cell(self, xy: np.ndarray) -> str:
        """Generalized spatial cell at the public resolution."""
        res = float(self.cfg.release["public_spatial_resolution_m"])
        e, n = np.floor(np.asarray(xy)[:2] / res).astype(int)
        return f"C{e:+04d}{n:+04d}"

    def _audio(self, snr_db: float, dur_s: float, sr: int, defect: str | None):
        n = int(dur_s * sr)
        t = np.arange(n) / sr
        noise = self.rng.normal(0, 1.0, n)
        # Rotor tonal complex: blade-pass fundamental plus harmonics.
        f0 = self.rng.uniform(90, 190)
        sig = sum((0.7 ** k) * np.sin(2 * math.pi * f0 * (k + 1) * t + self.rng.uniform(0, 6.3))
                  for k in range(4))
        # Normalize to unit RMS, not to unit peak. SNR is a ratio of *powers*, so
        # scaling by the peak makes the realized SNR differ from the requested one
        # by 10 log10 of the crest factor - about 6 dB for a four-harmonic complex.
        # With the peak normalization the corpus is systematically quieter than
        # its own metadata claims, and the predicted-versus-achieved comparison
        # measures that bookkeeping error instead of the sensor.
        sig /= np.sqrt(np.mean(sig ** 2)) + 1e-9
        amp = 10 ** (snr_db / 20.0)
        y = (amp * sig + noise) * 0.05
        if defect == "clipping":
            y *= 14.0
        elif defect == "silence":
            y *= 1e-4
        elif defect == "speech":                 # 3-4 formant-like band, 250 Hz mod
            y += 0.25 * np.sin(2 * math.pi * 300 * t) * (0.5 + 0.5 * np.sin(2 * math.pi * 4 * t))
        return y

    def _frame(self, target_px: float, defect: str | None) -> np.ndarray:
        h, w = 96, 128
        yy, xx = np.mgrid[0:h, 0:w]
        img = 150 + 12 * np.sin(xx / 9.0) + self.rng.normal(0, 5, (h, w))  # sky texture
        cx, cy = self.rng.uniform(20, w - 20), self.rng.uniform(15, h - 15)
        sigma = max(target_px, 0.6) / 2.0
        blob = 90 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2)))
        img = img - blob                                   # dark target against sky
        if defect == "blur":
            k = np.ones((5, 5)) / 25.0
            pad = np.pad(img, 2, mode="edge")
            img = sum(k[i, j] * pad[i:i + h, j:j + w]
                      for i in range(5) for j in range(5))
        elif defect == "over_exposure":
            img = img * 1.9 + 70
        elif defect == "under_exposure":
            img = img * 0.25
        return img

    # -- the four raw streams ---------------------------------------------- #
    def generate(self) -> Dict[str, Path]:
        cfg = self.cfg
        kin = cfg["kinematics"]
        rate = float(kin["groundtruth_rate_hz"])
        det = cfg["detectability"]
        fm = cfg["flight_matrix"]

        raw = self.out / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        s1: List[dict] = []
        ep: List[dict] = []
        mk: List[dict] = []
        s2: List[dict] = []
        s3: List[dict] = []
        s4: List[dict] = []
        tracks_dir = raw / "tracks"
        media_dir = raw / "media"

        specs = self._event_specs()
        for spec in specs:
            self._one_event(spec, rate, det, tracks_dir, media_dir, s1, s2, s3, s4, ep, mk)

        # Background public warnings unrelated to any event: real feeds carry
        # them, and a pipeline that assumes every warning matches an event will
        # over-associate.
        for i in range(35):
            ts = self.t0_ns + int(self.rng.uniform(0, 45) * DAY_NS)
            s2.append(self._warning_record(f"bg-{i:03d}", ts, None, "background"))

        paths = {
            "s1": raw / "s1_takeoff_events.jsonl",
            "s2": raw / "s2_public_warnings.jsonl",
            "s3": raw / "s3_mobile_reports.jsonl",
            "s4": raw / "s4_media_index.jsonl",
            "episodes": raw / "site_episode_log.jsonl",
            "markers": raw / "sync_markers.jsonl",
            "manifest": raw / "rehearsal_manifest.json",
        }
        for key, records in (("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4),
                             ("episodes", ep), ("markers", mk)):
            with open(paths[key], "w", encoding="utf-8") as fh:
                for r in records:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")

        paths["manifest"].write_text(json.dumps({
            "generator": "uavews.simulate.RehearsalGenerator",
            "provenance": "SYNTHETIC REHEARSAL CORPUS - NOT EMPIRICAL DATA",
            "seed": self.seed,
            "n_controlled": self.n_controlled,
            "n_observational": self.n_observational,
            "n_negative": self.n_negative,
            "counts": {"s1": len(s1), "s2": len(s2), "s3": len(s3),
                       "s4": len(s4), "episodes": len(ep), "markers": len(mk)},
        }, indent=2), encoding="utf-8")
        return paths

    def _event_specs(self) -> List[dict]:
        fm = self.cfg["flight_matrix"]
        rng = self.rng
        specs: List[dict] = []
        idx = 0
        for i in range(self.n_controlled):
            specs.append({
                "kind": "controlled_flight", "idx": idx,
                "campaign": f"CMP-{(i // 30) + 1}",
                "platform": str(rng.choice(fm["platform_class"])),
                "geom": str(rng.choice(fm["approach_geometry"])),
                "speed_band": str(rng.choice(fm["speed_band"])),
                "alt_band": str(rng.choice(fm["altitude_band"])),
                "illumination": str(rng.choice(fm["illumination"])),
                "background": str(rng.choice(fm["background"])),
            })
            idx += 1
        for i in range(self.n_observational):
            specs.append({
                "kind": "verified_observation" if i % 3 else "weak_observation",
                "idx": idx, "campaign": "OBS-1",
                "platform": str(rng.choice(fm["platform_class"])),
                "geom": str(rng.choice(fm["approach_geometry"])),
                "speed_band": str(rng.choice(fm["speed_band"])),
                "alt_band": str(rng.choice(fm["altitude_band"])),
                "illumination": str(rng.choice(fm["illumination"])),
                "background": str(rng.choice(fm["background"])),
            })
            idx += 1
        negatives = ["bird", "helicopter", "ground_vehicle", "wind", "anthropogenic_noise"]
        for i in range(self.n_negative):
            specs.append({
                "kind": "negative_control", "idx": idx, "campaign": "NEG-1",
                "negative_type": negatives[i % len(negatives)],
                "illumination": str(rng.choice(fm["illumination"])),
                "background": str(rng.choice(fm["background"])),
            })
            idx += 1
        return specs

    def _one_event(self, spec, rate, det, tracks_dir, media_dir,
                   s1, s2, s3, s4, ep, mk) -> None:
        rng = self.rng
        cfg = self.cfg
        kin = cfg["kinematics"]
        native = f"RUN-{spec['idx']:04d}"
        site = str(rng.choice(self.sites))
        day = int(rng.uniform(0, 45))
        anchor = self.t0_ns + day * DAY_NS + int(rng.uniform(0, 86_400) * tb.NS)

        if spec["kind"] == "negative_control":
            track = make_negative_track(rng, spec["negative_type"], rate)
            platform = "unknown"
        else:
            track = make_track(rng, spec["platform"], spec["geom"],
                               spec["speed_band"], spec["alt_band"], rate,
                               float(kin["groundtruth_sigma_h_m"]),
                               float(kin["groundtruth_sigma_v_m"]))
            platform = spec["platform"]

        # The recording site is the one the track actually came closest to, not
        # an arbitrary one: a site only produces an object for a target that
        # entered its envelope. This has to be resolved before any record is
        # emitted - the takeoff log, the episode log, the markers, and the media
        # index must all name the same site, or the clock offsets measured at one
        # site get attributed to a source profile belonging to another.
        best = None
        for cand in self.sites:
            sl = np.sqrt(((track.xy - self.site_xy[cand]) ** 2).sum(axis=1)
                         + track.z_m ** 2)
            if best is None or sl.min() < best[1].min():
                best = (cand, sl)
        site, slant = best
        site_xy = self.site_xy[site]

        d = self.zone.boundary_distance(track.xy)
        sd = self.zone.signed_boundary_distance(track.xy)
        t_cross = geometry.crossing_time(track.t_s, sd)

        # Ground-truth track: controlled tier only, written for the S1 adapter.
        tp = tracks_dir / f"{native}.csv"
        tp.parent.mkdir(parents=True, exist_ok=True)
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write("t_s,east_m,north_m,alt_m,d_boundary_m,signed_d_m\n")
            for k in range(track.t_s.size):
                fh.write(f"{track.t_s[k]:.3f},{track.xy[k,0]:.3f},{track.xy[k,1]:.3f},"
                         f"{track.z_m[k]:.3f},{d[k]:.3f},{sd[k]:.3f}\n")

        t_start = anchor
        t_end = anchor + tb.seconds_to_ns(float(track.t_s[-1]))

        # ---- S1: takeoff indication (controlled flights only) ------------- #
        if spec["kind"] == "controlled_flight":
            lead = rng.uniform(4.0, 25.0)
            s1.append({
                "native_run_id": native,
                "campaign_id": spec["campaign"],
                "site_code": site,
                "site_group": self.site_group[site],
                "takeoff_time": tb.ns_to_rfc3339(t_start - tb.seconds_to_ns(lead)),
                "track_start_time": tb.ns_to_rfc3339(t_start),
                "track_end_time": tb.ns_to_rfc3339(t_end),
                "track_csv": f"tracks/{native}.csv",
                "platform_class": platform,
                "approach_geometry": spec["geom"],
                "speed_band": spec["speed_band"],
                "altitude_band": spec["alt_band"],
                "illumination": spec["illumination"],
                "background": spec["background"],
                "groundtruth_rate_hz": rate,
                "sigma_h_m": kin["groundtruth_sigma_h_m"],
                "sigma_v_m": kin["groundtruth_sigma_v_m"],
                "clock_method": "gnss_pps",
                "clock_sigma_ms": 2.0,
                "crossing_time_s": None if t_cross is None else round(t_cross, 3),
            })

        # ---- Site episode log: the anchor for events S1 never sees --------- #
        # An observational or negative-control event has no takeoff indication.
        # The authorized monitoring site's own episode log is the first record of
        # it, and it is what makes such an event addressable at all. The log
        # carries no trajectory, so the kinematic targets of Equations (1) and
        # (2) are simply unavailable for these events - which is exactly why
        # their labels sit in a weaker evidence tier.
        if spec["kind"] != "controlled_flight":
            ep.append({
                "native_run_id": native,
                "episode_kind": spec["kind"],
                "site_code": site,
                "site_group": self.site_group[site],
                "episode_start": tb.ns_to_rfc3339(t_start),
                "episode_end": tb.ns_to_rfc3339(t_end),
                "negative_type": spec.get("negative_type"),
                "illumination": spec["illumination"],
                "background": spec["background"],
                "clock_method": "ntp",
                "clock_sigma_ms": 40.0,
                "verified_by_operator": spec["kind"] == "verified_observation",
            })

        # ---- S2: public warning, sometimes duplicated by the feed --------- #
        if spec["kind"] != "negative_control" and rng.random() < 0.55:
            issued = t_start + int(rng.normal(0, 20) * tb.NS)
            rec = self._warning_record(f"w-{spec['idx']:04d}", issued, native, "alert")
            s2.append(rec)
            if rng.random() < 0.12:          # duplicate re-delivery
                dup = dict(rec)
                dup["retrieved_at"] = tb.ns_to_rfc3339(
                    tb.rfc3339_to_ns(rec["retrieved_at"]) + 90 * tb.NS)
                s2.append(dup)

        # ---- S3: mobile reports ------------------------------------------- #
        base_rate = {"controlled_flight": 2.2, "verified_observation": 3.0,
                     "weak_observation": 3.4, "negative_control": 1.1}[spec["kind"]]
        n_reports = int(rng.poisson(base_rate))
        for j in range(n_reports):
            contributor = str(rng.choice(self.contributors))
            frac = rng.uniform(0.15, 0.95)
            t_obs = t_start + int(frac * (t_end - t_start))
            k = min(int(frac * track.t_s.size), track.t_s.size - 1)
            dist = float(d[k])
            # Perceived direction degrades with distance and is absent for
            # non-kinematic negatives.
            if spec["kind"] == "negative_control" and \
                    spec["negative_type"] in ("wind", "anthropogenic_noise"):
                perceived = None
            else:
                truth = geometry.direction_labels(
                    track.t_s, d, cfg.delta_t_s, cfg.epsilon_m)[k]
                p_wrong = float(np.clip(0.10 + dist / 6000.0, 0.10, 0.55))
                if rng.random() < p_wrong:
                    perceived = str(rng.choice(
                        ["approaching", "receding", "lateral_stationary", "uncertain"]))
                else:
                    perceived = str(truth)
            # Mobile clocks: mostly near-correct, occasionally grossly wrong.
            skew_s = rng.normal(0, 1.2)
            if rng.random() < 0.06:
                skew_s += rng.choice([-1, 1]) * rng.uniform(3.0, 25.0)
            s3.append({
                "report_uid": f"{native}-r{j}",
                "contributor_key": contributor,
                "device_profile": str(rng.choice(
                    ["phone_a", "phone_b", "phone_c", "tablet_a"])),
                "reported_at": tb.ns_to_rfc3339(t_obs + tb.seconds_to_ns(skew_s)),
                "received_at": tb.ns_to_rfc3339(
                    t_obs + tb.seconds_to_ns(skew_s + rng.uniform(2.0, 40.0))),
                "device_clock_skew_s": round(float(skew_s), 3),
                "observation_start": tb.ns_to_rfc3339(t_obs - 3 * tb.NS),
                "observation_end": tb.ns_to_rfc3339(t_obs + 3 * tb.NS),
                "coarse_east_m": float(track.xy[k, 0] + rng.normal(0, 400)),
                "coarse_north_m": float(track.xy[k, 1] + rng.normal(0, 400)),
                "perceived_direction": perceived,
                "self_confidence": round(float(np.clip(rng.beta(5, 2), 0, 1)), 3),
                "free_text": "seen from the road" if rng.random() < 0.3 else "",
                "consent_receipt": "v1.2",
                "linked_run_hint": native if rng.random() < 0.8 else None,
            })

        # ---- S4: audio and visual objects at authorized sites -------------- #
        # Capture is triggered, not continuous: the site starts recording when the
        # target enters its own envelope, so objects cluster around the point of
        # closest approach to the *sensor*. Sampling uniformly along the track
        # instead would put almost every object beyond any plausible acoustic
        # range and produce a corpus in which the audio channel is trivially
        # useless - an artefact of the sampling, not of the physics.
        ac, vi = det["acoustic"], det["visual"]
        f_px = vi["sensor_width_px"] / (2 * math.tan(math.radians(vi["horizontal_fov_deg"]) / 2))
        env = {"day": "rural_day", "dusk": "periurban", "night": "rural_night"}[
            spec["illumination"]]
        src_db = ac["source_level_db_at_ref"].get(platform, 70.0)
        span = vi["target_span_m"].get(platform, 0.6)

        k_cpa = int(np.argmin(slant))

        # ---- Synchronization markers -------------------------------------- #
        # Every run opens with a marker: one physical instant observed
        # simultaneously by the disciplined sources. It is the only construct
        # that makes Equation (3) measurable, because delta t is the deviation of
        # two clocks reading the *same* instant. Comparing an observation
        # timestamp with an event anchor instead measures where in the event the
        # observation fell, which is not a clock error at all.
        #
        # Mobile and external public sources cannot observe the marker. Their
        # residual offset is therefore not measurable, and the release reports
        # their declared uncertainty rather than inventing an error for them.
        marker_true = t_start
        for src_key, method in ((f"controlled-area::{site}", "gnss_pps"),
                                (f"site::{site}", "ptp" if rng.random() < 0.7 else "ntp")):
            if spec["kind"] != "controlled_flight" and src_key.startswith("controlled-area"):
                continue
            sigma_ms = {"gnss_pps": 2.0, "ptp": 5.0, "ntp": 40.0}[method]
            err_s = rng.normal(0.0, sigma_ms / 1000.0)
            if method == "ntp" and rng.random() < 0.05:
                err_s += rng.choice([-1, 1]) * rng.uniform(0.15, 0.8)   # NTP step
            mk.append({
                "native_run_id": native,
                "source_key": src_key,
                "sync_method": method,
                "true_marker_utc": tb.ns_to_rfc3339(marker_true, digits=6),
                "observed_marker_utc": tb.ns_to_rfc3339(
                    marker_true + tb.seconds_to_ns(err_s), digits=6),
                "declared_sigma_ms": sigma_ms,
            })

        n_media = int(rng.integers(1, 4))
        for j in range(n_media):
            # Offset from the closest-approach index, so the corpus spans the
            # detection threshold in both directions rather than sitting on it.
            off = int(rng.normal(0, 0.06 * track.t_s.size))
            k = int(np.clip(k_cpa + off, 0, track.t_s.size - 1))
            r_slant = float(max(slant[k], 5.0))
            frac = k / max(track.t_s.size - 1, 1)
            t_obj = t_start + tb.seconds_to_ns(float(track.t_s[k]))
            kind = "audio" if rng.random() < 0.55 else \
                   ("image" if rng.random() < 0.7 else "video")
            sr = 16000
            snr = float(src_db - 20 * math.log10(r_slant) -
                        ac["atmospheric_absorption_db_per_m"] * r_slant -
                        ac["ambient_noise_db"][env])
            if spec["kind"] == "negative_control":
                # Confounders are not silent - a helicopter is louder than any
                # sUAV - but their spectra do not match the rotor tonal model,
                # so the in-band SNR the detector sees is degraded.
                snr -= rng.uniform(2.0, 10.0)
            target_px = f_px * span / r_slant

            defect = None
            r = rng.random()
            if kind == "audio":
                if r < 0.05: defect = "clipping"
                elif r < 0.09: defect = "silence"
                elif r < 0.13: defect = "speech"
            else:
                if r < 0.07: defect = "blur"
                elif r < 0.11: defect = "over_exposure"
                elif r < 0.14: defect = "under_exposure"

            if rng.random() < 0.04:          # dropped channel: metadata, no payload
                s4.append(self._media_record(native, site, j, kind, t_obj, r_slant,
                                             snr, target_px, None, None, 0,
                                             "sensor_unavailable", spec))
                continue

            rel = f"media/{native}-m{j}." + ("wav" if kind == "audio" else "png")
            path = media_dir.parent / rel
            if kind == "audio":
                dur = float(rng.uniform(1.5, 3.0))
                payload = self._audio(snr, dur, sr, defect)
                write_wav(path, payload, sr)
            else:
                dur = None
                payload = self._frame(target_px, defect)
                write_png_gray(path, payload)
            size = path.stat().st_size
            s4.append(self._media_record(native, site, j, kind, t_obj, r_slant, snr,
                                         target_px, rel, dur, size, None, spec,
                                         defect))

            # Near-duplicate: a re-encoded copy of *the same* recording. It has to
            # be derived from the same samples, not generated afresh with the same
            # parameters - two independent realizations of one acquisition setting
            # are different content, and a duplicate detector that grouped them
            # would be grouping on metadata rather than on what was recorded. The
            # perturbations below are what re-encoding actually does: a small gain
            # change and requantization.
            if rng.random() < 0.07 and rel:
                rel2 = rel.replace(".", "-copy.")
                path2 = media_dir.parent / rel2
                if kind == "audio":
                    y2 = payload * rng.uniform(0.92, 1.08)
                    y2 = np.round(y2 * 2048.0) / 2048.0     # coarser requantization
                    write_wav(path2, y2, sr)
                else:
                    img2 = payload * rng.uniform(0.97, 1.03) + rng.uniform(-2.0, 2.0)
                    write_png_gray(path2, np.round(img2))
                s4.append(self._media_record(
                    native, site, j, kind, t_obj + 2 * tb.NS, r_slant, snr, target_px,
                    rel2, dur, path2.stat().st_size, None, spec, defect,
                    duplicate_of=rel))

    def _warning_record(self, uid: str, issued_ns: int, native: str | None,
                        category: str) -> dict:
        lag = self.rng.uniform(5, 240)
        return {
            "source_alert_id": uid,
            "sender": "public-warning-feed",
            "status": "actual",
            "msg_type": "alert",
            "scope": "public",
            "category": category,
            "issued_at": tb.ns_to_rfc3339(issued_ns),
            "retrieved_at": tb.ns_to_rfc3339(issued_ns + tb.seconds_to_ns(lag)),
            "area_generalized": f"AREA-{int(self.rng.integers(1, 5))}",
            "language": "uk",
            "headline_normalized": "air alert notification",
            "linked_run_hint": native,
        }

    def _media_record(self, native, site, j, kind, t_obj_ns, dist, snr, target_px,
                      rel, dur, size, missing, spec, defect=None,
                      duplicate_of=None) -> dict:
        rng = self.rng
        skew_s = rng.normal(0, 0.02) if rng.random() > 0.05 else rng.normal(0, 0.6)
        return {
            "object_key": f"{native}-m{j}" + ("-copy" if duplicate_of else ""),
            "native_run_id": native,
            "site_code": site,
            "site_group": self.site_group[site],
            "media_type": kind,
            "object_start": tb.ns_to_rfc3339(t_obj_ns + tb.seconds_to_ns(skew_s)),
            "object_end": tb.ns_to_rfc3339(
                t_obj_ns + tb.seconds_to_ns(skew_s + (dur if dur else 0.04))),
            "clock_method": "ptp" if rng.random() < 0.7 else "ntp",
            "relative_path": rel,
            "size_bytes": size,
            "true_slant_range_m": round(dist, 2),
            "planned_snr_db": round(snr, 2),
            "planned_target_px": round(float(target_px), 3),
            "duration_s": dur,
            "sample_rate_hz": 16000 if kind == "audio" else None,
            "width_px": None if kind == "audio" else 128,
            "height_px": None if kind == "audio" else 96,
            "frame_rate_hz": 25.0 if kind == "video" else None,
            "calibration_version": "cal-2025.03",
            "injected_defect": defect,
            "missing_reason": missing,
            "duplicate_of": duplicate_of,
            "illumination": spec.get("illumination"),
            "background": spec.get("background"),
        }


def generate(cfg: Config, out_dir: Path, seed: int = 20250411, **kwargs) -> Dict[str, Path]:
    return RehearsalGenerator(cfg, out_dir, seed=seed, **kwargs).generate()


# --------------------------------------------------------------------------- #
# Annotator simulation
# --------------------------------------------------------------------------- #
def simulate_annotations(events, windows, media, kinematics, cfg, salt,
                         seed: int = 991) -> "object":
    """Independent annotator judgements for the rehearsal corpus.

    SYNTHETIC. The point is not to imitate human annotators faithfully - it is to
    produce a disagreement structure with the property that makes agreement
    statistics worth computing at all: error that depends on how good the evidence
    was. An annotator here is right with probability

        p_correct = p_floor + (p_ceiling - p_floor) * sigmoid(quality)

    where ``quality`` combines the measured target extent of the visual objects
    attached to the event and the measured SNR of its audio objects. Events near
    the detection limit therefore generate genuine disagreement, and events with
    clean evidence do not - which is exactly the pattern that makes a single
    pooled alpha misleading and the per-stratum breakdown informative.
    """
    import pandas as pd
    from . import labeling

    rng = np.random.default_rng(seed)
    n_ann = int(cfg["annotation"]["n_annotators"])
    annotators = [f"ann-{i:02d}" for i in range(n_ann + 2)]

    if media is None or len(media) == 0:
        quality = {}
    else:
        m = media.copy()
        vis = m[m["media_type"] != "audio"].groupby("event_id")["target_px"].max()
        aud = m[m["media_type"] == "audio"].groupby("event_id")["snr_db"].max()
        quality = {}
        for eid in set(vis.index) | set(aud.index):
            v = float(vis.get(eid, 0.0) or 0.0)
            a = float(aud.get(eid, -60.0) or -60.0)
            # Normalize each channel to roughly [-3, 3] around its usable limit.
            quality[eid] = max((v - 3.0) / 6.0, (a + 16.0) / 8.0)

    ev = events.set_index("event_id")
    win_by_event = {eid: g for eid, g in windows.groupby("event_id")}
    rows = []

    for eid, e in ev.iterrows():
        q = quality.get(eid, -1.0)
        p_correct = 0.45 + 0.53 / (1.0 + math.exp(-1.4 * q))
        raters = list(rng.choice(annotators, size=n_ann, replace=False))
        support = (int(e["t_start_utc_ns"]), int(e["t_end_utc_ns"]))

        truth_presence = "absent" if e["event_kind"] == "negative_control" else "present"
        for r in raters:
            if rng.random() < p_correct:
                value = truth_presence
            else:
                value = str(rng.choice([v for v in ("present", "absent", "uncertain")
                                        if v != truth_presence]))
            conf = float(np.clip(rng.beta(2 + 6 * p_correct, 2), 0.05, 0.99))
            rows.append(labeling._row(
                salt, "event", eid, eid, "vehicle_presence", value,
                "expert_verified", r, conf, "rubric_v1",
                (support[0] + int(rng.normal(0, 0.4) * tb.NS), support[1]),
                final=False))

        kin = kinematics.get(eid)
        if kin is None:
            continue
        t0 = int(kin["t_start_ns"])
        wins = win_by_event.get(eid)
        if wins is None:
            continue
        for _, w in wins.iterrows():
            if w["window_role"] != "event" or rng.random() > 0.35:
                continue
            a = (int(w["w_start_utc_ns"]) - t0) / tb.NS
            b = (int(w["w_end_utc_ns"]) - t0) / tb.NS
            mask = (kin["t_s"] >= a) & (kin["t_s"] <= b)
            if mask.sum() < 2:
                continue
            vals, counts = np.unique(kin["direction"][mask].astype(str),
                                     return_counts=True)
            truth = str(vals[int(np.argmax(counts))])
            for r in raters[:2]:
                if rng.random() < p_correct:
                    value = truth
                else:
                    value = str(rng.choice(["approaching", "receding",
                                            "lateral_stationary", "uncertain"]))
                rows.append(labeling._row(
                    salt, "segment", w["window_id"], eid, "movement_direction",
                    value, "expert_verified", r,
                    float(np.clip(rng.beta(2 + 5 * p_correct, 2), 0.05, 0.99)),
                    "rubric_v1",
                    (int(w["w_start_utc_ns"]) + int(rng.normal(0, 0.5) * tb.NS),
                     int(w["w_end_utc_ns"])),
                    final=False))
    return pd.DataFrame(rows)
