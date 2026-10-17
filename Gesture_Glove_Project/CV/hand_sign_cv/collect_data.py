"""Collect labeled landmark features with explicit start/pause controls."""
import argparse
import csv
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import cv2
from common import DATASET, ROOT, ensure_dataset, load_vocabulary, read_dataset
from hand_features import FEATURE_VERSION, extract_features
from tracking import HandTracker, draw_hands, open_camera, show


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant", required=True, help="Pseudonym, e.g. p01")
    parser.add_argument("--session", required=True, help="Recording visit, e.g. day1; keep this ID across labels")
    parser.add_argument("--label", help="Starting label; N/P change it in the window")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--signs", type=Path, default=ROOT / "signs.json")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between saved rows")
    parser.add_argument("--samples", type=int, default=50, help="Rows per recording burst")
    args = parser.parse_args()
    if (args.interval < 0.1 or args.samples < 1 or not args.participant.strip()
            or not args.session.strip()):
        parser.error("Use nonempty IDs, --interval >= 0.1, and --samples >= 1.")
    signs, digest = load_vocabulary(args.signs)
    labels = list(signs)
    if args.label and args.label not in signs:
        parser.error(f"Unknown label. Choose from: {', '.join(labels)}")
    ensure_dataset(args.dataset)
    rows = read_dataset(args.dataset, signs, digest)
    counts = Counter(r["label"] for r in rows
                     if r["participant"] == args.participant and r["session"] == args.session)
    index = labels.index(args.label) if args.label else 0
    recording, ready_at, last_saved, burst_count = False, 0.0, 0.0, 0
    camera = None
    print("Labels:")
    for label, description in signs.items():
        print(f"  {label}: {description}")
    print("SPACE: start/pause (2-second countdown); N/P: next/previous label; Q: quit.")
    try:
        with HandTracker() as tracker, args.dataset.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            camera = open_camera(args.camera)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames. Existing rows are saved.")
                frame = cv2.flip(frame, 1)
                hands = tracker.detect(frame)
                features = None
                status = "Use exactly one visible hand"
                if len(hands) == 1:
                    try:
                        features = extract_features(hands[0], frame.shape[1], frame.shape[0])
                        status = "Hand ready"
                    except ValueError:
                        status = "Invalid landmarks: reposition hand"
                label = labels[index]
                now = time.monotonic()
                if recording and now >= ready_at and now - last_saved >= args.interval and features is not None:
                    writer.writerow([label, args.participant, args.session,
                                     datetime.now(timezone.utc).isoformat(), FEATURE_VERSION, digest,
                                     *[f"{v:.8g}" for v in features]])
                    f.flush()
                    last_saved = now
                    counts[label] += 1
                    burst_count += 1
                    if burst_count >= args.samples:
                        recording = False
                mode = f"RECORDING {burst_count}/{args.samples}" if recording else "PAUSED"
                if recording and now < ready_at:
                    mode = f"Get ready: {ready_at - now:.1f}s"
                draw_hands(frame, hands)
                key = show(frame, [f"Label: {label} | Session rows: {counts[label]}",
                                   f"{mode} | {status}",
                                   "SPACE: record/pause | N/P: label | Q: quit"], "Collect hand signs")
                if key in (ord("q"), 27):
                    break
                if key == ord(" "):
                    recording = not recording
                    if recording:
                        ready_at = time.monotonic() + 2
                        burst_count = 0
                elif key in (ord("n"), ord("p")):
                    index = (index + (1 if key == ord("n") else -1)) % len(labels)
                    recording = False
                    print(f"{labels[index]}: {signs[labels[index]]}")
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
    print(f"Saved to {args.dataset}. Session counts: {dict(counts)}")


if __name__ == "__main__":
    main()
