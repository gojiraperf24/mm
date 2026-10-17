"""Download Google's pretrained landmark detector (not your sign classifier)."""
import hashlib
import urllib.request
from common import LANDMARK_MODEL

URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main():
    LANDMARK_MODEL.parent.mkdir(parents=True, exist_ok=True)
    if not LANDMARK_MODEL.exists():
        temporary = LANDMARK_MODEL.with_suffix(".download")
        try:
            with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as f:
                while chunk := response.read(1024 * 1024):
                    f.write(chunk)
            if temporary.stat().st_size < 1_000_000:
                raise RuntimeError("Download is unexpectedly small; model not installed.")
            temporary.replace(LANDMARK_MODEL)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Landmark detector: {LANDMARK_MODEL}")
    print("SHA256:", hashlib.sha256(LANDMARK_MODEL.read_bytes()).hexdigest())
    print("Run python tracking.py to test the webcam.")


if __name__ == "__main__":
    main()
