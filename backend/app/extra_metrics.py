"""Additional real-time-feasible metrics beyond the KUKAN deterministic core.

These are our own implementation of the formulas described in the
"画像特徴量 — 計算式・使用AIモデル 一覧" feature handoff doc, scoped to the
subset classified as real-time-capable (pure numpy / OpenCV / scikit-learn,
no heavy deep-learning model such as MiDaS or YOLO). Unlike kukan_metrics.py
this is not a verbatim port of an existing reference implementation — the
doc only specifies formulas, not code — so treat these as a first pass
rather than a byte-exact spec. All outputs are clamped to [0,1] and rounded
the same way as the KUKAN core for consistency.
"""
from __future__ import annotations

from math import log2
from typing import Any, Dict

import cv2
import numpy as np
from sklearn.cluster import DBSCAN, MiniBatchKMeans

from .kukan_metrics import clamp01, rgb_hsv, round4

EXTRA_SPEC_VERSION = "space-analyser-extra-metrics-1.0.0"

# Working resolution for this module. KUKAN's own 720px target is sized for
# its exact-formula spec; these are aggregate/statistical measures where a
# coarser frame changes nothing meaningful while cutting the cost of the
# O(n^2)-ish steps (line-pair intersections, contour curvature, saliency)
# enough to fit a real-time per-frame budget.
WORKING_MAX_SIDE = 360

EXTRA_METRIC_KEYS = [
    "coherence_mean",
    "spectral_entropy",
    "spectral_slope",
    "radial_entropy",
    "band_ratio_low",
    "band_ratio_mid",
    "band_ratio_high",
    "directional_entropy",
    "anisotropy_index",
    "vanishing_point_confidence",
    "rectilinearity",
    "curvature_complexity",
    "free_space_ratio",
    "largest_component_ratio",
    "mean_access_radius",
    "corridor_index",
    "hue_circular_variance",
    "complementary_contrast",
    "saturation_std",
    "brightness_range",
    "dominant_color_ratio",
    "attention_peak_ratio",
    "attention_balance",
    "attention_flow_strength",
    "attention_direction_consistency",
    "attention_entropy",
]

_saliency = cv2.saliency.StaticSaliencyFineGrained_create()


def _entropy(p: np.ndarray) -> float:
    """Shannon entropy of a probability vector, normalized to [0,1] by log2(n)."""
    nz = p[p > 0]
    if nz.size <= 1:
        return 0.0
    h = float(-(nz * np.log2(nz)).sum())
    denom = log2(p.size)
    return clamp01(h / denom) if denom > 0 else 0.0


def compute_coherence(gray: np.ndarray) -> float:
    """Structure-tensor coherence: (lambda1-lambda2)/(lambda1+lambda2)."""
    g = gray.astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 1.5)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), 1.5)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), 1.5)
    diff = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2)
    trace = jxx + jyy
    coherence = diff / (trace + 1e-6)
    return clamp01(float(np.mean(coherence)))


