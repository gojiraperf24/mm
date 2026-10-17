"""Paths, vocabulary and strict dataset schema."""
import csv
import hashlib
import json
from pathlib import Path
from hand_features import FEATURE_NAMES, FEATURE_VERSION

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset" / "hand_signs.csv"
MODEL = ROOT / "models" / "hand_sign_classifier.pkl"
LANDMARK_MODEL = ROOT / "models" / "hand_landmarker.task"
COLUMNS = ["label", "participant", "session", "timestamp_utc", "feature_version",
           "vocabulary_hash"] + FEATURE_NAMES


def load_vocabulary(path=ROOT / "signs.json"):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    signs = config["signs"]
    if not isinstance(signs, dict) or "REST" not in signs or len(signs) < 2:
        raise ValueError("signs.json needs a signs object containing REST and target labels.")
    for label, description in signs.items():
        if (not label or not label.isascii() or not label.replace("_", "").isalnum()
                or label != label.upper() or label in {"UNKNOWN", "NO_SIGN"}
                or not isinstance(description, str) or not description.strip()):
            raise ValueError(f"Invalid label/description: {label!r}. Use uppercase ASCII labels.")
    digest = hashlib.sha256(json.dumps(signs, sort_keys=True).encode()).hexdigest()
    return signs, digest


def ensure_dataset(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as f:
            if next(csv.reader(f), None) != COLUMNS:
                raise ValueError("CSV schema differs. Use a new dataset file.")
    else:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUMNS)


def read_dataset(path, signs, vocabulary_hash):
    import numpy as np
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError("Dataset header does not match the feature schema.")
        for line, row in enumerate(reader, 2):
            if (None in row or any(v is None for v in row.values())
                    or row["label"] not in signs or not row["participant"].strip()
                    or not row["session"].strip()
                    or row["feature_version"] != FEATURE_VERSION
                    or row["vocabulary_hash"] != vocabulary_hash):
                raise ValueError(f"Invalid or incompatible metadata at CSV line {line}.")
            try:
                features = np.asarray([float(row[n]) for n in FEATURE_NAMES])
            except ValueError as exc:
                raise ValueError(f"Non-numeric feature at CSV line {line}.") from exc
            if not np.isfinite(features).all():
                raise ValueError(f"Non-finite feature at CSV line {line}.")
            rows.append(row)
    return rows
