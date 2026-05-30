import asyncio
import time
import cv2
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from config import (
    CAMERA_INDEX, CAMERA_URL,
    STREAM_HOST, STREAM_PORT,
    STREAM_WIDTH, STREAM_HEIGHT,
    DETECTION_INTERVAL, DETECTION_RATIO_THRESHOLD,
    DETECTION_BRIGHT_THRESH, DETECTION_RANGE_THRESH,
    DETECTION_CONFIRM_DELAY,
    DB_URL,
)
from camera.capture import Camera
from camera.stream import router as stream_router, set_camera
from detection.detector import BoxDetector
from detection.station import STATION_IDS
import db.sqlite_client as local_db
from db.upstream_sync import sync_loop, notify_change
from db.rules import apply_rules

cam = Camera(CAMERA_URL if CAMERA_URL else CAMERA_INDEX)
detector = BoxDetector(
    ratio_threshold=DETECTION_RATIO_THRESHOLD,
    bright_thresh=DETECTION_BRIGHT_THRESH,
    range_thresh=DETECTION_RANGE_THRESH,
)

station_states:   dict[int, bool] = {sid: False for sid in STATION_IDS}
station_statuses: dict[int, str]  = {sid: ""    for sid in STATION_IDS}
station_colors:   dict[int, str | None] = {sid: None for sid in STATION_IDS}

# Forced overrides set by routine.py via /stations/force.
# None = no override (use CV detection), True/False = forced value.
forced_states: dict[int, bool | None] = {sid: None for sid in STATION_IDS}

# Robot display state — updated by routine.py via POST /robot/state
robot_display = {
    "pose":     "",
    "curr_pos": None,
    "next_pos": None,
    "joints":   [],
}

DB_DEBOUNCE_S = 1.0


async def detection_loop():
    first_seen: dict[int, float | None] = {sid: None for sid in STATION_IDS}
    prev_written:          dict[int, bool] = {}
    prev_written_statuses: dict[int, str]  = {}
    last_write = 0.0

    while True:
        frame = cam.read()
        if frame is not None:
            raw = detector.detect(frame)
            now = time.monotonic()

            confirmed:  dict[int, bool] = {}
            statuses:   dict[int, str]  = {}
            for sid, color in raw.items():
                if forced_states.get(sid) is not None:
                    first_seen[sid] = None
                    confirmed[sid]  = forced_states[sid]
                    statuses[sid]   = ""
                elif color is not None:
                    if first_seen[sid] is None:
                        first_seen[sid] = now
                    present = (now - first_seen[sid]) >= DETECTION_CONFIRM_DELAY
                    confirmed[sid] = present
                    statuses[sid]  = "FAULTY:SURFACE_DAMAGE" if (present and color == "black") else ""
                else:
                    first_seen[sid] = None
                    confirmed[sid]  = False
                    statuses[sid]   = ""

            station_states.update(confirmed)
            station_statuses.update(statuses)
            station_colors.update(raw)

            changed = (confirmed != prev_written) or (statuses != prev_written_statuses)
            if changed and (now - last_write) >= DB_DEBOUNCE_S:
                await asyncio.to_thread(local_db.write_vision, confirmed, statuses)
                notify_change()
                prev_written          = confirmed.copy()
                prev_written_statuses = statuses.copy()
                last_write = now

        await asyncio.sleep(DETECTION_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cam.start()
    local_db.ensure_tables()
    asyncio.create_task(detection_loop())
    asyncio.create_task(sync_loop())
    yield
    cam.stop()


app = FastAPI(lifespan=lifespan)
set_camera(cam)
app.include_router(stream_router)


@app.get("/status")
def status():
    return JSONResponse({
        **{f"station_{k}": v for k, v in station_states.items()},
        **{f"station_{k}_status": v for k, v in station_statuses.items()},
        **{f"station_{k}_forced": forced_states[k] for k in STATION_IDS},
    })


class ForceBody(BaseModel):
    station: int
    value: bool | None  # True/False to force, null to release back to CV


@app.post("/stations/force")
def force_station(body: ForceBody):
    if body.station not in STATION_IDS:
        return JSONResponse({"error": f"unknown station {body.station}"}, status_code=400)
    forced_states[body.station] = body.value
    return JSONResponse({"station": body.station, "forced": body.value})


@app.post("/stations/force/clear")
def clear_all_forces():
    for sid in STATION_IDS:
        forced_states[sid] = None
    return JSONResponse({"cleared": True})


class RobotStateBody(BaseModel):
    pose:     str = ""
    curr_pos: int | None = None
    next_pos: int | None = None
    joints:   list[int] = []


@app.post("/robot/state")
def update_robot_display(body: RobotStateBody):
    robot_display.update(body.model_dump())
    return JSONResponse({"ok": True})


def _draw_hud(frame: cv2.typing.MatLike) -> cv2.typing.MatLike:
    h, w = frame.shape[:2]
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_small = 0.45
    font_large = 0.55
    pad        = 8
    line_h     = 18

    forced_tags = [
        f"P{sid}={'T' if v else 'F'}(forced)" if v is not None else f"P{sid}=cv"
        for sid, v in forced_states.items()
    ]
    joints_str = str(robot_display["joints"]) if robot_display["joints"] else "—"

    lines = [
        ("STATIONS", [
            "  " + "  ".join(
                f"P{sid}:{'FAULTY' if station_statuses[sid] else ('YES' if station_states[sid] else 'NO')}"
                for sid in STATION_IDS
            ),
            "  " + "  ".join(forced_tags),
        ]),
        ("ROBOT", [
            f"  pose:   {robot_display['pose'] or '—'}",
            f"  at:     {robot_display['curr_pos']}   next: {robot_display['next_pos']}",
            f"  joints: {joints_str}",
        ]),
    ]

    total   = sum(1 + len(v) for _, v in lines)
    panel_h = total * line_h + pad * 2

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    y = pad + line_h
    for section, section_lines in lines:
        cv2.putText(frame, section, (pad, y), font, font_large, (180, 180, 180), 1)
        y += line_h
        for text in section_lines:
            cv2.putText(frame, text, (pad, y), font, font_small, (220, 220, 220), 1)
            y += line_h

    return frame


def _debug_frames():
    while True:
        frame = cam.read()
        if frame is None:
            continue
        vision_dict = {
            **{f"pos{sid}_item_present": station_colors[sid] is not None for sid in STATION_IDS},
            **{f"pos{sid}_item_status":  station_statuses[sid] for sid in STATION_IDS},
        }
        calculated = apply_rules(vision_dict, robot_display)
        annotated  = detector.annotated(frame, station_colors, calculated)
        h, w = annotated.shape[:2]
        scale = min(STREAM_WIDTH / w, STREAM_HEIGHT / h)
        annotated = cv2.resize(annotated, (int(w * scale), int(h * scale)))
        annotated = _draw_hud(annotated)
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
