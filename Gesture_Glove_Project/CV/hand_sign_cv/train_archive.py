"""Audit labeled image folders and train a separate HOG/SVM alphabet baseline.

The supplied Test directory is held out. Training images are split 80/10/10
for SVM fitting, probability calibration and threshold validation.
No joint landmarks, person/session IDs or REST examples are invented.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import cv2
import joblib
import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from common import ROOT
from image_features import IMAGE_FEATURE_VERSION, image_features
from train_model import choose_threshold, rejection_metrics

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def prepare(archive, outdir):
    """Decode and audit all files; deduplicate by exact decoded grayscale pixels."""
    records, all_features = [], []
    for split in ("Train", "Test"):
        for path in sorted((archive / split).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label = path.parent.name
            encoded = path.read_bytes()
            row = {"path": path.relative_to(archive).as_posix(), "source_split": split,
                   "label": label, "filename_label": path.stem.rsplit("_", 1)[-1],
                   "file_sha256": hashlib.sha256(encoded).hexdigest(),
                   "pixel_sha256": "", "width": "", "height": "", "status": "ok"}
            gray = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            feature = None
            if gray is None:
                row["status"] = "unreadable"
            elif row["filename_label"] != label:
                row["status"] = "filename_label_mismatch"
            else:
                h, w = gray.shape
                row.update(width=w, height=h,
                           pixel_sha256=hashlib.sha256(str(gray.shape).encode() + gray.tobytes()).hexdigest())
                feature = image_features(gray)
            records.append(row)
            all_features.append(feature)
            if len(records) % 5000 == 0:
                print(f"Decoded {len(records)} images", flush=True)
    if not records:
        raise ValueError("No images found under Train and Test.")
    labels_by_hash = defaultdict(set)
    for row in records:
        if row["status"] == "ok":
            labels_by_hash[row["pixel_sha256"]].add(row["label"])
    seen = set()
    train_hashes = set()
    for row in records:  # Train rows always precede Test rows.
        if row["status"] != "ok":
            continue
        key = row["pixel_sha256"]
        if len(labels_by_hash[key]) > 1:
            row["status"] = "conflicting_labels_same_pixels"
        elif row["source_split"] == "Test" and key in train_hashes:
            row["status"] = "test_duplicate_of_train"
        elif (row["source_split"], key) in seen:
            row["status"] = "duplicate_within_split"
        else:
            seen.add((row["source_split"], key))
            if row["source_split"] == "Train":
                train_hashes.add(key)
    selected = [i for i, row in enumerate(records) if row["status"] == "ok"]
    if not selected:
        raise ValueError("No usable images remain after audit.")
    x = np.stack([all_features[i] for i in selected])
    valid = [records[i] for i in selected]
    y = np.array([r["label"] for r in valid])
    source = np.array([r["source_split"] for r in valid])
    summary = {
        "total_files": len(records),
        "original_counts": {split: dict(sorted(Counter(r["label"] for r in records if r["source_split"] == split).items()))
                            for split in ("Train", "Test")},
        "dimensions": dict(Counter(f"{r['width']}x{r['height']}" for r in records)),
        "statuses": dict(Counter(r["status"] for r in records)),
        "usable_counts": {split: dict(sorted(Counter(r["label"] for r in valid if r["source_split"] == split).items()))
                          for split in ("Train", "Test")},
        "manifest_digest": hashlib.sha256("\n".join(r["path"] + ":" + r["file_sha256"] for r in records).encode()).hexdigest(),
        "deduplication": "Exact decoded grayscale pixels; near-duplicates/augmentation families cannot be resolved without provenance.",
        "person_or_session_identifiers_available": False,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "archive_audit.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (outdir / "archive_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    np.savez_compressed(outdir / "archive_hog_features.npz", x=x, y=y, source=source,
                        paths=np.array([r["path"] for r in valid]), feature_version=IMAGE_FEATURE_VERSION)
    print("Audit:", summary["statuses"], flush=True)
    return x, y, source, valid, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT.parent / "archive")
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "archive_hog_classifier.pkl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    started = time.perf_counter()
    artifact_dir = ROOT / "dataset" / "archive_training"
    x, y, source, rows, audit = prepare(args.archive, artifact_dir)
    train_source = np.flatnonzero(source == "Train")
    test = np.flatnonzero(source == "Test")
    fit, reserved = train_test_split(train_source, test_size=0.2, stratify=y[train_source], random_state=args.seed)
    calibration, validation = train_test_split(reserved, test_size=0.5, stratify=y[reserved], random_state=args.seed)
    labels = sorted(set(y[fit]))
    for idx in [calibration, validation, test]:
        if set(y[idx]) != set(labels):
            raise ValueError("Every partition must contain every class.")
    partitions = {"fit": fit, "calibration": calibration, "validation": validation, "test": test}
    with (artifact_dir / "archive_partitions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "label", "partition", "pixel_sha256"])
        for name, idx in partitions.items():
            writer.writerows((rows[i]["path"], str(y[i]), name, rows[i]["pixel_sha256"]) for i in idx)
    print("Partitions:", {k: len(v) for k, v in partitions.items()}, flush=True)
    # Fixed, modest baseline settings: no tuning on the supplied Test folder.
    svc = SVC(C=10, kernel="rbf", gamma="scale", class_weight="balanced", cache_size=512)
    print("Fitting SVM on HOG features...", flush=True)
    svc.fit(x[fit], y[fit])
    print("Calibrating confidence using separate training images...", flush=True)
    model = CalibratedClassifierCV(FrozenEstimator(svc), method="sigmoid")
    model.fit(x[calibration], y[calibration])
    print("Selecting rejection threshold on validation images...", flush=True)
    val_prob = model.predict_proba(x[validation])
    threshold, sweep, target_met = choose_threshold(y[validation], model.classes_[val_prob.argmax(axis=1)],
                                                   val_prob.max(axis=1), labels)
    threshold = round(threshold, 2)
    print("Evaluating untouched Test images...", flush=True)
    prob = model.predict_proba(x[test])
    raw = model.classes_[prob.argmax(axis=1)]
    confidence = prob.max(axis=1)
    accepted = np.where(confidence >= threshold, raw, "UNKNOWN")
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "archive": str(args.archive.resolve()),
        "model_kind": "archive_image_hog_svm", "feature_version": IMAGE_FEATURE_VERSION,
        "feature_count": int(x.shape[1]), "labels": labels, "rest_trained": "REST" in labels,
        "seed": args.seed, "svm_parameters": svc.get_params(), "audit": audit,
        "partitions": {name: {"images": len(idx), "counts": dict(sorted(Counter(y[idx]).items()))}
                       for name, idx in partitions.items()},
        "threshold": threshold, "validation_target_met": target_met,
        "validation_threshold_sweep": sweep,
        "test_raw_accuracy": float(accuracy_score(y[test], raw)),
        "test_classification_report": classification_report(y[test], raw, labels=labels, output_dict=True, zero_division=0),
        "test_confusion_matrix": confusion_matrix(y[test], raw, labels=labels).tolist(),
        "test_with_rejection": rejection_metrics(y[test], raw, confidence, threshold, labels),
        "elapsed_seconds": time.perf_counter() - started,
        "limitations": ["Image-folder benchmark, not measured webcam accuracy.",
                        "No REST or unknown-pose examples supplied.",
                        "No subject/session metadata; near-duplicate/source-image leakage is possible.",
                        "Small grayscale archive images did not support the original MediaPipe landmark pipeline."],
        "versions": {"sklearn": sklearn.__version__, "opencv": cv2.__version__, "numpy": np.__version__},
    }
    bundle = {"model": model, "model_kind": report["model_kind"], "feature_version": IMAGE_FEATURE_VERSION,
              "threshold": threshold, "labels": labels, "rest_trained": report["rest_trained"],
              "sklearn_version": sklearn.__version__, "report": report}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.output, compress=3)
    args.output.with_suffix(".metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with args.output.with_suffix(".confusion.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["actual / predicted", *labels])
        writer.writerows([label, *line] for label, line in zip(labels, report["test_confusion_matrix"]))
    with args.output.with_suffix(".predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "actual", "raw", "confidence", "accepted"])
        writer.writerows((rows[i]["path"], y[i], p, float(c), a) for i, p, c, a in zip(test, raw, confidence, accepted))
    # Persist a readable results note alongside the exact machine-readable metrics.
    rejected = report["test_with_rejection"]
    accepted_accuracy = rejected["accepted_accuracy"]
    accepted_text = "N/A" if accepted_accuracy is None else f"{accepted_accuracy:.2%}"
    note = f"""# Archive training results

