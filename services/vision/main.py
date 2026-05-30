import asyncio
import time
import cv2
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from config import (
    CAMERA_INDEX, CAMERA_URL,
    STREAM_HOST, STREAM_PORT,
    STREAM_WIDTH, STREAM_HEIGHT,
    DETECTION_INTERVAL, DETECTION_RATIO_THRESHOLD,
    DETECTION_BRIGHT_THRESH, DETECTION_DARK_THRESH,
    DB_URL,
)
from camera.capture import Camera
from camera.stream import router as stream_router, set_camera
from detection.detector import BoxDetector
from db.sodastraw_client import StationWriter

cam = Camera(CAMERA_URL if CAMERA_URL else CAMERA_INDEX)
detector = BoxDetector(
    ratio_threshold=DETECTION_RATIO_THRESHOLD,
    bright_thresh=DETECTION_BRIGHT_THRESH,
    dark_thresh=DETECTION_DARK_THRESH,
)
writer = StationWriter()

# Shared state — last known station booleans
station_states: dict[int, bool] = {1: False, 2: False, 3: False, 4: False}


DB_DEBOUNCE_S = 1.0

async def detection_loop():
    prev_written: dict[int, bool] = {}
    last_write = 0.0
    while True:
        frame = cam.read()
        if frame is not None:
            states = detector.detect(frame)
            station_states.update(states)
            now = time.monotonic()
            if DB_URL and states != prev_written and (now - last_write) >= DB_DEBOUNCE_S:
                await writer.write(states)
                prev_written = states.copy()
                last_write = now
        await asyncio.sleep(DETECTION_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cam.start()
    if DB_URL:
        await writer.connect()
    asyncio.create_task(detection_loop())
    yield
    cam.stop()
    await writer.close()


app = FastAPI(lifespan=lifespan)
set_camera(cam)
app.include_router(stream_router)


@app.get("/status")
def status():
    return JSONResponse({f"station_{k}": v for k, v in station_states.items()})


def _debug_frames():
    while True:
        frame = cam.read()
        if frame is None:
            continue
        annotated = detector.annotated(frame, station_states)
        h, w = annotated.shape[:2]
        scale = min(STREAM_WIDTH / w, STREAM_HEIGHT / h)
        annotated = cv2.resize(annotated, (int(w * scale), int(h * scale)))
        _, buf = cv2.imencode(".jpg", annotated)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )


@app.get("/debug")
def debug_stream():
    return StreamingResponse(
        _debug_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host=STREAM_HOST, port=STREAM_PORT, reload=False)
