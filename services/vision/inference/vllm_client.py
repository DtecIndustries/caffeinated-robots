from __future__ import annotations

import base64
import time

import cv2
import numpy as np
from openai import OpenAI

from detection.schema import SceneMetadata, SceneUnderstanding

DEFAULT_SYSTEM_PROMPT = (
    "You are a real-time scene analyst for a robotics workcell camera. "
    "You receive a single video frame plus a list of objects a segmentation "
    "model already detected. Use the image to verify and enrich that list. "
    "Reply in 1-3 short sentences describing what is happening in the scene, "
    "the state of any work station or object, and anything unusual. "
    "Be concise and factual. Do not speculate beyond what is visible."
)


class VLMClient:
    """Synchronous client for a local vLLM OpenAI-compatible server.

    Encodes a frame as a JPEG data URL and sends it together with the YOLO
    metadata hint as a chat completion request to the Qwen2.5-VL model.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        max_tokens: int = 192,
        temperature: float = 0.2,
        jpeg_max_side: int = 768,
        jpeg_quality: int = 80,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        timeout: float = 60.0,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.jpeg_max_side = jpeg_max_side
        self.jpeg_quality = jpeg_quality
        self.system_prompt = system_prompt

    def _encode_frame(self, frame: np.ndarray) -> str:
        h, w = frame.shape[:2]
        scale = self.jpeg_max_side / float(max(h, w))
        if scale < 1.0:
            frame = cv2.resize(
                frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
            )
        ok, buf = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        )
        if not ok:
            raise RuntimeError("Failed to JPEG-encode frame for VLM")
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def describe(self, frame: np.ndarray, meta: SceneMetadata) -> SceneUnderstanding:
        data_url = self._encode_frame(frame)
        prompt = (
            f"{meta.hint()}\n\n"
            "Describe the current scene and the state of the detected objects."
        )
        start = time.perf_counter()
        error = None
        text = ""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    },
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - surface any backend failure
            error = f"{type(exc).__name__}: {exc}"

        latency_ms = (time.perf_counter() - start) * 1000.0
        return SceneUnderstanding(
            frame_id=meta.frame_id,
            timestamp=time.time(),
            text=text,
            latency_ms=latency_ms,
            based_on_signature=meta.signature,
            error=error,
        )

    def healthy(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
