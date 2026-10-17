"""Checks for image features and exact-duplicate split protection."""
import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from image_features import image_features
from train_archive import prepare
from predict_archive import crop_hand


class ArchiveTests(unittest.TestCase):
    def test_image_feature_shape_and_grayscale_consistency(self):
        gray = np.random.default_rng(1).integers(0, 256, (28, 28), dtype=np.uint8)
        feature = image_features(gray)
        self.assertEqual(feature.shape, (324,))
        self.assertTrue(np.isfinite(feature).all())
        np.testing.assert_allclose(feature, image_features(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))
        with self.assertRaises(ValueError):
            image_features(None)

    def test_duplicate_and_label_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for split in ["Train", "Test"]:
                for label in ["A", "B"]:
                    (root / split / label).mkdir(parents=True)
            rng = np.random.default_rng(8)
            image_a, image_b, image_c = [rng.integers(0, 256, (28, 28), dtype=np.uint8) for _ in range(3)]
            cv2.imwrite(str(root / "Train/A/1_A.png"), image_a)
            cv2.imwrite(str(root / "Train/A/2_A.png"), image_a)
            cv2.imwrite(str(root / "Test/A/3_A.png"), image_a)
            cv2.imwrite(str(root / "Train/B/4_B.png"), image_b)
            cv2.imwrite(str(root / "Test/B/5_B.png"), image_c)
            cv2.imwrite(str(root / "Test/B/6_A.png"), image_c)
            x, y, source, rows, audit = prepare(root, root / "results")
            self.assertEqual(audit["statuses"]["duplicate_within_split"], 1)
            self.assertEqual(audit["statuses"]["test_duplicate_of_train"], 1)
            self.assertEqual(audit["statuses"]["filename_label_mismatch"], 1)
            self.assertEqual(len(x), 3)
            self.assertFalse({r["pixel_sha256"] for r in rows if r["source_split"] == "Train"}
                             & {r["pixel_sha256"] for r in rows if r["source_split"] == "Test"})

    def test_crop_bounds(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        points = np.zeros((21, 3))
        points[:, 0] = np.linspace(0, 0.4, 21)
        points[:, 1] = np.linspace(0, 0.5, 21)
        crop, box = crop_hand(frame, points)
        self.assertGreater(crop.size, 0)
        self.assertGreaterEqual(min(box), 0)
        self.assertLessEqual(box[2], 640)
        self.assertLessEqual(box[3], 480)


if __name__ == "__main__":
    unittest.main(verbosity=2)
