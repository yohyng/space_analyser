
from __future__ import annotations
from math import floor, log2, pi, sqrt
from pathlib import Path
from typing import Any, Dict
import numpy as np
from PIL import Image

SPEC_VERSION = "kukan-image-first-metrics-1.0.0"
MAX_ANALYSIS_SIZE = 720
METRIC_KEYS = [
"mean_luminance","contrast_index","dark_ratio","highlight_ratio","midtone_ratio",
"mean_saturation","colorfulness","hue_entropy","warm_ratio","cool_ratio",
"luminance_entropy","edge_density","edge_strength","orientation_entropy",
"texture_variation","high_frequency_proxy","visual_center_x","visual_center_y",
"center_distance","left_right_balance","top_bottom_balance","vertical_symmetry",
"horizontal_symmetry","axis_aligned_ratio","depth_cue_proxy","openness_proxy",
"enclosure_proxy","layer_separation_proxy","foreground_weight_proxy",
"background_lightness_proxy","spatial_clarity_proxy"]

def clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v))) if np.isfinite(v) else 0.0

def round4(v: float) -> float:
    v = clamp01(v)
    return floor(v*10000+0.5)/10000

def ent(hist: np.ndarray) -> float:
    total=float(hist.sum())
    if total<=0 or hist.size<=1: return 0.0
    p=hist.astype(float)/total; p=p[p>0]
    return float(-(p*np.log2(p)).sum()/log2(hist.size))

def rgb_hsv(rgb: np.ndarray):
    a=rgb.astype(float)/255.0; r,g,b=a[...,0],a[...,1],a[...,2]
    mx=a.max(2); mn=a.min(2); d=mx-mn; h=np.zeros_like(mx)
    mask=d!=0
    rm=mask&(mx==r); gm=mask&(mx==g); bm=mask&(mx==b)
    h[rm]=np.mod((g[rm]-b[rm])/d[rm],6); h[gm]=(b[gm]-r[gm])/d[gm]+2; h[bm]=(r[bm]-g[bm])/d[bm]+4
    h*=60; h[h<0]+=360
    s=np.zeros_like(mx); nz=mx!=0; s[nz]=d[nz]/mx[nz]
    return h,s

def symmetry_v(gray):
    H,W=gray.shape; half=W//2; ys=np.arange(0,H,2); xs=np.arange(0,half,2)
    if half==0 or not len(ys) or not len(xs): return 1.0
    return clamp01(1-float(np.mean(np.abs(gray[np.ix_(ys,xs)]-gray[np.ix_(ys,W-1-xs)])))/255)

def symmetry_h(gray):
    H,W=gray.shape; half=H//2; ys=np.arange(0,half,2); xs=np.arange(0,W,2)
    if half==0 or not len(ys) or not len(xs): return 1.0
    return clamp01(1-float(np.mean(np.abs(gray[np.ix_(ys,xs)]-gray[np.ix_(H-1-ys,xs)])))/255)

def texture(gray, block=18):
    H,W=gray.shape; vals=[]
    for by in range(0,H,block):
        for bx in range(0,W,block):
            b=gray[by:min(H,by+block),bx:min(W,bx+block)]
            if b.size: vals.append(float(np.std(b))/128)
    return clamp01(float(np.mean(vals)) if vals else 0)

