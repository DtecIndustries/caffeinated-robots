from dataclasses import dataclass


@dataclass
class Station:
    id: int
    # ROI as normalized coords (0.0–1.0 of frame width/height)
    x1: float
    y1: float
    x2: float
    y2: float


# 4 equal vertical columns across the full frame height.
# Tune these fractions to match your physical setup.
STATIONS: list[Station] = [
    Station(1, 0.25, 0.65, 0.35, 0.85),
    Station(2, 0.40, 0.65, 0.50, 0.85),
    Station(3, 0.55, 0.65, 0.65, 0.85),
    Station(4, 0.71, 0.65, 0.81, 0.85),
]
