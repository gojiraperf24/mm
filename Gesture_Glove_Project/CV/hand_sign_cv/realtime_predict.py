"""Standalone webcam inference; no glove, Bluetooth or speech dependency."""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import time
import cv2
import joblib
import sklearn
from common import MODEL, ROOT, load_vocabulary
from hand_features import FEATURE_NAMES, FEATURE_VERSION, extract_features
from prediction import PredictionSmoother, classify
from tracking import HandTracker, draw_hands, open_camera, show


def load_model(path, signs_path):
    if not path.is_file():
        raise FileNotFoundError("No trained sign classifier. Collect data, then run python train_model.py.")
    # Pickle/joblib can execute code. Load only a model you trained or trust.
    bundle = joblib.load(path)
    _, digest = load_vocabulary(signs_path)
    if (bundle.get("feature_version") != FEATURE_VERSION
            or bundle.get("feature_names") != FEATURE_NAMES
            or bundle.get("vocabulary_hash") != digest or bundle.get("mirror") is not True):
        raise ValueError("Model/config mismatch. Recollect/retrain after feature or vocabulary changes.")
    if bundle.get("sklearn_version") != sklearn.__version__:
        raise ValueError("scikit-learn version differs from training. Use requirements.txt and retrain.")
    if not 0 <= bundle["threshold"] <= 1:
        raise ValueError("Invalid saved confidence threshold.")
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--signs", type=Path, default=ROOT / "signs.json")
    parser.add_argument("--threshold", type=float, help="Override the saved validation threshold")
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--log", type=Path, help="Optional new CSV file for offline comparison")
    args = parser.parse_args()
    if args.frames < 1 or (args.threshold is not None and not 0 <= args.threshold <= 1):
        parser.error("Use --frames >= 1 and a threshold between 0 and 1.")
    try:
        bundle = load_model(args.model, args.signs)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f"Prediction stopped: {exc}\n")
    threshold = bundle["threshold"] if args.threshold is None else args.threshold
    smoother = PredictionSmoother(args.frames)
    camera, log_file = None, None
    previous_output = None
    try:
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            log_file = args.log.open("x", newline="", encoding="utf-8")
            writer = csv.writer(log_file)
            writer.writerow(["timestamp_utc", "source", "raw_label", "confidence", "accepted_label", "reason", "latency_ms"])
        with HandTracker() as tracker:
            camera = open_camera(args.camera)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames.")
                captured_utc = datetime.now(timezone.utc).isoformat()
                started = time.perf_counter()
                frame = cv2.flip(frame, 1)
                hands = tracker.detect(frame)
                confidence, raw = None, ""
                if not hands:
                    candidate, reason = "NO_SIGN", "no_hand_detected"
                elif len(hands) != 1:
                    candidate, reason = "UNKNOWN", "multiple_hands"
                else:
                    try:
                        features = extract_features(hands[0], frame.shape[1], frame.shape[0])
                        candidate, raw, confidence = classify(bundle["model"], features, threshold)
                        reason = "low_confidence" if candidate == "UNKNOWN" else "classified"
                    except ValueError:
                        candidate, reason = "UNKNOWN", "invalid_landmarks"
                accepted = smoother.update(candidate, time.monotonic())
                if candidate not in ("UNKNOWN", "NO_SIGN") and accepted == "UNKNOWN":
                    reason = "stabilizing"
                latency_ms = (time.perf_counter() - started) * 1000
                if accepted != previous_output:
                    print(f"{captured_utc} | {accepted} | {reason}")
                    previous_output = accepted
                if log_file:
                    writer.writerow([captured_utc, "cv", raw, "" if confidence is None else f"{confidence:.4f}",
                                     accepted, reason, f"{latency_ms:.2f}"])
                    log_file.flush()
                draw_hands(frame, hands)
                score = "N/A" if confidence is None else f"{confidence:.1%}"
                lines = [f"Accepted: {accepted}", f"Raw: {raw or '-'} | Confidence: {score}",
                         f"Threshold: {threshold:.0%} | Stable frames: {min(smoother.count, args.frames)}/{args.frames}",
                         f"{reason} | Processing: {latency_ms:.0f} ms | Q: quit"]
                if show(frame, lines, "Hand sign CV add-on") in (ord("q"), 27):
                    break
    finally:
        if camera is not None:
            camera.release()
        if log_file is not None:
            log_file.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
