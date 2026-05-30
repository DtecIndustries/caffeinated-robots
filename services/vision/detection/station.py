from dataclasses import dataclass


@dataclass
class Station:
    id: int
    # ROI as normalized coords (0.0–1.0 of frame width/height)
    x1: float
    y1: float
    x2: float
    y2: float


# Tune these fractions to match your physical setup.
# All coords are normalized (0.0–1.0 of frame width/height): x1, y1, x2, y2
STATIONS: list[Station] = [
    Station(1, 0.25, 0.65, 0.35, 0.85),
    Station(2, 0.40, 0.65, 0.50, 0.85),
    Station(3, 0.55, 0.65, 0.65, 0.85),
    Station(4, 0.71, 0.65, 0.81, 0.85),
    Station(5, 0.61, 0.30, 0.70, 0.48),
]

STATION_IDS = [s.id for s in STATIONS]
STATION_BY_ID: dict[int, Station] = {s.id: s for s in STATIONS}


def crop_roi(frame, station_id: int, padding: float = 0.1):
    """Crop a frame to a station's ROI with optional padding on all sides (normalized)."""
    s = STATION_BY_ID.get(station_id)
    if s is None:
        return frame
    h, w = frame.shape[:2]
    pw = (s.x2 - s.x1) * padding
    ph = (s.y2 - s.y1) * padding
    x1 = max(0, int((s.x1 - pw) * w))
    y1 = max(0, int((s.y1 - ph) * h))
    x2 = min(w, int((s.x2 + pw) * w))
    y2 = min(h, int((s.y2 + ph) * h))
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size else frame
