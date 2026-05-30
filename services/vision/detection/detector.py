import cv2
import numpy as np
from detection.station import STATIONS


class BoxDetector:
    def __init__(self, threshold: float):
        # MOG2 learns the static background (conveyor belt) over ~200 frames,
        # then flags anything that appears on top as foreground.
        self._bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=40)
        self._threshold = threshold

    def detect(self, frame: np.ndarray) -> dict[int, bool]:
        h, w = frame.shape[:2]
        fg_mask = self._bg.apply(frame)

        results: dict[int, bool] = {}
        for s in STATIONS:
            x1, y1 = int(s.x1 * w), int(s.y1 * h)
            x2, y2 = int(s.x2 * w), int(s.y2 * h)
            roi = fg_mask[y1:y2, x1:x2]
            ratio = np.count_nonzero(roi) / roi.size
            results[s.id] = ratio > self._threshold

        return results

    def annotated(self, frame: np.ndarray, states: dict[int, bool]) -> np.ndarray:
        """Return a copy of the frame with ROIs and states drawn on it (useful for debug stream)."""
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
