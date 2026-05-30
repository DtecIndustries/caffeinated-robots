import cv2
import numpy as np
from detection.station import STATIONS


class BoxDetector:
    def __init__(self, ratio_threshold: float, bright_thresh: int, dark_thresh: int):
        self._ratio_threshold = ratio_threshold
        self._bright_thresh = bright_thresh
        self._dark_thresh = dark_thresh
        # Morphological kernel to remove small noise specks
        self._kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    def _object_mask(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        # White objects: well above the dark grey table
        _, bright = cv2.threshold(blurred, self._bright_thresh, 255, cv2.THRESH_BINARY)
        # Black objects: below the dark grey table
        _, dark = cv2.threshold(blurred, self._dark_thresh, 255, cv2.THRESH_BINARY_INV)
        mask = cv2.bitwise_or(bright, dark)
        # Remove isolated noise pixels while keeping solid objects
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)

    def detect(self, frame: np.ndarray) -> dict[int, bool]:
        h, w = frame.shape[:2]
        mask = self._object_mask(frame)

        results: dict[int, bool] = {}
        for s in STATIONS:
            x1, y1 = int(s.x1 * w), int(s.y1 * h)
            x2, y2 = int(s.x2 * w), int(s.y2 * h)
            roi = mask[y1:y2, x1:x2]
            ratio = np.count_nonzero(roi) / roi.size
            results[s.id] = ratio > self._ratio_threshold

        return results

    def annotated(self, frame: np.ndarray, states: dict[int, bool]) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]
        for s in STATIONS:
            x1, y1 = int(s.x1 * w), int(s.y1 * h)
            x2, y2 = int(s.x2 * w), int(s.y2 * h)
            present = states.get(s.id, False)
            color = (0, 255, 0) if present else (0, 0, 255)
            cv2.rectangle(out, (x1, y1), (x2 - 1, y2 - 1), color, 2)
            cv2.putText(out, f"P{s.id}: {'YES' if present else 'NO'}",
                        (x1 + 6, y1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return out
