"""Measured media quality.

Every value in this module is computed from the released byte sequence, never
declared by the generator or copied from an acquisition plan. That distinction
matters: the manuscript's Table 7 asks for *observed* audio and visual quality,
and a manifest that echoes the intended SNR instead of the achieved one would
pass its own validation while telling the user nothing.
"""

from __future__ import annotations

import math
import struct
import wave
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import numpy as np


# --------------------------------------------------------------------------- #
# Decoders
# --------------------------------------------------------------------------- #
def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as fh:
        sr = fh.getframerate()
        n = fh.getnframes()
        raw = fh.readframes(n)
        width = fh.getsampwidth()
        channels = fh.getnchannels()
    if width != 2:
        raise ValueError(f"expected 16-bit PCM, got {width * 8}-bit")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return x, sr


def read_png_gray(path: Path) -> np.ndarray:
    """Decode the 8-bit grayscale PNGs written by :mod:`uavews.simulate`.

    Supports the five standard scanline filters so that a re-encoded object from
    another tool still decodes; anything beyond 8-bit grayscale is rejected
    rather than silently misread.
    """
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, w = 8, b"", None
    h = bit_depth = color = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            w, h, bit_depth, color = struct.unpack(">IIBB", payload[:10])
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
        pos += 12 + length
    if bit_depth != 8 or color != 0:
        raise ValueError(f"unsupported PNG: depth={bit_depth} color={color}")
    raw = zlib.decompress(idat)
    out = np.zeros((h, w), dtype=np.uint8)
    prev = np.zeros(w, dtype=np.int32)
    i = 0
    for r in range(h):
        ftype = raw[i]; i += 1
        line = np.frombuffer(raw[i:i + w], dtype=np.uint8).astype(np.int32); i += w
        if ftype == 0:
            cur = line
        elif ftype == 1:
            cur = line.copy()
            for c in range(1, w):
                cur[c] = (cur[c] + cur[c - 1]) & 0xFF
        elif ftype == 2:
            cur = (line + prev) & 0xFF
        elif ftype == 3:
            cur = line.copy()
            for c in range(w):
                left = cur[c - 1] if c else 0
                cur[c] = (cur[c] + ((left + prev[c]) >> 1)) & 0xFF
        elif ftype == 4:
            cur = line.copy()
            for c in range(w):
                a = cur[c - 1] if c else 0
                b = prev[c]
                cc = prev[c - 1] if c else 0
                p = a + b - cc
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - cc)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else cc)
                cur[c] = (cur[c] + pred) & 0xFF
        else:
            raise ValueError(f"unknown PNG filter {ftype}")
        out[r] = cur.astype(np.uint8)
        prev = cur.astype(np.int32)
    return out


# --------------------------------------------------------------------------- #
# Audio metrics
# --------------------------------------------------------------------------- #
def _rolling_max(a: np.ndarray, size: int = 5) -> np.ndarray:
    """Maximum over a centred window, so a harmonic landing between bins is caught."""
    half = size // 2
    pad = np.pad(a, half, mode="edge")
    out = pad[: a.size].copy()
    for k in range(1, size):
        out = np.maximum(out, pad[k: k + a.size])
    return out


