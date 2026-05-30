import cv2
import threading


class Camera:
    def __init__(self, index: int):
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera {index}")
        self._frame = None
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            ok, frame = self._cap.read()
            if ok:
                with self._lock:
                    self._frame = frame

    def read(self):
        with self._lock:
            return self._frame

    def stop(self):
        self._running = False
        self._cap.release()
