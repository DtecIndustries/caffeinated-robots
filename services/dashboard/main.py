"""Caffeinated Robots — Quality dashboards.

Two templates over one defect rule:
  GET /            Overview / supervisor dashboard — live faulty-part count + feed.
  GET /operator    Operator repair dashboard — what is defect, where on the line,
                   and step-by-step repair instructions for one part.

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
import repair
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


def _shape(row: dict) -> dict:
    """Common defect fields shared by the list and detail responses."""
    return {
        "product_id": row["product_id"],
        "label": row["label"],
        "sku": row.get("sku"),
        "batch": row.get("batch"),
        "product_status": row["product_status"],
        "station_id": row.get("station_id"),
        "station_name": row.get("station_name"),
        "station_position": row.get("station_position"),
        "has_failed_detection": row["has_failed_detection"],
        "defect": row.get("defect") or _status_label(row["product_status"]),
        "defect_code": row.get("defect_code"),
        "severity": row.get("severity") or _status_severity(row["product_status"]),
        "reason": row.get("reason"),
        "confidence": row.get("confidence"),
        "image_url": row.get("image_url"),
        "failed_at": _iso(row.get("failed_at")),
        "detected_at": _iso(row.get("detected_at")),
    }


def _status_label(status: str) -> str:
    return {"rejected": "QC rejected", "hold": "Held for review"}.get(status, "Faulty part")


def _status_severity(status: str) -> str:
    return {"rejected": "major", "hold": "minor"}.get(status, "")


# ---- JSON API ---------------------------------------------------------------

@app.get("/api/summary")
async def api_summary():
    _require_db()
    return await db.get_summary()


@app.get("/api/defects")
async def api_defects():
    _require_db()
    rows = await db.list_defects()
    return {"count": len(rows), "defects": [_shape(r) for r in rows]}


@app.get("/api/defects/{product_id}")
async def api_defect(product_id: int):
    _require_db()
    row = await db.get_defect(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="No faulty part with that id")
    data = _shape(row)
    data["repair"] = repair.lookup(row.get("defect_code"), row.get("station_name"))
    # Surface the camera capture only when one has actually been stored.
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
            "is_here": s["id"] == row.get("station_id"),
        }
        for s in await db.get_line()
    ]
    return data


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
