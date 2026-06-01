import threading
import time
import urllib.request

import cv2
import numpy as np


def _is_url(source) -> bool:
    return isinstance(source, str) and source.lower().startswith(
        ("http://", "https://")
    )


def _parse_headers(raw: str | None) -> dict:
    """Parse "Key: Value" lines (newline- or '|'-separated) into a dict."""
    headers: dict[str, str] = {}
    if not raw:
        return headers
    for line in raw.replace("|", "\n").splitlines():
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers


class Camera:
    """Frame source: a local camera index or a remote MJPEG-over-HTTP stream.

    The camera runs on another machine on the wifi and is exposed as an
    `multipart/x-mixed-replace` MJPEG stream over ngrok. OpenCV's FFMPEG
    backend chokes on that (HTTPS + multipart), so for URL sources we read the
    HTTP stream directly, split out the JPEG frames, and decode them with
    OpenCV. HTTP headers (notably `ngrok-skip-browser-warning`, without which
    ngrok-free serves an interstitial) are sent on the request. The reader
    self-heals: if the stream drops it reconnects.
    """

    def __init__(
        self, source, http_headers: str | None = None, reconnect_delay: float = 1.0
    ):
        self._source = (
            int(source) if (isinstance(source, str) and source.isdigit()) else source
        )
        self._is_url = _is_url(self._source)
        self._headers = _parse_headers(http_headers)
        self._reconnect_delay = reconnect_delay
        self._frame = None
        self._lock = threading.Lock()
        self._running = False

        if not self._is_url:
            self._cap = cv2.VideoCapture(self._source)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not self._cap.isOpened():
                raise RuntimeError(f"Cannot open camera {self._source!r}")
        else:
            self._cap = None  # opened lazily in the reader thread

    # ---- lifecycle -------------------------------------------------------

    def start(self):
        self._running = True
        target = self._mjpeg_loop if self._is_url else self._device_loop
        threading.Thread(target=target, daemon=True).start()

    def stop(self):
        self._running = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass

    # ---- local camera ----------------------------------------------------

    def _device_loop(self):
        while self._running:
            ok, frame = self._cap.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.01)

    # ---- remote MJPEG stream --------------------------------------------

    def _mjpeg_loop(self):
        while self._running:
            try:
                self._read_mjpeg()
            except Exception as exc:  # noqa: BLE001
                print(f"[camera] stream error ({exc}); reconnecting...", flush=True)
                time.sleep(self._reconnect_delay)

    def _read_mjpeg(self):
        req = urllib.request.Request(self._source, headers=self._headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            buf = b""
            while self._running:
                chunk = resp.read(8192)
                if not chunk:
                    raise ConnectionError("stream ended")
                buf += chunk
                # Extract complete JPEGs by SOI/EOI markers.
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9", start + 2)
                while start != -1 and end != -1:
                    jpg = buf[start : end + 2]
                    buf = buf[end + 2 :]
                    frame = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                    if frame is not None:
                        with self._lock:
                            self._frame = frame
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2)
                # Guard against unbounded growth on a malformed stream.
                if len(buf) > 8_000_000:
                    buf = b""

    # ---- access ----------------------------------------------------------

    def read(self):
        with self._lock:
            return self._frame