def compute_fft_features(gray: np.ndarray) -> Dict[str, float]:
    """2D FFT power-spectrum derived features: entropy, slope, band energy, direction."""
    h, w = gray.shape
    target = 256
    if max(h, w) > target:
        scale = target / max(h, w)
        small = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))))
    else:
        small = gray
    gs = small.astype(np.float64)
    H, W = gs.shape
    if H < 4 or W < 4:
        return {k: 0.0 for k in (
            "spectral_entropy", "spectral_slope", "radial_entropy",
            "band_ratio_low", "band_ratio_mid", "band_ratio_high",
            "directional_entropy", "anisotropy_index",
        )}

    window = np.outer(np.hanning(H), np.hanning(W))
    windowed = gs * window
    spectrum = np.fft.fftshift(np.fft.fft2(windowed))
    power = np.abs(spectrum) ** 2
    total = float(power.sum())
    if total <= 0:
        return {k: 0.0 for k in (
            "spectral_entropy", "spectral_slope", "radial_entropy",
            "band_ratio_low", "band_ratio_mid", "band_ratio_high",
            "directional_entropy", "anisotropy_index",
        )}

    spectral_entropy = _entropy((power / total).ravel())

    cy, cx = H // 2, W // 2
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    r_int = r.astype(int)
    max_r = int(r_int.max())
    radial_sum = np.bincount(r_int.ravel(), weights=power.ravel(), minlength=max_r + 1)
    radial_entropy = _entropy(radial_sum / (radial_sum.sum() + 1e-12))

    rs = np.arange(1, max_r + 1)
    ps = radial_sum[1:max_r + 1]
    mask = ps > 0
    if mask.sum() >= 2:
        slope, _intercept = np.polyfit(np.log(rs[mask]), np.log(ps[mask]), 1)
    else:
        slope = 0.0
    # Natural-image spectra roll off with slope roughly in [-4, 0]; map to [0,1]
    # so a steeper (smoother-image) rolloff reads as a higher value.
    spectral_slope = clamp01(-float(slope) / 4)

    edges = [0, max_r / 3, 2 * max_r / 3, max_r + 1]
    total_energy = float(radial_sum.sum()) + 1e-12
    band_ratio_low = float(radial_sum[int(edges[0]):int(edges[1])].sum()) / total_energy
    band_ratio_mid = float(radial_sum[int(edges[1]):int(edges[2])].sum()) / total_energy
    band_ratio_high = float(radial_sum[int(edges[2]):].sum()) / total_energy

    theta = np.mod(np.arctan2(yy - cy, xx - cx), np.pi)
    nbins = 18
    theta_bins = np.clip(np.floor(theta / np.pi * nbins).astype(int), 0, nbins - 1)
    mask_r = r >= 1
    ang_energy = np.bincount(theta_bins[mask_r], weights=power[mask_r], minlength=nbins)
    directional_entropy = _entropy(ang_energy / (ang_energy.sum() + 1e-12))
    anisotropy_index = clamp01(1 - float(ang_energy.min()) / (float(ang_energy.max()) + 1e-12)) if ang_energy.max() > 0 else 0.0

    return {
        "spectral_entropy": spectral_entropy,
        "spectral_slope": spectral_slope,
        "radial_entropy": radial_entropy,
        "band_ratio_low": clamp01(band_ratio_low),
        "band_ratio_mid": clamp01(band_ratio_mid),
        "band_ratio_high": clamp01(band_ratio_high),
        "directional_entropy": directional_entropy,
        "anisotropy_index": anisotropy_index,
    }


def compute_geometry_features(gray_u8: np.ndarray) -> Dict[str, float]:
    """Vanishing-point confidence, rectilinearity, contour curvature complexity."""
    edges = cv2.Canny(gray_u8, 80, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=20, maxLineGap=6)

    rectilinearity = 0.0
    vanishing_point_confidence = 0.0

    if lines is not None and len(lines) > 0:
        segs = lines[:, 0, :][:150]
        x1, y1, x2, y2 = segs[:, 0], segs[:, 1], segs[:, 2], segs[:, 3]
        lengths = np.hypot(x2 - x1, y2 - y1)
        angles = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
        ortho = (angles < 8) | (angles > 172) | ((angles > 82) & (angles < 98))
        total_len = float(lengths.sum())
        if total_len > 0:
            rectilinearity = clamp01(float(lengths[ortho].sum()) / total_len)

        # Homogeneous-coordinate pairwise intersections, capped for cost.
        ones = np.ones(len(segs))
        p1 = np.stack([x1, y1, ones], axis=1)
        p2 = np.stack([x2, y2, ones], axis=1)
        line_vecs = np.cross(p1, p2)
        n = len(line_vecs)
        pts = []
        max_pairs = 1500
        count = 0
        for i in range(n):
            if count >= max_pairs:
                break
            cross = np.cross(line_vecs[i], line_vecs[i + 1:])
            wv = cross[:, 2]
            valid = np.abs(wv) > 1e-6
            if not np.any(valid):
                continue
            xs = cross[valid, 0] / wv[valid]
            ys = cross[valid, 1] / wv[valid]
            in_frame = (np.abs(xs) < 5000) & (np.abs(ys) < 5000)
            xs, ys = xs[in_frame], ys[in_frame]
            remaining = max_pairs - count
            if len(xs) > remaining:
                xs, ys = xs[:remaining], ys[:remaining]
            pts.append(np.stack([xs, ys], axis=1))
            count += len(xs)
        if pts:
            all_pts = np.concatenate(pts, axis=0)
            if len(all_pts) >= 3:
                labels = DBSCAN(eps=max(gray_u8.shape) * 0.03, min_samples=3).fit_predict(all_pts)
                valid_labels = labels[labels >= 0]
                if valid_labels.size > 0:
                    _, counts = np.unique(valid_labels, return_counts=True)
                    vanishing_point_confidence = clamp01(float(counts.max()) / len(all_pts))

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    curvatures = []
    long_contours = [c for c in contours if len(c) >= 15]
    for c in sorted(long_contours, key=cv2.contourArea, reverse=True)[:20]:
        approx = cv2.approxPolyDP(c, 2.0, closed=False).reshape(-1, 2)
        if len(approx) < 3:
            continue
        v = np.diff(approx, axis=0).astype(np.float64)
        norms = np.linalg.norm(v, axis=1)
        valid = norms > 1e-6
        if valid.sum() < 2:
            continue
        v = v[valid] / norms[valid, None]
        cos_angle = np.clip((v[:-1] * v[1:]).sum(axis=1), -1, 1)
        curvatures.append(np.arccos(cos_angle))

    curvature_complexity = 0.0
    if curvatures:
        kappa = np.concatenate(curvatures)
        if kappa.size > 0:
            mean_norm = clamp01(float(kappa.mean()) / np.pi)
            std_norm = clamp01(float(kappa.std()) / np.pi)
            hist, _ = np.histogram(kappa, bins=12, range=(0, np.pi))
            h_kappa = _entropy(hist / (hist.sum() + 1e-12))
            curvature_complexity = clamp01((mean_norm + std_norm + h_kappa) / 3)

    return {
        "vanishing_point_confidence": vanishing_point_confidence,
        "rectilinearity": rectilinearity,
        "curvature_complexity": curvature_complexity,
    }


