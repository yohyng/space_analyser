import unittest

import numpy as np

from app.extra_metrics import EXTRA_METRIC_KEYS, compute_extra_metrics


class T(unittest.TestCase):
    def test_range_and_keys(self):
        rng = np.random.default_rng(3)
        rgb = rng.integers(0, 256, (240, 320, 3), dtype="uint8")
        result = compute_extra_metrics(rgb)
        self.assertEqual(set(result), set(EXTRA_METRIC_KEYS))
        for key, value in result.items():
            self.assertTrue(0 <= value <= 1, f"{key}={value} out of [0,1]")

    def test_deterministic(self):
        rng = np.random.default_rng(11)
        rgb = rng.integers(0, 256, (180, 240, 3), dtype="uint8")
        self.assertEqual(compute_extra_metrics(rgb), compute_extra_metrics(rgb))

    def test_degenerate_frames_do_not_crash(self):
        for arr in [
            np.zeros((100, 140, 3), dtype="uint8"),
            np.full((100, 140, 3), 255, dtype="uint8"),
        ]:
            result = compute_extra_metrics(arr)
            self.assertEqual(len(result), len(EXTRA_METRIC_KEYS))


if __name__ == "__main__":
    unittest.main()
