"""Features for tiny archive images, distinct from the landmark model."""
import cv2
import numpy as np

IMAGE_FEATURE_VERSION = "gray28_resize32_hog16_stride8_cell8_bins9_v1"
HOG = cv2.HOGDescriptor((32, 32), (16, 16), (8, 8), (8, 8), 9)


def image_features(image):
    if image is None or image.size == 0:
        raise ValueError("Empty or unreadable image.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if gray.ndim != 2:
        raise ValueError("Expected grayscale or BGR image.")
    # Match training image resolution even for large webcam crops.
    gray = cv2.resize(gray, (28, 28), interpolation=cv2.INTER_AREA)
    gray = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_LINEAR)
    return HOG.compute(gray).ravel().astype(np.float32)