def compute_topology_features(gray_u8: np.ndarray) -> Dict[str, float]:
    """Free-space ratio, largest-component ratio, and distance-transform reach."""
    _thresh, binary = cv2.threshold(gray_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    total = cleaned.size
    on = int(np.count_nonzero(cleaned))
    off = total - on
    free_mask = cleaned if on >= off else cv2.bitwise_not(cleaned)
    free_space_ratio = clamp01(max(on, off) / total)

    largest_component_ratio = 0.0
    mean_access_radius = 0.0
    corridor_index = 0.0

    free_area = int(np.count_nonzero(free_mask))
    if free_area > 0:
        num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(free_mask, connectivity=8)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            largest_component_ratio = clamp01(float(areas.max()) / free_area)

        dist = cv2.distanceTransform(free_mask, cv2.DIST_L2, 5)
        norm = max(gray_u8.shape) / 2.0
        # A mask with no background pixels (e.g. a blank frame) makes distanceTransform
        # return its "no boundary" sentinel (float32 max) everywhere, which overflows
        # float32 accumulation on .mean(); cap it since anything beyond a few diagonals
        # away is equally "wide open" for our purposes.
        dist = np.minimum(dist, norm * 4)
        mean_access_radius = clamp01(float(dist.mean()) / norm)
        dvals = dist[free_mask > 0]
        if dvals.size > 0:
            thresh = float(np.percentile(dvals, 25))
            narrow = dvals[dvals <= thresh]
            if narrow.size > 0:
                corridor_index = clamp01(float(narrow.mean()) / norm)

    return {
        "free_space_ratio": free_space_ratio,
        "largest_component_ratio": largest_component_ratio,
        "mean_access_radius": mean_access_radius,
        "corridor_index": corridor_index,
    }


def compute_color_features(rgb: np.ndarray, hue: np.ndarray, sat: np.ndarray, val: np.ndarray) -> Dict[str, float]:
    """Hue circular variance, complementary contrast, saturation/brightness spread, dominant color."""
    valid = sat > 0.12
    if np.any(valid):
        theta = np.radians(hue[valid])
        mean_cos = float(np.cos(theta).mean())
        mean_sin = float(np.sin(theta).mean())
        resultant = np.hypot(mean_cos, mean_sin)
        hue_circular_variance = clamp01(1 - resultant)
    else:
        hue_circular_variance = 0.0

    hist, _ = np.histogram(hue[valid] if np.any(valid) else hue, bins=36, range=(0, 360))
    shifted = np.roll(hist, 18)
    if hist.std() > 0 and shifted.std() > 0:
        corr = float(np.corrcoef(hist.astype(np.float64), shifted.astype(np.float64))[0, 1])
    else:
        corr = 0.0
    complementary_contrast = clamp01((-corr + 1) / 2)

    saturation_std = clamp01(float(sat.std()))
    v_norm = val / 255.0
    brightness_range = clamp01(float(np.percentile(v_norm, 90) - np.percentile(v_norm, 10)))

    pixels = rgb.reshape(-1, 3).astype(np.float64)
    stride = max(1, pixels.shape[0] // 2000)
    sample = pixels[::stride]
    dominant_color_ratio = 0.0
    if len(sample) >= 5:
        km = MiniBatchKMeans(n_clusters=5, random_state=0, n_init=1, max_iter=50, batch_size=256)
        labels = km.fit_predict(sample)
        _, counts = np.unique(labels, return_counts=True)
        dominant_color_ratio = clamp01(float(counts.max()) / len(sample))

    return {
        "hue_circular_variance": hue_circular_variance,
        "complementary_contrast": complementary_contrast,
        "saturation_std": saturation_std,
        "brightness_range": brightness_range,
        "dominant_color_ratio": dominant_color_ratio,
    }


def compute_attention_features(bgr_u8: np.ndarray) -> Dict[str, float]:
    """OpenCV StaticSaliencyFineGrained-derived attention metrics."""
    success, sal = _saliency.computeSaliency(bgr_u8)
    if not success:
        return {k: 0.0 for k in (
            "attention_peak_ratio", "attention_balance", "attention_flow_strength",
            "attention_direction_consistency", "attention_entropy",
        )}
    sal = sal.astype(np.float64)
    total = float(sal.sum())
    if total <= 0:
        return {k: 0.0 for k in (
            "attention_peak_ratio", "attention_balance", "attention_flow_strength",
            "attention_direction_consistency", "attention_entropy",
        )}

    p90 = np.percentile(sal, 90)
    attention_peak_ratio = clamp01(float(sal[sal >= p90].sum()) / total)

    h, w = sal.shape
    gy_edges = [int(h * i / 3) for i in range(4)]
    gx_edges = [int(w * i / 3) for i in range(4)]
    cell_sums = []
    for i in range(3):
        for j in range(3):
            cell = sal[gy_edges[i]:gy_edges[i + 1], gx_edges[j]:gx_edges[j + 1]]
            cell_sums.append(float(cell.sum()))
    cell_p = np.array(cell_sums) / (sum(cell_sums) + 1e-12)
    attention_balance = clamp01(float(1 - (cell_p ** 2).sum()))

    gx = cv2.Sobel(sal, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(sal, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    attention_flow_strength = clamp01(float(mag.mean()) * 3)

    ang = np.mod(np.arctan2(gy, gx), np.pi)
    nbins = 18
    strong = mag > (mag.mean() * 0.5)
    if np.any(strong):
        hist, _ = np.histogram(ang[strong], bins=nbins, range=(0, np.pi))
        direction_entropy = _entropy(hist / (hist.sum() + 1e-12))
    else:
        direction_entropy = 1.0
    attention_direction_consistency = clamp01(1 - direction_entropy)

    p_hat = sal / total
    attention_entropy = _entropy(p_hat.ravel())

    return {
        "attention_peak_ratio": attention_peak_ratio,
        "attention_balance": attention_balance,
        "attention_flow_strength": attention_flow_strength,
        "attention_direction_consistency": attention_direction_consistency,
        "attention_entropy": attention_entropy,
    }


def compute_extra_metrics(rgb_u8: np.ndarray) -> Dict[str, Any]:
    """rgb_u8: RGB-order uint8 frame, typically the already-resized (<=720px) KUKAN input."""
    h, w = rgb_u8.shape[:2]
    if max(h, w) > WORKING_MAX_SIDE:
        scale = WORKING_MAX_SIDE / max(h, w)
        small = cv2.resize(
            rgb_u8, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA
        )
    else:
        small = rgb_u8

    rgb = small.astype(np.float64)
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)
    hue, sat = rgb_hsv(rgb)
    val = rgb.max(axis=2)

    metrics: Dict[str, float] = {"coherence_mean": compute_coherence(gray)}
    metrics.update(compute_fft_features(gray))
    metrics.update(compute_geometry_features(gray_u8))
    metrics.update(compute_topology_features(gray_u8))
    metrics.update(compute_color_features(rgb, hue, sat, val))
    metrics.update(compute_attention_features(small))
    return {k: round4(metrics[k]) for k in EXTRA_METRIC_KEYS}
