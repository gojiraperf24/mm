"""One feature definition shared by collection, training and prediction."""
from itertools import combinations
import numpy as np

FEATURE_VERSION = "wrist_palm_scale_aspect_v1"
TIP_PAIRS = list(combinations([4, 8, 12, 16, 20], 2))
JOINTS = [(1, 2, 3), (2, 3, 4), (5, 6, 7), (6, 7, 8),
          (9, 10, 11), (10, 11, 12), (13, 14, 15), (14, 15, 16),
          (17, 18, 19), (18, 19, 20)]
FEATURE_NAMES = ([f"lm{i}_{axis}" for i in range(21) for axis in "xyz"]
                 + [f"distance_{a}_{b}" for a, b in TIP_PAIRS]
                 + [f"cosine_{a}_{b}_{c}" for a, b, c in JOINTS])


def normalize_landmarks(landmarks, width, height):
    """Return 21x3 wrist-relative, palm-scaled points; preserve orientation.

    MediaPipe x/z use image-width units; y uses image-height units.
    Convert to a common scale before computing lengths. Depth is approximate.
    """
    points = np.asarray(landmarks, dtype=np.float64)
    if points.shape != (21, 3) or not np.isfinite(points).all():
        raise ValueError("Expected 21 finite (x, y, z) landmarks.")
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")
    points = points * [width, height, width]
    points -= points[0].copy()
    scale = np.mean(np.linalg.norm(points[[5, 9, 13, 17]], axis=1))
    if scale < 1e-6:
        raise ValueError("Degenerate palm: landmarks cannot be normalized.")
    return points / scale


def extract_features(landmarks, width, height):
    """83 features: 63 coordinates, 10 tip distances, 10 joint cosines."""
    p = normalize_landmarks(landmarks, width, height)
    distances = [np.linalg.norm(p[a] - p[b]) for a, b in TIP_PAIRS]
    cosines = []
    for a, b, c in JOINTS:
        u, v = p[a] - p[b], p[c] - p[b]
        denom = np.linalg.norm(u) * np.linalg.norm(v)
        if denom < 1e-8:
            raise ValueError("Collapsed finger joint: skip this frame.")
        cosines.append(np.clip(np.dot(u, v) / denom, -1, 1))
    return np.concatenate([p.ravel(), distances, cosines]).astype(np.float32)
