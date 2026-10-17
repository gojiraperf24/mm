"""Confidence rejection and consecutive-frame smoothing, independent of UI."""
import numpy as np


def classify(model, features, threshold):
    probabilities = model.predict_proba(np.asarray(features).reshape(1, -1))[0]
    index = int(np.argmax(probabilities))
    raw_label, confidence = str(model.classes_[index]), float(probabilities[index])
    return (raw_label if confidence >= threshold else "UNKNOWN"), raw_label, confidence


class PredictionSmoother:
    """Require N consecutive labels, immediately clearing stale accepted signs."""
    def __init__(self, frames=5, max_gap=0.5):
        if frames < 1 or max_gap <= 0:
            raise ValueError("frames and max_gap must be positive.")
        self.frames, self.max_gap = frames, max_gap
        self.reset()

    def reset(self):
        self.candidate, self.count, self.last_time = None, 0, None

    def update(self, label, now):
        if self.last_time is not None and (now - self.last_time > self.max_gap or now < self.last_time):
            self.reset()
        self.last_time = now
        if label in ("UNKNOWN", "NO_SIGN"):
            self.candidate, self.count = None, 0
            return label
        if label != self.candidate:
            self.candidate, self.count = label, 1
        else:
            self.count += 1
        return label if self.count >= self.frames else "UNKNOWN"
