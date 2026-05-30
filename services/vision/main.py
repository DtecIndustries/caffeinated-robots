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
    DETECTION_CONFIRM_DELAY,
    DB_URL,
)
from camera.capture import Camera
from camera.stream import router as stream_router, set_camera
from detection.detector import BoxDetector
from detection.station import STATION_IDS
from db.sodastraw_client import StationWriter

cam = Camera(CAMERA_URL if CAMERA_URL else CAMERA_INDEX)
detector = BoxDetector(
    ratio_threshold=DETECTION_RATIO_THRESHOLD,
    bright_thresh=DETECTION_BRIGHT_THRESH,
    dark_thresh=DETECTION_DARK_THRESH,
)
writer = StationWriter()

# Shared state — derived from STATIONS, no hardcoding
station_states: dict[int, bool] = {sid: False for sid in STATION_IDS}


DB_DEBOUNCE_S = 1.0

async def detection_loop():
    first_seen: dict[int, float | None] = {sid: None for sid in STATION_IDS}
    prev_written: dict[int, bool] = {}
    last_write = 0.0

    while True:
        frame = cam.read()
        if frame is not None:
            raw = detector.detect(frame)
            now = time.monotonic()

            confirmed: dict[int, bool] = {}
            for sid, detected in raw.items():
                if detected:
                    if first_seen[sid] is None:
                        first_seen[sid] = now
                    confirmed[sid] = (now - first_seen[sid]) >= DETECTION_CONFIRM_DELAY
                else:
                    first_seen[sid] = None
                    confirmed[sid] = False

            station_states.update(confirmed)

            if DB_URL and confirmed != prev_written and (now - last_write) >= DB_DEBOUNCE_S:
                await writer.write(confirmed)
                prev_written = confirmed.copy()
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
