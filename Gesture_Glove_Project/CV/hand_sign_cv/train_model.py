"""Train a Random Forest with separate grouped train/validation/test sets."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from common import DATASET, MODEL, ROOT, load_vocabulary, read_dataset
from hand_features import FEATURE_NAMES, FEATURE_VERSION


def grouped_split(y, groups, seed=42):
    """Choose a reproducible split with every label in each partition.

    Search uses only labels/group coverage, never model scores or features.
    Fractions refer to groups, so frame fractions may differ.
    """
    labels = set(y)
    for label in labels:
        if len(set(groups[y == label])) < 3:
            raise ValueError(f"{label} needs at least 3 distinct groups; aim for 5+ full sessions.")
    outer = GroupShuffleSplit(n_splits=100, test_size=0.2, random_state=seed)
    for remaining, test in outer.split(y, y, groups):
        if set(y[test]) != labels or set(y[remaining]) != labels:
            continue
        inner = GroupShuffleSplit(n_splits=100, test_size=0.25, random_state=seed + 1)
        for train_local, val_local in inner.split(y[remaining], y[remaining], groups[remaining]):
            train, val = remaining[train_local], remaining[val_local]
            if set(y[train]) == labels and set(y[val]) == labels:
                return train, val, test
    raise ValueError("No split covers every class. Record every label including REST in more complete sessions.")


def rejection_metrics(y, raw, confidence, threshold, labels):
    keep = confidence >= threshold
    accepted = np.where(keep, raw, "UNKNOWN")
    return {
        "threshold": float(threshold),
        "coverage": float(np.mean(keep)),
        "accepted_accuracy": float(np.mean(raw[keep] == y[keep])) if keep.any() else None,
        "overall_accuracy_with_rejection": float(np.mean(accepted == y)),
        "macro_f1_with_rejection": float(f1_score(y, accepted, labels=labels, average="macro", zero_division=0)),
    }


def choose_threshold(y, raw, confidence, labels, target=0.95):
    table = [rejection_metrics(y, raw, confidence, t, labels)
             for t in np.arange(0.50, 0.951, 0.05)]
    # Require meaningful coverage instead of accepting one easy sample.
    eligible = [r for r in table if r["coverage"] >= 0.5
                and (r["accepted_accuracy"] or 0) >= target]
    if eligible:
        selected = max(eligible, key=lambda r: (r["coverage"], r["threshold"]))
    else:
        selected = max(table, key=lambda r: (r["macro_f1_with_rejection"], r["coverage"], r["threshold"]))
    return selected["threshold"], table, bool(eligible)


def train(dataset, output, signs_path=ROOT / "signs.json", group_by="session", seed=42, threshold=None):
    signs, digest = load_vocabulary(signs_path)
    rows = read_dataset(dataset, signs, digest)
    if not rows:
        raise ValueError("Dataset is empty. Collect your own examples with collect_data.py first.")
    y = np.array([r["label"] for r in rows])
    labels = sorted(signs)
    missing = set(labels) - set(y)
    if missing:
        raise ValueError(f"No samples for: {', '.join(sorted(missing))}.")
    counts = Counter(y)
    if min(counts.values()) < 15:
        raise ValueError("Need at least 15 rows per class; aim for 200-500 varied rows per class.")
    x = np.array([[float(r[n]) for n in FEATURE_NAMES] for r in rows], dtype=np.float32)
    # JSON avoids collisions between participant/session strings.
    groups = np.array([r["participant"] if group_by == "participant" else
                       json.dumps([r["participant"], r["session"]]) for r in rows])
    train_idx, val_idx, test_idx = grouped_split(y, groups, seed)
    model = RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                                   class_weight="balanced", random_state=seed, n_jobs=-1)
    model.fit(x[train_idx], y[train_idx])
    val_prob = model.predict_proba(x[val_idx])
    val_raw = model.classes_[np.argmax(val_prob, axis=1)]
    selected, threshold_table, target_met = choose_threshold(
        y[val_idx], val_raw, val_prob.max(axis=1), labels)
    if threshold is not None:
        selected = threshold
    test_prob = model.predict_proba(x[test_idx])
    test_raw = model.classes_[np.argmax(test_prob, axis=1)]
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(Path(dataset).read_bytes()).hexdigest(),
        "group_by": group_by, "seed": seed, "labels": labels,
        "class_counts": {k: int(v) for k, v in counts.items()},
        "partitions": {name: {"rows": len(idx), "groups": sorted(set(groups[idx])),
                               "class_counts": dict(Counter(y[idx]))}
                       for name, idx in [("train", train_idx), ("validation", val_idx), ("test", test_idx)]},
        "threshold": selected,
        "threshold_source": "explicit_argument" if threshold is not None else "validation",
        "validation_target_met_by_search": target_met,
        "validation_threshold_sweep": threshold_table,
        "test_raw_accuracy": float(accuracy_score(y[test_idx], test_raw)),
        "test_classification_report": classification_report(y[test_idx], test_raw, labels=labels,
                                                              output_dict=True, zero_division=0),
        "test_confusion_matrix": confusion_matrix(y[test_idx], test_raw, labels=labels).tolist(),
        "test_with_rejection": rejection_metrics(y[test_idx], test_raw, test_prob.max(axis=1), selected, labels),
        "limitations": "Frame metrics for known classes only; smoothing, NO_SIGN and unseen-pose rejection require live trials.",
    }
    bundle = {"model": model, "feature_version": FEATURE_VERSION, "feature_names": FEATURE_NAMES,
              "vocabulary_hash": digest, "signs": signs, "threshold": selected,
              "sklearn_version": sklearn.__version__, "created_utc": report["created_utc"],
              "mirror": True, "report": report}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output)
    output.with_suffix(".metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    import csv
    with output.with_suffix(".confusion.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["actual / predicted", *labels])
        for label, row in zip(labels, report["test_confusion_matrix"]):
            writer.writerow([label, *row])
    print(classification_report(y[test_idx], test_raw, labels=labels, zero_division=0))
    print("Threshold:", round(selected, 2), "| Test rejection metrics:", report["test_with_rejection"])
    if not target_met and threshold is None:
        print("Validation did not reach 95% accepted accuracy at >=50% coverage. Improve data before the demo.")
    print(f"Saved {output}. The saved model is the evaluated train-only model; no test-set refit.")
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=MODEL)
    parser.add_argument("--signs", type=Path, default=ROOT / "signs.json")
    parser.add_argument("--group-by", choices=["session", "participant"], default="session")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, help="Optional fixed threshold instead of validation selection")
    args = parser.parse_args()
    if args.threshold is not None and not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1.")
    try:
        train(args.dataset, args.output, args.signs, args.group_by, args.seed, args.threshold)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f"Training stopped: {exc}\n")


if __name__ == "__main__":
    main()
