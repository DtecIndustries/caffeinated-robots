import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from camera.capture import Camera

router = APIRouter()
_camera: Camera | None = None


def set_camera(cam: Camera):
    global _camera
    _camera = cam


def _generate():
    while True:
        frame = _camera.read()
        if frame is None:
            continue
        _, buf = cv2.imencode(".jpg", frame)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )


@router.get("/stream")
def mjpeg_stream():
    return StreamingResponse(
        _generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
