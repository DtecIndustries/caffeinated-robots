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
