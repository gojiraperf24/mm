"""Meaningful camera-free checks. Synthetic fixtures are NOT sign training data."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from common import COLUMNS, ensure_dataset, load_vocabulary, read_dataset
from hand_features import FEATURE_NAMES, FEATURE_VERSION, extract_features, normalize_landmarks
from prediction import PredictionSmoother, classify
from realtime_predict import load_model
from train_model import grouped_split, train


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.points = np.random.default_rng(7).uniform(0.2, 0.8, (21, 3))

    def test_translation_and_scale_invariance(self):
        baseline = extract_features(self.points, 640, 480)
        moved = extract_features(self.points * 0.6 + [0.1, 0.2, -0.03], 640, 480)
        np.testing.assert_allclose(baseline, moved, atol=1e-6)
        self.assertEqual(len(baseline), 83)
        np.testing.assert_allclose(normalize_landmarks(self.points, 640, 480)[0], 0)

    def test_aspect_correction_and_orientation(self):
        resized = self.points * [640 / 1280, 480 / 720, 640 / 1280]
        baseline = extract_features(self.points, 640, 480)
        np.testing.assert_allclose(baseline, extract_features(resized, 1280, 720), atol=1e-6)
        rotated = self.points.copy()
        rotated[:, :2] *= -1
        self.assertFalse(np.allclose(baseline, extract_features(rotated, 640, 480)))

    def test_invalid_landmarks(self):
        for bad in [np.zeros((21, 3)), np.full((21, 3), np.nan), np.zeros((20, 3))]:
            with self.assertRaises(ValueError):
                extract_features(bad, 640, 480)

    def test_smoothing_transitions_and_gap(self):
        s = PredictionSmoother(3)
        self.assertEqual([s.update("FIST", t) for t in [0, 0.1, 0.2]], ["UNKNOWN", "UNKNOWN", "FIST"])
        self.assertEqual(s.update("OPEN_PALM", 0.3), "UNKNOWN")
        self.assertEqual(s.update("NO_SIGN", 0.4), "NO_SIGN")
        self.assertEqual(s.update("FIST", 0.5), "UNKNOWN")
        self.assertEqual(s.update("UNKNOWN", 0.6), "UNKNOWN")
        self.assertEqual(s.count, 0)
        for t in [0.7, 0.8, 0.9]:
            result = s.update("REST", t)
        self.assertEqual(result, "REST")
        self.assertEqual(s.update("REST", 2), "UNKNOWN")

    def test_low_confidence_rejection(self):
        class FakeModel:
            classes_ = np.array(["REST", "FIST"])
            def predict_proba(self, x):
                return np.array([[0.45, 0.55]])
        self.assertEqual(classify(FakeModel(), np.zeros(83), 0.7), ("UNKNOWN", "FIST", 0.55))

    def test_group_separation(self):
        y = np.tile(["A", "B", "REST"], 10)
        groups = np.repeat(np.arange(10), 3)
        a, b, c = grouped_split(y, groups)
        for left, right in [(a, b), (a, c), (b, c)]:
            self.assertFalse(set(groups[left]) & set(groups[right]))
        for idx in [a, b, c]:
            self.assertEqual(set(y[idx]), set(y))
        with self.assertRaises(ValueError):
            grouped_split(y, np.zeros(len(y)))

    def test_train_save_reload_and_bad_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "signs.json"
            config.write_text(json.dumps({"signs": {"A": "Fixture A", "B": "Fixture B", "REST": "Fixture rest"}}))
            signs, digest = load_vocabulary(config)
            dataset = root / "test.csv"
            ensure_dataset(dataset)
            rng = np.random.default_rng(23)
            with dataset.open("a", newline="") as f:
                writer = csv.writer(f)
                for session in range(10):
                    for label_index, label in enumerate(signs):
                        for _ in range(8):
                            features = rng.normal(label_index * 3, 0.1, len(FEATURE_NAMES))
                            writer.writerow([label, "synthetic", str(session), "fixture", FEATURE_VERSION, digest, *features])
            output = root / "test.pkl"
            trained = train(dataset, output, config)
            loaded = load_model(output, config)
            probe = np.zeros((1, len(FEATURE_NAMES)))
            np.testing.assert_allclose(trained["model"].predict_proba(probe), loaded["model"].predict_proba(probe))
            self.assertTrue(output.with_suffix(".metrics.json").is_file())
            self.assertTrue(output.with_suffix(".confusion.csv").is_file())
            with dataset.open("a", newline="") as f:
                csv.writer(f).writerow(["A", "p", "s", "t", FEATURE_VERSION, digest, *(["nan"] * 83)])
            with self.assertRaisesRegex(ValueError, "Non-finite"):
                read_dataset(dataset, signs, digest)
            config.write_text(json.dumps({"signs": {"A": "Changed pose", "REST": "Rest"}}))
            with self.assertRaisesRegex(ValueError, "mismatch"):
                load_model(output, config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
