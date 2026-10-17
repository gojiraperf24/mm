"""MediaPipe Tasks webcam adapter; also usable as a tracking-only demo."""
import argparse
import time
import cv2
import mediapipe as mp
import numpy as np
from common import LANDMARK_MODEL

CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7),
               (7, 8), (5, 9), (9, 10), (10, 11), (11, 12), (9, 13),
               (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
               (17, 18), (18, 19), (19, 20)]


class HandTracker:
    def __init__(self, model_path=LANDMARK_MODEL):
        if not model_path.is_file():
            raise FileNotFoundError("Missing hand_landmarker.task. Run python setup_model.py first.")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,  # Detect a second hand so we can reject ambiguous frames.
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6)
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.last_timestamp = -1

    def detect(self, frame):
        timestamp = max(self.last_timestamp + 1, time.monotonic_ns() // 1_000_000)
        self.last_timestamp = timestamp
        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        result = self.detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
        hands = [np.array([[p.x, p.y, p.z] for p in hand]) for hand in result.hand_landmarks]
        return hands

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.detector.close()


def open_camera(index):
    camera = cv2.VideoCapture(index)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Cannot open camera {index}. Close other camera apps, check permissions or try --camera 1.")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera


def draw_hands(frame, hands):
    h, w = frame.shape[:2]
    for hand in hands:
        pixels = [(int(x * w), int(y * h)) for x, y, _ in hand]
        for a, b in CONNECTIONS:
            cv2.line(frame, pixels[a], pixels[b], (100, 220, 80), 2)
        for p in pixels:
            cv2.circle(frame, p, 3, (20, 180, 255), -1)


def show(frame, lines, title):
    # Text panel is separate from the image, so instructions do not hide fingers.
    panel = np.zeros((len(lines) * 27 + 14, frame.shape[1], 3), dtype=np.uint8)
    for i, line in enumerate(lines):
        cv2.putText(panel, line, (10, 25 + 27 * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.52, (240, 240, 240), 1, cv2.LINE_AA)
    cv2.imshow(title, np.vstack([frame, panel]))
    key = cv2.waitKey(1) & 0xFF
    if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
        return ord("q")
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    camera = None
    try:
        with HandTracker() as tracker:
            camera = open_camera(args.camera)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames.")
                frame = cv2.flip(frame, 1)  # Identical mirror policy in every script.
                hands = tracker.detect(frame)
                draw_hands(frame, hands)
                if show(frame, [f"Hands: {len(hands)} | Use exactly one hand | Q: quit"],
                        "Hand tracking") in (ord("q"), 27):
                    break
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