def bands(gray,n=5):
    H=gray.shape[0]
    return [float(gray[(H*i)//n:(H*(i+1))//n,:].mean()) for i in range(n)]

def analyze_rgba(rgba: np.ndarray) -> Dict[str,Any]:
    H,W=rgba.shape[:2]; rgb=rgba[...,:3].astype(float)
    r,g,b=rgb[...,0],rgb[...,1],rgb[...,2]
    gray=.2126*r+.7152*g+.0722*b; hue,sat=rgb_hsv(rgb); N=H*W
    meanY=float(gray.mean()); stdY=float(np.std(gray))
    dark=float((gray<55).sum()); hi=float((gray>205).sum()); mid=N-dark-hi
    lh,_=np.histogram(gray,bins=32,range=(0,256)); hh,_=np.histogram(hue[sat>.12],bins=24,range=(0,360))
    warm=float(((sat>.12)&((hue<=65)|(hue>=330))).sum()); cool=float(((sat>.12)&(hue>=170)&(hue<=270)).sum())
    rg=r-g; yb=.5*(r+g)-b
    cf=sqrt(float(np.std(rg))**2+float(np.std(yb))**2)+.3*sqrt(float(rg.mean())**2+float(yb.mean())**2)
    if W>=3 and H>=3:
        gx=gray[1:-1,2:]-gray[1:-1,:-2]; gy=gray[2:,1:-1]-gray[:-2,1:-1]; mag=np.sqrt(gx*gx+gy*gy)/2
        ig=gray[1:-1,1:-1]; isat=sat[1:-1,1:-1]
    else:
        mag=np.zeros((0,0)); gx=gy=mag; ig=isat=mag
    inner=max(1,mag.size); edge=mag>24; high=mag>42; edgeRaw=float(edge.sum())/inner
    oh=np.zeros(18,dtype=int)
    if mag.size and edge.any():
        ang=np.mod(np.arctan2(gy,gx),pi); oh,_=np.histogram(ang[edge],bins=18,range=(0,pi))
    orient=ent(oh); axisRaw=float(oh[[0,1,8,9,16,17]].sum())/max(1,int(oh.sum()))
    if mag.size:
        w=mag+np.abs(ig-meanY)*.18+isat*12
        ys,xs=np.meshgrid(np.arange(1,H-1),np.arange(1,W-1),indexing="ij"); ws=float(w.sum())
        cx=float((xs*w).sum())/ws/W if ws else .5; cy=float((ys*w).sum())/ws/H if ws else .5
        L=float(w[xs<W/2].sum()); R=float(w[xs>=W/2].sum()); T=float(w[ys<H/2].sum()); B=float(w[ys>=H/2].sum())
    else:
        cx=cy=.5; L=R=T=B=0
    lrb=clamp01(1-abs(L-R)/max(1,L+R)); tbb=clamp01(1-abs(T-B)/max(1,T+B))
    bs=bands(gray); top=bs[0]/255; bot=bs[4]/255; cen=bs[2]/255; bstd=float(np.std(bs))/128; ced=abs(cen-(top+bot)/2)
    vs=symmetry_v(gray); hs=symmetry_h(gray); tex=texture(gray)
    raw={
    "mean_luminance":meanY/255,"contrast_index":stdY/96,"dark_ratio":dark/N,"highlight_ratio":hi/N,"midtone_ratio":mid/N,
    "mean_saturation":float(sat.mean()),"colorfulness":cf/120,"hue_entropy":ent(hh),"warm_ratio":warm/N,"cool_ratio":cool/N,
    "luminance_entropy":ent(lh),"edge_density":edgeRaw*2.6,"edge_strength":float(mag.sum())/inner/128,
    "orientation_entropy":orient,"texture_variation":tex,"high_frequency_proxy":float(high.sum())/inner*3.4,
    "visual_center_x":cx,"visual_center_y":cy,"center_distance":sqrt((cx-.5)**2+(cy-.5)**2)/sqrt(.5),
    "left_right_balance":lrb,"top_bottom_balance":tbb,"vertical_symmetry":vs,"horizontal_symmetry":hs,
    "axis_aligned_ratio":axisRaw*1.8,"depth_cue_proxy":abs(top-bot)*.55+ced*.45+axisRaw*.18,
    "openness_proxy":top*.45+(1-edgeRaw)*.25+(hi/N)*.35+lrb*.12,
    "enclosure_proxy":(1-top)*.34+edgeRaw*.44+(dark/N)*.42,
    "layer_separation_proxy":bstd*.75+tex*.25,"foreground_weight_proxy":B/max(1,T+B),
    "background_lightness_proxy":top,"spatial_clarity_proxy":vs*.24+lrb*.22+axisRaw*.22+(1-orient)*.18+(mid/N)*.14}
    return {"spec_version":SPEC_VERSION,"analyzed_width":W,"analyzed_height":H,"metrics":{k:round4(raw[k]) for k in METRIC_KEYS}}

def analyze_image(path: str|Path, max_side: int=MAX_ANALYSIS_SIZE):
    im=Image.open(path).convert("RGBA"); W,H=im.size; s=min(max_side/W,max_side/H,1); out=(max(1,int(np.floor(W*s))),max(1,int(np.floor(H*s))))
    if out!=(W,H): im=im.resize(out,Image.Resampling.LANCZOS)
    arr=np.asarray(im,dtype=np.uint8).copy(); arr[arr[...,3]==0,:3]=0
    result=analyze_rgba(arr); result["source_path"]=str(path); return result
