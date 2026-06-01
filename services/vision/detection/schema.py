from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Detection:
    """A single segmented instance from the YOLO model."""

    label: str
    confidence: float
    # Bounding box in pixel coords (x1, y1, x2, y2).
    box: tuple[int, int, int, int]
    # Normalized centroid (cx, cy) in [0, 1] range, relative to frame size.
    centroid: tuple[float, float]
    # Fraction of the frame area covered by the segmentation mask, in [0, 1].
    area_frac: float

    def summary(self) -> str:
        cx, cy = self.centroid
        return (
            f"{self.label} ({self.confidence:.0%}) "
            f"at ({cx:.2f},{cy:.2f}) covering {self.area_frac:.1%}"
        )


@dataclass
class SceneMetadata:
    """Aggregated YOLO output for one frame. Fed to the VLM as a hint."""

    frame_id: int
    timestamp: float
    width: int
    height: int
    detections: list[Detection] = field(default_factory=list)
    infer_ms: float = 0.0

    @property
    def signature(self) -> str:
        """Coarse fingerprint of the scene: sorted class label + count.

        Used to decide whether the scene changed enough to re-query the VLM.
        Position is bucketed coarsely so small jitter does not trigger a call.
        """
        buckets: dict[str, int] = {}
        for d in self.detections:
            cx, cy = d.centroid
            cell = f"{d.label}:{int(cx * 3)}{int(cy * 3)}"
            buckets[cell] = buckets.get(cell, 0) + 1
        return "|".join(f"{k}={v}" for k, v in sorted(buckets.items()))

    def hint(self) -> str:
        """Compact textual summary handed to the VLM alongside the image."""
        if not self.detections:
            return "No objects detected by the segmenter."
        lines = [d.summary() for d in self.detections]
        return "Segmenter detected:\n- " + "\n- ".join(lines)

    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
            "infer_ms": round(self.infer_ms, 2),
            "signature": self.signature,
            "detections": [
                {
                    "label": d.label,
                    "confidence": round(d.confidence, 4),
                    "box": list(d.box),
                    "centroid": [round(d.centroid[0], 4), round(d.centroid[1], 4)],
                    "area_frac": round(d.area_frac, 4),
                }
                for d in self.detections
            ],
        }


@dataclass
class SceneUnderstanding:
    """Latest VLM interpretation of the scene."""

    frame_id: int
    timestamp: float
    text: str
    latency_ms: float
    based_on_signature: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "text": self.text,
            "latency_ms": round(self.latency_ms, 2),
            "based_on_signature": self.based_on_signature,
            "error": self.error,
        }