Trained at {report['created_utc']} using {audit['total_files']:,} supplied images.

- Labels: {', '.join(labels)}. No J, Z or REST examples were supplied.
- Input: 28x28 grayscale images; OpenCV HOG produces {x.shape[1]} edge-pattern features.
- Classifier: RBF SVM, C=10, gamma=scale, balanced class weights.
- Fitting: {len(fit):,}; confidence calibration: {len(calibration):,}; threshold validation: {len(validation):,}; untouched test: {len(test):,} images.
- Test accuracy before rejection: **{report['test_raw_accuracy']:.2%}**.
- Confidence threshold: {threshold:.2f}; accepted coverage: **{rejected['coverage']:.2%}**; accuracy among accepted images: **{accepted_text}**.
- Accuracy over all test images when UNKNOWN counts as an error: {rejected['overall_accuracy_with_rejection']:.2%}.
- Total elapsed training/audit time: {report['elapsed_seconds']:.1f} seconds.

These are scores on this archive, not on a live webcam or new signers. Exact pixel duplicates were excluded where found; related augmentations/near-duplicates cannot be ruled out because source/signer metadata is absent. The model has no learned REST class. The original 83-landmark-feature Random Forest remains a separate pipeline and was not trained with these images.

See the matching metrics JSON, confusion CSV and predictions CSV for the complete results. The audit and exact split assignments are in dataset/archive_training.
"""
    args.output.with_suffix(".report.md").write_text(note, encoding="utf-8")
    print(classification_report(y[test], raw, labels=labels, zero_division=0), flush=True)
    print(json.dumps({"accuracy": report["test_raw_accuracy"], "rejection": rejected,
                      "seconds": report["elapsed_seconds"], "saved": str(args.output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
