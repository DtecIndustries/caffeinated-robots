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


def _severity(row: dict) -> str:
    """High-confidence detections are flagged major, the rest minor."""
    c = row.get("confidence")
    return "major" if (c is not None and c >= 0.85) else "minor"


def _shape(row: dict) -> dict:
    """Map a faulty_parts row to the dashboard's defect contract.

    `product_id` carries the faulty_parts id so the existing dashboard links
    (/operator?product_id=…) and image route keep working unchanged.
    """
    fault = row.get("fault") or "faulty part"
    return {
        "product_id": row["defect_id"],
        "label": f"Faulty part #{row['defect_id']}",
        "sku": None,
        "batch": None,
        "product_status": row["status"],
        "station_id": row.get("station_id"),
        "station_name": row.get("station_name") or f"station {row['station_pos']}",
        "station_position": row.get("station_pos"),
        "has_failed_detection": True,
        "defect": fault,
        "defect_code": fault.strip().lower(),
        "severity": _severity(row),
        "reason": f"Automated inspection flagged this part as “{fault}”.",
        "confidence": row.get("confidence"),
        "image_url": None,
        "failed_at": _iso(row.get("detected_at")),
        "detected_at": _iso(row.get("detected_at")),
    }


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
    data["repair"] = repair.lookup(data["defect_code"], data["station_name"])
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
