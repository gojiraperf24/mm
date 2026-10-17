"""Use the separately trained image model on a picture or experimental webcam crop."""
import argparse
from pathlib import Path
import time
import cv2
import joblib
import sklearn
from common import ROOT
from image_features import IMAGE_FEATURE_VERSION, image_features
from prediction import PredictionSmoother, classify


def load_archive_model(path):
    # As with the landmark classifier, only load trusted locally trained pickles.
    bundle = joblib.load(path)
    if (bundle.get("model_kind") != "archive_image_hog_svm"
            or bundle.get("feature_version") != IMAGE_FEATURE_VERSION):
        raise ValueError("This command needs the archive HOG model, not a landmark model.")
    if bundle.get("sklearn_version") != sklearn.__version__:
        raise ValueError("Use the same scikit-learn version used for training.")
    return bundle


def crop_hand(frame, landmarks):
    """Square box around the detected hand. Its distribution differs from the archive."""
    h, w = frame.shape[:2]
    xy = landmarks[:, :2] * [w, h]
    low, high = xy.min(axis=0), xy.max(axis=0)
    center = (low + high) / 2
    side = max(high - low) * 1.4
    x1, y1 = max(0, int(center[0] - side / 2)), max(0, int(center[1] - side / 2))
    x2, y2 = min(w, int(center[0] + side / 2)), min(h, int(center[1] + side / 2))
    if x2 - x1 < 20 or y2 - y1 < 20:
        raise ValueError("Hand crop too small.")
    return frame[y1:y2, x1:x2], (x1, y1, x2, y2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", type=Path, help="Already cropped hand image")
    mode.add_argument("--camera", type=int, help="Experimental live webcam, e.g. 0")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "archive_hog_classifier.pkl")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--flip-crop", action="store_true", help="Flip the crop if your signing hand faces the opposite way to the archive")
    args = parser.parse_args()
    if args.frames < 1 or (args.threshold is not None and not 0 <= args.threshold <= 1):
        parser.error("Use frames >= 1 and threshold between 0 and 1.")
    bundle = load_archive_model(args.model)
    threshold = bundle["threshold"] if args.threshold is None else args.threshold
    print("Archive letter model; no learned REST class. Webcam accuracy has not been measured.")
    if args.image:
        frame = cv2.imread(str(args.image))
        if frame is None:
            parser.error(f"Cannot read {args.image}")
        if args.flip_crop:
            frame = cv2.flip(frame, 1)
        accepted, raw, score = classify(bundle["model"], image_features(frame), threshold)
        print(f"Prediction: {accepted} | Raw: {raw} | Confidence: {score:.1%} | Threshold: {threshold:.0%}")
        return

    from tracking import HandTracker, open_camera, draw_hands, show
    smoother = PredictionSmoother(args.frames)
    camera = None
    try:
        with HandTracker() as tracker:
            camera = open_camera(args.camera)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames.")
                frame = cv2.flip(frame, 1)
                hands = tracker.detect(frame)
                raw, score, box = "-", None, None
                if not hands:
                    candidate = "NO_SIGN"
                elif len(hands) != 1:
                    candidate = "UNKNOWN"
                else:
                    try:
                        crop, box = crop_hand(frame, hands[0])
                        if args.flip_crop:
                            crop = cv2.flip(crop, 1)
                        candidate, raw, score = classify(bundle["model"], image_features(crop), threshold)
                    except ValueError:
                        candidate = "UNKNOWN"
                accepted = smoother.update(candidate, time.monotonic())
                if box:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 50), 2)
                draw_hands(frame, hands)
                score_text = "N/A" if score is None else f"{score:.1%}"
                if show(frame, ["EXPERIMENTAL archive model | No REST training", f"Accepted: {accepted}",
                                f"Raw: {raw} | Confidence: {score_text} | Q: quit"],
                        "Archive alphabet experiment") in (ord("q"), 27):
                    break
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
