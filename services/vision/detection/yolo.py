from __future__ import annotations

import time

import cv2
import numpy as np

from detection.schema import Detection, SceneMetadata


class YoloSegmenter:
    """Thin wrapper over an Ultralytics YOLO segmentation model.

    Loads the model onto the configured device (GPU by default) and runs
    instance segmentation on a single BGR frame, returning structured
    metadata rather than raw tensors.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        imgsz: int = 640,
        conf: float = 0.35,
        half: bool = True,
    ):
        # Imported lazily so the rest of the service can import this module
        # without pulling in torch/ultralytics (e.g. for type checking).
        from ultralytics import YOLO

        self.imgsz = imgsz
        self.conf = conf
        self.half = half and device.startswith("cuda")
        self.device = device
        self.model = YOLO(model_path)
        # Warm up so the first real frame is not penalised by lazy CUDA init.
        self.model.to(device)
        self._frame_id = 0

    def infer(self, frame: np.ndarray) -> SceneMetadata:
        h, w = frame.shape[:2]
        start = time.perf_counter()
        results = self.model.predict(
            frame,
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        infer_ms = (time.perf_counter() - start) * 1000.0
        self._frame_id += 1

        meta = SceneMetadata(
            frame_id=self._frame_id,
            timestamp=time.time(),
            width=w,
            height=h,
            infer_ms=infer_ms,
        )

        if not results:
            return meta

        r = results[0]
        names = r.names
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            return meta

        frame_area = float(w * h)
        # Per-instance mask areas, if the model produced masks.
        mask_areas: list[float] = []
        if r.masks is not None and r.masks.data is not None:
            md = r.masks.data  # (n, mh, mw) on device
            # Scale factor between mask resolution and original frame.
            mh, mw = md.shape[-2:]
            scale = frame_area / float(mh * mw)
            mask_areas = [float(m.sum()) * scale for m in md.cpu().numpy()]

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)

        for i in range(len(boxes)):
            x1, y1, x2, y2 = (int(v) for v in xyxy[i])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            if i < len(mask_areas):
                area_frac = mask_areas[i] / frame_area
            else:
                area_frac = ((x2 - x1) * (y2 - y1)) / frame_area
            meta.detections.append(
                Detection(
                    label=str(names.get(clss[i], clss[i])),
                    confidence=float(confs[i]),
                    box=(x1, y1, x2, y2),
                    centroid=(cx, cy),
                    area_frac=float(min(max(area_frac, 0.0), 1.0)),
                )
            )

        # Sort by area so the most prominent objects lead the VLM hint.
        meta.detections.sort(key=lambda d: d.area_frac, reverse=True)
        return meta

    @staticmethod
    def annotate(frame: np.ndarray, meta: SceneMetadata) -> np.ndarray:
        """Draw boxes + labels onto a copy of the frame for the debug stream."""
        out = frame.copy()
        for d in meta.detections:
            x1, y1, x2, y2 = d.box
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            tag = f"{d.label} {d.confidence:.0%}"
            cv2.putText(
                out, tag, (x1, max(0, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA,
            )
        return out
