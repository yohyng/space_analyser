"""Quantitative space-analysis metrics computed from a single camera frame.

Each metric is a small, independent function of the frame (plus rolling
state for temporal metrics like motion). New metrics can be added by
appending to METRIC_DEFINITIONS and implementing the corresponding
computation in FrameAnalyzer.analyze().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

ANALYSIS_WIDTH = 320  # frames are downscaled to this width before analysis


@dataclass
class MetricDef:
    key: str
    label_ja: str
    unit: str
    group: str
    description_ja: str


METRIC_DEFINITIONS: list[MetricDef] = [
    MetricDef("brightness_mean", "明るさ（平均輝度）", "0-255", "照明", "画面全体の平均輝度"),
    MetricDef("brightness_std", "コントラスト（輝度標準偏差）", "0-255", "照明", "明暗のばらつき"),
    MetricDef("contrast_michelson", "ミケルソンコントラスト", "0-1", "照明", "最明部と最暗部の差の比率"),
    MetricDef("sharpness", "鮮明度（ラプラシアン分散）", "a.u.", "画質", "ピントの合い具合。値が低いほどぼやけている"),
    MetricDef("blur_ratio", "ぼやけ領域の割合", "0-1", "画質", "画面内でピントが甘い領域の割合"),
    MetricDef("noise_estimate", "ノイズ推定量", "a.u.", "画質", "画像に含まれる高周波ノイズの推定量"),
    MetricDef("edge_density", "エッジ密度", "0-1", "構造", "輪郭線が占める画素の割合。物の多さ・複雑さの目安"),
    MetricDef("line_count", "直線検出数", "本", "構造", "ハフ変換で検出した直線の本数。人工物の多さの目安"),
    MetricDef("symmetry_score", "左右対称性", "0-1", "構造", "画面の左右対称性。1に近いほど対称"),
    MetricDef("rule_of_thirds_score", "三分割構図スコア", "0-1", "構造", "三分割線付近へのエッジの集中度"),
    MetricDef("saturation_mean", "彩度（平均）", "0-255", "色彩", "色の鮮やかさの平均"),
    MetricDef("colorfulness", "カラフルさ指数", "a.u.", "色彩", "Hasler-Süsstrunk法によるカラフルさ"),
    MetricDef("color_entropy", "色情報エントロピー", "bit", "色彩", "輝度分布の情報量。高いほど情報量が多い"),
    MetricDef("unique_color_ratio", "色多様性", "0-1", "色彩", "量子化した色空間のうち使用されている割合"),
    MetricDef("avg_color_r", "平均色 R", "0-255", "色彩", "画面の平均色（赤成分）"),
    MetricDef("avg_color_g", "平均色 G", "0-255", "色彩", "画面の平均色（緑成分）"),
    MetricDef("avg_color_b", "平均色 B", "0-255", "色彩", "画面の平均色（青成分）"),
    MetricDef("motion_level", "動き量", "0-1", "動的変化", "直前フレームとの差分。動きの大きさ"),
    MetricDef("foreground_ratio", "前景占有率", "0-1", "動的変化", "背景モデルとの差分から推定した前景（変化物・人など）の割合"),
    MetricDef("clutter_index", "乱雑度指数", "0-100", "総合", "エッジ密度・直線数・前景占有率を統合した散らかり度の簡易指標"),
]

METRIC_KEYS = [m.key for m in METRIC_DEFINITIONS]


def _entropy(gray: np.ndarray) -> float:
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist = hist / (hist.sum() + 1e-9)
    nz = hist[hist > 0]
    return float(-(nz * np.log2(nz)).sum())


def _colorfulness(frame_bgr: np.ndarray) -> float:
    b, g, r = cv2.split(frame_bgr.astype("float32"))
    rg = r - g
    yb = 0.5 * (r + g) - b
    std_rg, mean_rg = rg.std(), rg.mean()
    std_yb, mean_yb = yb.std(), yb.mean()
    return float(np.sqrt(std_rg**2 + std_yb**2) + 0.3 * np.sqrt(mean_rg**2 + mean_yb**2))


def _symmetry_score(gray: np.ndarray) -> float:
    flipped = cv2.flip(gray, 1)
    mad = float(np.abs(gray.astype("int16") - flipped.astype("int16")).mean())
    return max(0.0, 1.0 - mad / 255.0)


def _noise_estimate(gray: np.ndarray) -> float:
    # Immerkaer's fast noise estimation
    h, w = gray.shape
    if h < 3 or w < 3:
        return 0.0
    mask = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype="float32")
    conv = cv2.filter2D(gray.astype("float32"), -1, mask)
    sigma = np.sum(np.abs(conv)) * np.sqrt(0.5 * np.pi) / (6 * (w - 2) * (h - 2))
    return float(sigma)


def _blur_ratio(gray: np.ndarray, grid: int = 4, threshold: float = 60.0) -> float:
    h, w = gray.shape
    gh, gw = h // grid, w // grid
    if gh == 0 or gw == 0:
        return 0.0
    blurry = 0
    total = 0
    for i in range(grid):
        for j in range(grid):
            patch = gray[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw]
            if patch.size == 0:
                continue
            total += 1
            if cv2.Laplacian(patch, cv2.CV_64F).var() < threshold:
                blurry += 1
    return blurry / total if total else 0.0


def _rule_of_thirds_score(edges: np.ndarray) -> float:
    h, w = edges.shape
    total_energy = float(edges.sum()) + 1e-9
    band_h, band_w = max(1, h // 8), max(1, w // 8)
    lines_y = [h // 3, 2 * h // 3]
    lines_x = [w // 3, 2 * w // 3]
    energy = 0.0
    for y in lines_y:
        y0, y1 = max(0, y - band_h // 2), min(h, y + band_h // 2)
        energy += float(edges[y0:y1, :].sum())
    for x in lines_x:
        x0, x1 = max(0, x - band_w // 2), min(w, x + band_w // 2)
        energy += float(edges[:, x0:x1].sum())
    return min(1.0, energy / total_energy)


def _unique_color_ratio(frame_bgr: np.ndarray, levels: int = 4) -> float:
    quant = (frame_bgr.astype("int32") * levels // 256).clip(0, levels - 1)
    flat = quant[:, :, 0] * levels * levels + quant[:, :, 1] * levels + quant[:, :, 2]
    unique = np.unique(flat).size
    return unique / (levels**3)


@dataclass
class FrameAnalyzer:
    """Holds temporal state (previous frame, background model) for one stream/session."""

    prev_gray: Optional[np.ndarray] = None
    bg_avg: Optional[np.ndarray] = None

    def analyze(self, frame_bgr: np.ndarray) -> dict[str, float]:
        h, w = frame_bgr.shape[:2]
        if w > ANALYSIS_WIDTH:
            scale = ANALYSIS_WIDTH / w
            frame_bgr = cv2.resize(frame_bgr, (ANALYSIS_WIDTH, int(h * scale)))

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        edges = cv2.Canny(gray, 100, 200)

        brightness_mean = float(gray.mean())
        brightness_std = float(gray.std())
        lmin, lmax = float(gray.min()), float(gray.max())
        contrast_michelson = (lmax - lmin) / (lmax + lmin + 1e-9)

        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        blur_ratio = _blur_ratio(gray)
        noise_estimate = _noise_estimate(gray)

        edge_density = float(edges.mean() / 255.0)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=25, maxLineGap=8)
        line_count = int(0 if lines is None else len(lines))
        symmetry_score = _symmetry_score(gray)
        rule_of_thirds_score = _rule_of_thirds_score(edges)

        saturation_mean = float(hsv[:, :, 1].mean())
        colorfulness = _colorfulness(frame_bgr)
        color_entropy = _entropy(gray)
        unique_color_ratio = _unique_color_ratio(frame_bgr)
        b_mean, g_mean, r_mean = [float(x) for x in cv2.mean(frame_bgr)[:3]]

        if self.prev_gray is not None and self.prev_gray.shape == gray.shape:
            motion_level = float(np.abs(gray.astype("int16") - self.prev_gray.astype("int16")).mean() / 255.0)
        else:
            motion_level = 0.0
        self.prev_gray = gray

        gray_f32 = gray.astype("float32")
        if self.bg_avg is None:
            self.bg_avg = gray_f32.copy()
        cv2.accumulateWeighted(gray_f32, self.bg_avg, 0.05)
        diff = np.abs(gray_f32 - self.bg_avg)
        foreground_ratio = float((diff > 25).mean())

        clutter_index = float(
            min(
                100.0,
                (edge_density * 45.0 + min(line_count / 60.0, 1.0) * 35.0 + foreground_ratio * 20.0),
            )
        )

        return {
            "brightness_mean": brightness_mean,
            "brightness_std": brightness_std,
            "contrast_michelson": contrast_michelson,
            "sharpness": sharpness,
            "blur_ratio": blur_ratio,
            "noise_estimate": noise_estimate,
            "edge_density": edge_density,
            "line_count": float(line_count),
            "symmetry_score": symmetry_score,
            "rule_of_thirds_score": rule_of_thirds_score,
            "saturation_mean": saturation_mean,
            "colorfulness": colorfulness,
            "color_entropy": color_entropy,
            "unique_color_ratio": unique_color_ratio,
            "avg_color_r": r_mean,
            "avg_color_g": g_mean,
            "avg_color_b": b_mean,
            "motion_level": motion_level,
            "foreground_ratio": foreground_ratio,
            "clutter_index": clutter_index,
        }
