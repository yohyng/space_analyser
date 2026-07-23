"""Quantitative space-analysis metrics computed from a single camera frame.

The 31 image-statistics metrics are the KUKAN deterministic core
(`kukan_metrics.py`, spec `kukan-image-first-metrics-1.0.0`) — ported
unmodified from the reference implementation so results stay reproducible:
same preprocessed image in, same numbers out, regardless of when or how
often a frame is analyzed. `motion_level` and `foreground_ratio` are the
two exceptions: they compare a frame against recent history (previous
frame / running background average), which is inherently not a
single-image-reproducible quantity, so they are kept as a separate
"dynamic change" group layered on top of the deterministic core.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from .kukan_metrics import MAX_ANALYSIS_SIZE, SPEC_VERSION, analyze_rgba, round4


@dataclass
class MetricDef:
    key: str
    label_ja: str
    unit: str
    group: str
    description_ja: str


def _d(high: str, low: str, note: str = "") -> str:
    text = f"高いと{high}。低いと{low}。"
    return f"{text}({note})" if note else text


METRIC_DEFINITIONS: list[MetricDef] = [
    # 光・明暗
    MetricDef("mean_luminance", "平均明度", "0-1", "光・明暗", _d("明るい・白い・採光が強い", "暗い・陰影が強い", "Y=0.2126R+0.7152G+0.0722B")),
    MetricDef("contrast_index", "コントラスト", "0-1", "光・明暗", _d("明暗差が強い", "淡くフラット", "露出・編集の影響を受ける")),
    MetricDef("dark_ratio", "暗部比率", "0-1", "光・明暗", _d("暗部・影・黒い面が多い", "暗部が少ない", "閾値55は固定")),
    MetricDef("highlight_ratio", "明部比率", "0-1", "光・明暗", _d("白い面・発光面が多い", "強い明部が少ない", "白飛びにも反応")),
    MetricDef("midtone_ratio", "中間調比率", "0-1", "光・明暗", _d("中間階調が多い", "暗部か明部に偏る", "階調バランスの補助指標")),
    # 色彩
    MetricDef("mean_saturation", "平均彩度", "0-1", "色彩", _d("鮮やかな色が多い", "無彩色・低彩度", "HSVのSを使用")),
    MetricDef("colorfulness", "カラフルネス", "0-1", "色彩", _d("カラフル・色差が大きい", "色差が小さい", "rg=R-G, yb=0.5(R+G)-B")),
    MetricDef("hue_entropy", "色相多様性", "0-1", "色彩", _d("多様な色相", "特定色相に偏る", "低彩度ピクセルは除外")),
    MetricDef("warm_ratio", "暖色比率", "0-1", "色彩", _d("暖色・木質・電球色が多い", "暖色が少ない", "素材色と照明色の両方に反応")),
    MetricDef("cool_ratio", "寒色比率", "0-1", "色彩", _d("青・寒色が多い", "寒色が少ない", "窓外の青空にも反応")),
    # 複雑性・テクスチャ
    MetricDef("luminance_entropy", "輝度エントロピー", "0-1", "複雑性・テクスチャ", _d("階調が多様", "単調な明度分布", "エッジ量ではなく階調分布")),
    MetricDef("edge_density", "エッジ密度", "0-1", "複雑性・テクスチャ", _d("輪郭・細部・目地が多い", "大きな面が多い", "mag=sqrt(gx^2+gy^2)/2")),
    MetricDef("edge_strength", "エッジ強度", "0-1", "複雑性・テクスチャ", _d("境界が強い", "境界が柔らかい", "ピントの影響を受ける")),
    MetricDef("orientation_entropy", "方向多様性", "0-1", "複雑性・テクスチャ", _d("多方向の線", "水平・垂直等に集中", "線量ではなく方向分布")),
    MetricDef("texture_variation", "局所テクスチャ変動", "0-1", "複雑性・テクスチャ", _d("素材感・模様が強い", "滑らかで均質", "圧縮ノイズにも反応")),
    MetricDef("high_frequency_proxy", "高周波成分", "0-1", "複雑性・テクスチャ", _d("細部が多い", "滑らかな面が多い", "FFTではなく勾配近似")),
    # 構図・幾何
    MetricDef("visual_center_x", "視覚重心X", "0-1", "構図・幾何", _d("右寄り", "左寄り", "w=mag+abs(Y-meanY)*0.18+S*12")),
    MetricDef("visual_center_y", "視覚重心Y", "0-1", "構図・幾何", _d("下寄り", "上寄り", "w=mag+abs(Y-meanY)*0.18+S*12")),
    MetricDef("center_distance", "中心からのズレ", "0-1", "構図・幾何", _d("偏った構図", "中心に近い構図", "構図偏りの補助指標")),
    MetricDef("left_right_balance", "左右バランス", "0-1", "構図・幾何", _d("左右が均衡", "左右に偏る", "対称性ではなく重みの均衡")),
    MetricDef("top_bottom_balance", "上下バランス", "0-1", "構図・幾何", _d("上下が均衡", "上下に偏る", "空間写真では下寄りになりやすい")),
    MetricDef("vertical_symmetry", "左右対称性", "0-1", "構図・幾何", _d("左右対称的", "左右差が大きい", "2px間隔でサンプリング")),
    MetricDef("horizontal_symmetry", "上下対称性", "0-1", "構図・幾何", _d("上下が類似", "上下差が大きい", "2px間隔でサンプリング")),
    MetricDef("axis_aligned_ratio", "水平垂直軸性", "0-1", "構図・幾何", _d("直交性が強い", "斜め線・曲線が多い", "建築写真では高くなりやすい")),
    # 空間プロキシ
    MetricDef("depth_cue_proxy", "奥行き手がかり", "0-1", "空間プロキシ", _d("奥行き手がかりが強い", "平面的", "深度推定ではない")),
    MetricDef("openness_proxy", "開放感プロキシ", "0-1", "空間プロキシ", _d("明るく抜けがある", "囲われ感・密度が強い", "体験そのものではなく画像プロキシ")),
    MetricDef("enclosure_proxy", "囲われ感プロキシ", "0-1", "空間プロキシ", _d("囲われた印象", "開けた印象", "心理効果の直接測定ではない")),
    MetricDef("layer_separation_proxy", "前中背景分離", "0-1", "空間プロキシ", _d("レイヤー差がある", "均質で平面的", "セマンティック分割ではない")),
    MetricDef("foreground_weight_proxy", "前景重み", "0-1", "空間プロキシ", _d("手前・床・家具が強い", "上側・奥側が強い", "本物の前景認識ではない")),
    MetricDef("background_lightness_proxy", "背景明るさ", "0-1", "空間プロキシ", _d("上部・奥側が明るい", "上部・奥側が暗い", "背景を厳密検出していない")),
    MetricDef("spatial_clarity_proxy", "空間明瞭性", "0-1", "空間プロキシ", _d("構造が読み取りやすい", "構造が読み取りにくい", "空間の良し悪しではない")),
    # 動的変化 (フレーム間の時間的な変化。単一画像からは再現できない指標)
    MetricDef("motion_level", "動き量", "0-1", "動的変化", "直前フレームとの輝度差分。動きの大きさ。(時系列依存のため単一画像では再現不可)"),
    MetricDef("foreground_ratio", "前景占有率", "0-1", "動的変化", "背景モデルとの差分から推定した前景の割合。(時系列依存のため単一画像では再現不可)"),
]

METRIC_KEYS = [m.key for m in METRIC_DEFINITIONS]


def _prepare_rgba(frame_bgr: np.ndarray) -> np.ndarray:
    """Resize per the KUKAN preprocess spec: scale=min(720/w,720/h,1), LANCZOS."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb, mode="RGB").convert("RGBA")
    w, h = im.size
    scale = min(MAX_ANALYSIS_SIZE / w, MAX_ANALYSIS_SIZE / h, 1)
    out = (max(1, int(np.floor(w * scale))), max(1, int(np.floor(h * scale))))
    if out != (w, h):
        im = im.resize(out, Image.Resampling.LANCZOS)
    arr = np.asarray(im, dtype=np.uint8).copy()
    arr[arr[..., 3] == 0, :3] = 0
    return arr


@dataclass
class FrameAnalyzer:
    """Holds temporal state (previous frame, background model) for one stream/session."""

    prev_gray: Optional[np.ndarray] = None
    bg_avg: Optional[np.ndarray] = None

    def analyze(self, frame_bgr: np.ndarray) -> dict:
        rgba = _prepare_rgba(frame_bgr)
        result = analyze_rgba(rgba)
        metrics: dict[str, float] = dict(result["metrics"])

        rgb = rgba[..., :3].astype(np.float64)
        gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

        if self.prev_gray is not None and self.prev_gray.shape == gray.shape:
            motion_level = float(np.abs(gray - self.prev_gray).mean() / 255.0)
        else:
            motion_level = 0.0
        self.prev_gray = gray

        if self.bg_avg is None or self.bg_avg.shape != gray.shape:
            self.bg_avg = gray.copy()
        else:
            self.bg_avg = self.bg_avg * 0.95 + gray * 0.05
        foreground_ratio = float((np.abs(gray - self.bg_avg) > 25).mean())

        metrics["motion_level"] = round4(motion_level)
        metrics["foreground_ratio"] = round4(foreground_ratio)

        return {"spec_version": SPEC_VERSION, "metrics": metrics}
