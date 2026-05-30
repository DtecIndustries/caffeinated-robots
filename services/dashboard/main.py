"""Caffeinated Robots — Quality dashboards.

Two templates over the live faulty_parts state:
  GET /            Overview — line status (ON HOLD / clear) + live defect feed.
  GET /operator    Operator view — what is defective, where on the line, the
                   camera capture, and the current state / required action.

A defect is on the line while it's unresolved (or NO-GO pending robot removal);
it drops off once it's a GO (false positive), the robot has handled it, or it no
longer exists.

JSON API (polled by the browsers):
  GET /api/summary
  GET /api/defects
  GET /api/defects/{product_id}
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

import db
from config import HOST, POLL_INTERVAL_MS, PORT

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if db.configured():
        await db.connect()
    yield
    if db.configured():
        await db.close()


app = FastAPI(title="Caffeinated Robots — Quality Dashboards", lifespan=lifespan)


def _require_db():
    if not db.configured():
        raise HTTPException(
            status_code=503,
            detail="DB_URL is not configured. Set it in services/dashboard/.env",
        )


def _iso(dt):
    return dt.isoformat() if dt else None


def _severity(row: dict) -> str:
    """High-confidence detections are flagged major, the rest minor."""
    c = row.get("confidence")
    return "major" if (c is not None and c >= 0.85) else "minor"


def _shape(row: dict) -> dict:
    """Map a faulty_parts row to the dashboard's defect contract.

    Everything reaching the dashboard is an unresolved ticket — i.e. a part the
    line is on hold for, awaiting the supervisor's GO / NO-GO decision in
    Discord. (GO, NO-GO and latest-ticket-resolved all clear the line.)

    `product_id` carries the faulty_parts id so the dashboard links
    (/operator?product_id=…) and the image route stay stable.
    """
    return {
        "product_id": row["defect_id"],
        "label": f"Part #{row['defect_id']}",
        "defect": row.get("fault") or "paint NOK",
        "severity": _severity(row),
        "station_id": row.get("station_id"),
        "station_name": row.get("station_name") or f"station {row['station_pos']}",
        "station_position": row.get("station_pos"),
        "confidence": row.get("confidence"),
        "status": row.get("status"),
        "detected_at": _iso(row.get("detected_at")),
        "phase": "awaiting_resolution",
        "phase_label": "Awaiting resolution",
        "phase_message": "⏸ LINE ON HOLD — waiting for the supervisor's GO / NO-GO "
                         "decision in Discord.",
        "on_hold": True,
    }


# ---- JSON API ---------------------------------------------------------------

@app.get("/api/summary")
async def api_summary():
    _require_db()
    return await db.get_summary()


@app.get("/api/defects")
async def api_defects():
    _require_db()
    defects = [_shape(r) for r in await db.list_defects()]
    return {
        "count": len(defects),
        "on_hold": any(d["on_hold"] for d in defects),
        "defects": defects,
    }


@app.get("/api/defects/{product_id}")
async def api_defect(product_id: int):
    _require_db()
    row = await db.get_defect(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="No faulty part with that id")
    data = _shape(row)
    # Surface the camera capture only when a real image has actually been stored.
    capture = await db.get_defect_image_meta(product_id)
    data["has_capture"] = capture is not None
    data["capture_url"] = f"/api/defects/{product_id}/image" if capture else None
    data["captured_at"] = _iso(capture["captured_at"]) if capture else None
    data["line"] = [
        {
            "id": s["id"],
            "name": s["name"],
            "position": s["position"],
            "status": s["status"],
            "is_here": s["position"] == row.get("station_pos"),
        }
        for s in await db.get_line()
    ]
    return data


@app.get("/api/history")
async def api_history():
    _require_db()
    rows = await db.list_history()
    out = []
    for r in rows:
        res = r.get("resolution")
        out.append({
            "product_id": r["defect_id"],
            "defect": r.get("fault") or "paint NOK",
            "station_name": r.get("station_name") or f"station {r['station_pos']}",
            "station_position": r.get("station_pos"),
            "resolution": res,
            "outcome": "GO — continued" if res == "go" else "NO-GO — removed",
            "resolution_note": r.get("resolution_note") or "",
            "resolved_by": r.get("resolved_by") or "",
            "resolved_at": _iso(r.get("resolved_at")),
            "detected_at": _iso(r.get("detected_at")),
            "robot_acked": r.get("robot_acked"),
            "has_capture": r.get("has_image"),
            "capture_url": f"/api/defects/{r['defect_id']}/image" if r.get("has_image") else None,
        })
    return {"count": len(out), "history": out}


@app.get("/api/defects/{product_id}/image")
async def api_defect_image(product_id: int):
    _require_db()
    img = await db.get_defect_image(product_id)
    if not img:
        raise HTTPException(status_code=404, detail="No captured image for that part")
    data, content_type = img
    return Response(content=data, media_type=content_type)


@app.exception_handler(HTTPException)
async def _http_exc(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


# ---- HTML dashboards --------------------------------------------------------

@app.get("/")
async def overview(request: Request):
    return templates.TemplateResponse(
        request, "overview.html", {"poll_ms": POLL_INTERVAL_MS}
    )


@app.get("/operator")
async def operator(request: Request, product_id: int | None = None):
    return templates.TemplateResponse(
        request,
        "operator.html",
        {"poll_ms": POLL_INTERVAL_MS, "product_id": product_id},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
