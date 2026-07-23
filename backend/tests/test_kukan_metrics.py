
import unittest, numpy as np
from app.kukan_metrics import analyze_rgba, METRIC_KEYS

def rgba(rgb):
    a=np.full((*rgb.shape[:2],1),255,dtype=np.uint8)
    return np.concatenate([rgb,a],axis=2)

class T(unittest.TestCase):
    def test_black(self):
        m=analyze_rgba(rgba(np.zeros((16,16,3),dtype=np.uint8)))["metrics"]
        self.assertEqual(len(m),31); self.assertEqual(m["dark_ratio"],1.0); self.assertEqual(m["mean_luminance"],0.0)
    def test_white(self):
        m=analyze_rgba(rgba(np.full((16,16,3),255,dtype=np.uint8)))["metrics"]
        self.assertEqual(m["highlight_ratio"],1.0); self.assertEqual(m["mean_luminance"],1.0)
    def test_deterministic(self):
        rng=np.random.default_rng(7); arr=rgba(rng.integers(0,256,(24,31,3),dtype=np.uint8))
        self.assertEqual(analyze_rgba(arr),analyze_rgba(arr))
    def test_range(self):
        rng=np.random.default_rng(9); m=analyze_rgba(rgba(rng.integers(0,256,(20,20,3),dtype=np.uint8)))["metrics"]
        self.assertEqual(set(m),set(METRIC_KEYS))
        self.assertTrue(all(0<=v<=1 for v in m.values()))
if __name__=="__main__": unittest.main()
