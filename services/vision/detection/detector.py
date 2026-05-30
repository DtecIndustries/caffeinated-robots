import cv2
import numpy as np
from detection.station import STATIONS

DetectionResult = str | None  # "white" | "black" | None


class BoxDetector:
    def __init__(self, ratio_threshold: float, bright_thresh: int, range_thresh: int):
        self._ratio_threshold = ratio_threshold
        self._bright_thresh   = bright_thresh   # pixels above this = white object
        self._range_thresh    = range_thresh    # min/max grey difference above this = non-white object present
        self._kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    def detect(self, frame: np.ndarray) -> dict[int, DetectionResult]:
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        h, w    = blurred.shape

        _, bright_mask = cv2.threshold(blurred, self._bright_thresh, 255, cv2.THRESH_BINARY)
        bright_mask    = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, self._kernel)

        results: dict[int, DetectionResult] = {}
        for s in STATIONS:
            x1, y1 = int(s.x1 * w), int(s.y1 * h)
            x2, y2 = int(s.x2 * w), int(s.y2 * h)
            size    = (y2 - y1) * (x2 - x1)

            bright_ratio = np.count_nonzero(bright_mask[y1:y2, x1:x2]) / size

            if bright_ratio > self._ratio_threshold:
                # Enough white pixels — good part (always takes priority)
                results[s.id] = "white"
            else:
                roi = blurred[y1:y2, x1:x2]
                grey_range = int(roi.max()) - int(roi.min())
                if grey_range > self._range_thresh:
                    # Grey range is unstable — something is there but not white → faulty
                    results[s.id] = "black"
                else:
                    # Uniform grey — nothing present
                    results[s.id] = None

        return results

    def annotated(
        self,
        frame: np.ndarray,
        results: dict[int, DetectionResult],
        calculated: dict | None = None,
    ) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]
        COLOR = {"white": (0, 255, 0), "black": (0, 100, 255), None: (0, 0, 255)}
        LABEL = {"white": "GOOD",      "black": "FAULTY",       None: "EMPTY"}
        calc = calculated or {}

        for s in STATIONS:
            x1, y1 = int(s.x1 * w), int(s.y1 * h)
            x2, y2 = int(s.x2 * w), int(s.y2 * h)
            res   = results.get(s.id)
            color = COLOR[res]

            present    = bool(calc.get(f"pos{s.id}_item_present"))
            calc_str   = "TRUE" if present else "FALSE"
            label      = f"P{s.id}: {LABEL[res]} | {calc_str}"

            cv2.rectangle(out, (x1, y1), (x2 - 1, y2 - 1), color, 2)
            cv2.putText(out, label,
                        (x1 + 6, y1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return out