def _harmonic_statistic(p: np.ndarray, idx: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Harmonic-sum statistic S(f0) for every candidate f0, vectorized."""
    pmax = _rolling_max(p)
    return np.where(valid, pmax[idx], 0.0).sum(axis=1)


@lru_cache(maxsize=64)
def _null_quantile(n_bins: int, n_cand: int, n_harm: int, seed: int = 11,
                   n_trials: int = 300, alpha: float = 0.01) -> float:
    """Monte-Carlo null for the harmonic-sum statistic, in units of the noise floor.

    The analytic bound one would write down - the maximum of N exponential bins
    exceeds the median by about ln(N)/ln(2) - is not the right null here, and
    using it silently reports pure noise as a weak detection. Two maximizations
    sit inside the statistic that the analytic form ignores: the search over
    candidate fundamentals, and the local maximum taken in a window around each
    harmonic. Both inflate the statistic under the null, and both depend on the
    grid size, so the correction is not a constant.

    The null is therefore calibrated by simulation against the correct noise
    model - the periodogram bins of Gaussian noise are exponentially distributed -
    using the identical statistic, the identical candidate grid, and the identical
    windowing. The result is cached per (n_bins, n_cand, n_harm), which is all the
    statistic depends on, so the cost is paid once per distinct clip geometry.
    """
    rng = np.random.default_rng(seed)
    # The candidate grid used in calibration mirrors the real one: harmonics of
    # each candidate, clipped to the band.
    base = np.arange(1, n_cand + 1, dtype=np.float64)
    harm = np.arange(1, n_harm + 1, dtype=np.float64)
    idx = np.rint(np.outer(base, harm)).astype(int)
    valid = idx < n_bins
    idx = np.clip(idx, 0, n_bins - 1)

    peaks = np.empty(n_trials)
    for t in range(n_trials):
        p = rng.exponential(1.0, n_bins)
        floor = float(np.median(p)) + 1e-20
        peaks[t] = _harmonic_statistic(p, idx, valid).max() / floor
    return float(np.quantile(peaks, 1.0 - alpha))


def _harmonic_sum_snr(p: np.ndarray, f: np.ndarray, n_harmonics: int = 5,
                      f0_range=(60.0, 260.0)):
    """Broadband in-band SNR recovered through a harmonic-sum estimator.

    A rotor radiates a blade-pass fundamental with harmonics, so nearly all of
    its power sits in a handful of narrow bins while the noise is spread over all
    of them. Comparing the single largest bin with the noise floor - the obvious
    estimate - measures the wrong quantity: it is a peak-to-floor ratio, which
    for a concentrated tonal runs tens of decibels above the broadband SNR the
    propagation model predicts, so measurement and prediction cannot be compared.

    This estimator instead isolates the total signal power from the H harmonic
    bins and refers it to the noise power over the whole band:

        f0_hat  = argmax over the search range of  S(f0) = sum_h max p[h*f0 +- 2]
        P_sig   = S(f0_hat) - H * floor
        SNR_dB  = 10 log10( P_sig / (floor * N) )

    which is the same quantity as ``L(r) - L_ambient`` in
    :mod:`uavews.trialdesign`, and is therefore directly comparable with it.

    Concentrating the estimate in H bins rather than N is where the sensitivity
    comes from, and it is also what bounds it: a detection is declared only when
    S exceeds the Monte-Carlo null of :func:`_null_quantile`, which accounts for
    the search over candidates. Below that the estimator is saturated, and the
    release reports null with a flag rather than a number that looks like a weak
    detection and is not one.
    """
    n_bins = int(p.size)
    if n_bins < 32:
        return None, None, None, 1.0
    floor = float(np.median(p)) + 1e-20
    df = float(f[1] - f[0])
    lo = max(1, int(round((f0_range[0] - f[0]) / df)))
    hi = min(n_bins - 1, int(round((f0_range[1] - f[0]) / df)))
    if hi - lo < 4:
        return None, None, None, floor

    cand = np.arange(lo, hi + 1, dtype=np.float64)
    harm = np.arange(1, n_harmonics + 1, dtype=np.float64)
    idx = np.rint(np.outer(cand, harm)).astype(int)
    valid = idx < n_bins
    idx = np.clip(idx, 0, n_bins - 1)

    S = _harmonic_statistic(p, idx, valid)
    k = int(np.argmax(S))
    s_best = float(S[k])
    h_used = int(valid[k].sum())
    f0 = float(f[0] + cand[k] * df)

    null_ratio = _null_quantile(n_bins, int(hi - lo + 1), n_harmonics)
    # Express the detection bound as an SNR so it can be plotted on the same axis
    # as the measurement: the smallest P_sig that clears the null, referred to the
    # total in-band noise power.
    p_sig_min = max(null_ratio - h_used, 1e-12) * floor
    snr_min_db = 10.0 * math.log10(p_sig_min / (floor * n_bins))

    p_sig = s_best - h_used * floor
    if p_sig <= 0 or s_best / floor <= null_ratio:
        return None, snr_min_db, f0, floor
    return 10.0 * math.log10(p_sig / (floor * n_bins)), snr_min_db, f0, floor


def audio_metrics(path: Path, speech_band=(200.0, 900.0),
                  clip_threshold: float = 0.995,
                  low_snr_db: float = -16.0) -> Dict[str, object]:
    """Clipping, level, SNR, and a speech screen, measured from the samples.

    The SNR is the broadband in-band figure defined by :func:`_harmonic_sum_snr`,
    so it can be compared directly against the propagation model that sized the
    sensor placement. When the estimator cannot separate a tonal from noise it
    returns null and sets ``snr_not_measurable`` - a saturated estimate reported
    as a small positive SNR would look like a weak detection and is not one.
    """
    x, sr = read_wav(path)
    n = x.size
    if n == 0:
        return {"error": "empty", "quality_flags": ["corruption"]}

    clip_frac = float(np.mean(np.abs(x) >= clip_threshold))
    rms = float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))

    win = np.hanning(n)
    spec = np.abs(np.fft.rfft(x * win)) ** 2
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    band = (freqs >= 50.0) & (freqs <= 4000.0)
    if band.sum() < 8:
        return {"error": "too_short", "quality_flags": ["corruption"]}
    p, f = spec[band], freqs[band]

    snr_db, snr_min_db, f0, floor = _harmonic_sum_snr(p, f)
    measurable = snr_db is not None

    sb = (f >= speech_band[0]) & (f <= speech_band[1])
    speech_ratio = float(np.sum(p[sb]) / (np.sum(p) + 1e-20))

    flags: List[str] = []
    if clip_frac > 0.001:
        flags.append("clipping")
    if rms < 1e-3:
        flags.append("silence")
    if not measurable:
        flags.append("snr_not_measurable")
    elif snr_db < low_snr_db:
        # The threshold is an input SNR: the detector's post-gain requirement
        # less its processing gain. Flagging at the post-gain figure would mark
        # every usable recording as low-SNR, because the front end is designed to
        # work below the broadband noise floor.
        flags.append("low_snr")
    if speech_ratio > 0.35 and rms > 1e-3:
        flags.append("speech_detected")

    return {
        "duration_s": n / sr, "sample_rate_hz": sr, "channels": 1, "bit_depth": 16,
        "clip_fraction": clip_frac, "rms": rms, "peak": peak,
        "snr_db": snr_db if measurable else None,
        "snr_raw_db": snr_db,
        "snr_estimator_floor_db": snr_min_db,
        "snr_measurable": measurable,
        "dominant_hz": f0,
        "speech_band_ratio": speech_ratio, "quality_flags": flags,
    }


# --------------------------------------------------------------------------- #
# Visual metrics
# --------------------------------------------------------------------------- #
_LAPLACIAN = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]])


def _convolve3(img: np.ndarray, k: np.ndarray) -> np.ndarray:
    pad = np.pad(img, 1, mode="edge")
    out = np.zeros_like(img, dtype=np.float64)
    for i in range(3):
        for j in range(3):
            out += k[i, j] * pad[i:i + img.shape[0], j:j + img.shape[1]]
    return out


def visual_metrics(path: Path) -> Dict[str, object]:
    """Blur, exposure, and apparent target extent, measured from the pixels.

    Sharpness is the variance of the Laplacian response, the standard
    no-reference focus measure: a blurred frame has little high-frequency energy
    and therefore a small Laplacian variance. Apparent target extent is measured
    as the full width at half depth of the darkest blob against the sky, which is
    what the detection-range calculation in :mod:`uavews.trialdesign` predicts and
    is therefore the quantity that lets prediction and observation be compared.
    """
    img = read_png_gray(path).astype(np.float64)
    lap = _convolve3(img, _LAPLACIAN)
    sharpness = float(np.var(lap))
    mean, std = float(img.mean()), float(img.std())
    over = float(np.mean(img >= 250.0))
    under = float(np.mean(img <= 8.0))

    background = float(np.median(img))
    depth = background - float(img.min())
    if depth > 6.0:
        mask = img <= (background - depth / 2.0)
        ys, xs = np.nonzero(mask)
        target_px = float(max(xs.max() - xs.min(), ys.max() - ys.min()) + 1) \
            if xs.size else 0.0
        contrast = depth / (std + 1e-9)
    else:
        target_px, contrast = 0.0, 0.0

    flags: List[str] = []
    if sharpness < 12.0:
        flags.append("blur")
    if over > 0.15 or mean > 225.0:
        flags.append("over_exposure")
    if under > 0.15 or mean < 45.0:
        flags.append("under_exposure")
    return {
        "width_px": img.shape[1], "height_px": img.shape[0],
        "blur_score": sharpness, "mean_level": mean, "std_level": std,
        "over_exposed_fraction": over, "under_exposed_fraction": under,
        "target_px": target_px, "target_contrast": contrast,
        "quality_flags": flags,
    }


def _dct2(block: np.ndarray) -> np.ndarray:
    """Type-II DCT along both axes, built from the orthonormal basis.

    Written out rather than taken from SciPy so the release environment stays at
    numpy; the blocks are 32x32, so the O(n^3) matrix form costs nothing.
    """
    n = block.shape[0]
    k = np.arange(n)
    basis = np.cos(np.pi * (2 * k[:, None] + 1) * k[None, :] / (2 * n))
    basis[:, 0] *= 1 / math.sqrt(2)
    basis *= math.sqrt(2.0 / n)
    return basis.T @ block @ basis


def perceptual_hash(path: Path, media_type: str, bits: int = 64) -> str:
    """Content hash that survives re-encoding, for near-duplicate grouping.

    Exact SHA-256 catches a byte-identical redelivery. It does not catch the more
    damaging case: the same recording re-encoded or trivially re-scaled, which
    yields a different digest and can therefore land in two different evaluation
    partitions.

    Both constructions below threshold *low-frequency* coefficients against their
    own median, and both deliberately discard the DC term:

    * images - the standard DCT perceptual hash. The image is reduced to 32x32,
      transformed, and the top-left 8x8 block of coefficients (minus DC) is
      thresholded. Thresholding pixel intensities directly, as a naive
      block-average hash does, is useless on this material: frames of open sky
      are near-uniform, so almost every pair lands within a few bits of every
      other and the whole corpus collapses into one duplicate group.
    * audio - log band energies over a mel-like spacing, differenced between
      adjacent bands before thresholding. Differencing removes the overall gain,
      so a re-encode at a different level still hashes alike while genuinely
      different recordings do not.
    """
    if media_type == "audio":
        x, sr = read_wav(path)
        if x.size < 512:
            return "0" * (bits // 4)
        n_fft = 1024
        hop = max(1, (x.size - n_fft) // 48)
        frames = [x[i:i + n_fft] for i in range(0, max(1, x.size - n_fft), hop)][:48]
        win = np.hanning(n_fft)
        spec = np.abs(np.fft.rfft(np.stack([f * win for f in frames
                                            if f.size == n_fft]), axis=1)) ** 2
        if spec.size == 0:
            return "0" * (bits // 4)
        edges = np.unique(np.geomspace(2, spec.shape[1] - 1, bits + 2).astype(int))
        bands = np.log1p(np.stack(
            [spec[:, edges[i]:edges[i + 1]].mean(axis=1)
             for i in range(len(edges) - 1)], axis=1)).mean(axis=0)
        feat = np.diff(bands)
    else:
        img = read_png_gray(path).astype(np.float64)
        side = 32
        h, w = img.shape
        ri = np.linspace(0, h, side + 1).astype(int)
        ci = np.linspace(0, w, side + 1).astype(int)
        small = np.array([[img[ri[a]:ri[a + 1], ci[b]:ci[b + 1]].mean()
                           for b in range(side)] for a in range(side)])
        coeffs = _dct2(small)[:8, :8].flatten()[1:]     # drop DC
        feat = coeffs

    feat = feat[:bits] if feat.size >= bits else np.pad(feat, (0, bits - feat.size))
    med = np.median(feat)
    bitstr = "".join("1" if v > med else "0" for v in feat)
    return f"{int(bitstr, 2):0{bits // 4}x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")
