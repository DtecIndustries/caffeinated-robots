from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from camera.capture import Camera
from detection.schema import SceneMetadata, SceneUnderstanding
from detection.yolo import YoloSegmenter
from inference.vllm_client import VLMClient


class InferencePipeline:
    """Real-time YOLO-gated VLM pipeline.

    A YOLO thread segments every (Nth) frame from the camera and keeps the
    latest metadata + annotated frame. A separate VLM thread watches the
    scene signature and re-queries the Qwen VLM only when the scene changes
    or a heartbeat interval elapses, so the heavy model fires sparingly while
    YOLO stays real-time. Both models share the single 8 GB GPU.
    """

    def __init__(
        self,
        camera: Camera,
        segmenter: YoloSegmenter,
        vlm: VLMClient,
        yolo_every_n: int = 1,
        vlm_min_interval_s: float = 2.0,
        vlm_heartbeat_s: float = 15.0,
        enable_vlm: bool = True,
    ):
        self.camera = camera
        self.segmenter = segmenter
        self.vlm = vlm
        self.yolo_every_n = max(1, yolo_every_n)
        self.vlm_min_interval_s = vlm_min_interval_s
        self.vlm_heartbeat_s = vlm_heartbeat_s
        self.enable_vlm = enable_vlm

        self._running = False
        self._lock = threading.Lock()
        self._yolo_thread: Optional[threading.Thread] = None
        self._vlm_thread: Optional[threading.Thread] = None

        # Shared state (guarded by _lock).
        self._latest_meta: Optional[SceneMetadata] = None
        self._latest_annotated: Optional[np.ndarray] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_scene: Optional[SceneUnderstanding] = None

        # Gate bookkeeping (VLM thread only).
        self._last_vlm_sig: Optional[str] = None
        self._last_vlm_time = 0.0
        self._vlm_busy = False

    # ---- lifecycle -------------------------------------------------------

    def start(self):
        if self._running:
            return
        self._running = True
        self._yolo_thread = threading.Thread(target=self._yolo_loop, daemon=True)
        self._yolo_thread.start()
        if self.enable_vlm:
            self._vlm_thread = threading.Thread(target=self._vlm_loop, daemon=True)
            self._vlm_thread.start()

    def stop(self):
        self._running = False
        for t in (self._yolo_thread, self._vlm_thread):
            if t is not None:
                t.join(timeout=2.0)

    # ---- worker loops ----------------------------------------------------

    def _yolo_loop(self):
        frame_count = 0
        while self._running:
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.01)
                continue
            frame_count += 1
            if frame_count % self.yolo_every_n != 0:
                time.sleep(0.001)
                continue
            try:
                meta = self.segmenter.infer(frame)
                annotated = self.segmenter.annotate(frame, meta)
            except Exception as exc:  # noqa: BLE001
                # Keep the loop alive; surface the issue on next scene query.
                print(f"[pipeline] YOLO inference error: {exc}", flush=True)
                time.sleep(0.05)
                continue
            with self._lock:
                self._latest_meta = meta
                self._latest_annotated = annotated
                self._latest_frame = frame

    def _vlm_loop(self):
        while self._running:
            time.sleep(0.1)
            with self._lock:
                meta = self._latest_meta
                frame = self._latest_frame
            if meta is None or frame is None:
                continue
            if not self._should_query(meta):
                continue

            self._vlm_busy = True
            scene = self.vlm.describe(frame, meta)
            self._vlm_busy = False

            self._last_vlm_sig = meta.signature
            self._last_vlm_time = time.time()
            with self._lock:
                self._latest_scene = scene

    def _should_query(self, meta: SceneMetadata) -> bool:
        if self._vlm_busy:
            return False
        now = time.time()
        elapsed = now - self._last_vlm_time
        if elapsed < self.vlm_min_interval_s:
            return False
        changed = meta.signature != self._last_vlm_sig
        heartbeat = elapsed >= self.vlm_heartbeat_s
        return changed or heartbeat

    # ---- accessors -------------------------------------------------------

    def latest_metadata(self) -> Optional[SceneMetadata]:
        with self._lock:
            return self._latest_meta

    def latest_scene(self) -> Optional[SceneUnderstanding]:
        with self._lock:
            return self._latest_scene

    def latest_annotated(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._latest_annotated is None else self._latest_annotated

    def status(self) -> dict:
        with self._lock:
            meta = self._latest_meta
            scene = self._latest_scene
        return {
            "running": self._running,
            "vlm_enabled": self.enable_vlm,
            "vlm_busy": self._vlm_busy,
            "frames_processed": meta.frame_id if meta else 0,
            "last_yolo_ms": round(meta.infer_ms, 2) if meta else None,
            "last_scene_age_s": (
                round(time.time() - scene.timestamp, 2) if scene else None
            ),
        }
