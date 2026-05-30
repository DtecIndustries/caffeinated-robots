"""Smoke test for the web layer — no database needed.

Stubs the db module with the same row shape Postgres returns (validated live
against the caffeinated DB), then drives every route through FastAPI's
TestClient: JSON shapes, the repair playbook join, and both HTML templates.
"""

from datetime import datetime, timezone

import db
import main

_NOW = datetime(2026, 5, 30, 13, 33, 38, tzinfo=timezone.utc)

SEED = [
    {
        "product_id": 1, "label": "Widget A-1042", "product_status": "rejected",
        "sku": "WA-1042", "batch": "B-2207", "station_id": 2,
        "station_name": "inspection", "station_position": 2,
        "has_failed_detection": True, "failed_at": _NOW, "confidence": 0.94,
        "image_url": "https://picsum.photos/seed/wa1042/480/320",
        "defect_code": "SURF_SCRATCH", "defect": "Surface scratch", "severity": "major",
        "reason": "Surface scratch on top face exceeds 2mm tolerance", "detected_at": _NOW,
    },
    {
        "product_id": 3, "label": "Widget A-1044", "product_status": "in_transit",
        "sku": "WA-1044", "batch": "B-2208", "station_id": 2,
        "station_name": "inspection", "station_position": 2,
        "has_failed_detection": True, "failed_at": _NOW, "confidence": 0.88,
        "image_url": None, "defect_code": "MISALIGN", "defect": "Component misalignment",
        "severity": "minor", "reason": "Left bracket offset by 3.1mm beyond tolerance",
        "detected_at": _NOW,
    },
    {
        "product_id": 2, "label": "Widget A-1043", "product_status": "hold",
        "sku": "WA-1043", "batch": "B-2207", "station_id": 3,
        "station_name": "qc_gate", "station_position": 3,
        "has_failed_detection": False, "failed_at": None, "confidence": None,
        "image_url": None, "defect_code": None, "defect": "", "severity": "",
        "reason": "", "detected_at": _NOW,
    },
]

LINE = [
    {"id": 1, "name": "intake", "position": 1, "status": "idle"},
    {"id": 2, "name": "inspection", "position": 2, "status": "idle"},
    {"id": 3, "name": "qc_gate", "position": 3, "status": "idle"},
    {"id": 4, "name": "packaging", "position": 4, "status": "idle"},
]


async def _noop():
    pass


async def _list():
    return list(SEED)


async def _get(pid):
    return next((r for r in SEED if r["product_id"] == pid), None)


async def _line():
    return list(LINE)


async def _img_meta(pid):
    return None  # no captured image stored -> dashboard hides the capture block


async def _summary():
    return {
        "faulty_count": len(SEED),
        "by_station": {"inspection": 2, "qc_gate": 1},
        "by_severity": {"major": 1, "minor": 1, "other": 1},
    }


db.configured = lambda: True
db.connect = _noop
db.close = _noop
db.list_defects = _list
db.get_defect = _get
db.get_line = _line
db.get_summary = _summary
db.get_defect_image_meta = _img_meta

from fastapi.testclient import TestClient  # noqa: E402

with TestClient(main.app) as c:
    s = c.get("/api/summary").json()
    assert s["faulty_count"] == 3, s

    d = c.get("/api/defects").json()
    assert d["count"] == 3, d
    first = d["defects"][0]
    assert {"product_id", "label", "defect", "severity", "station_name"} <= first.keys()

    # hold part has no detection payload -> defect/severity backfilled from status
    hold = next(x for x in d["defects"] if x["product_id"] == 2)
    assert hold["defect"] == "Held for review" and hold["severity"] == "minor", hold

    det = c.get("/api/defects/1").json()
    assert det["repair"]["est_minutes"] == 4, det["repair"]
    assert any(s["is_here"] for s in det["line"]), det["line"]
    # No image stored -> capture is hidden and the URL is absent.
    assert det["has_capture"] is False and det["capture_url"] is None, det
    assert c.get("/api/defects/999").status_code == 404

    ov = c.get("/")
    assert ov.status_code == 200 and "Live defect feed" in ov.text

    op = c.get("/operator?product_id=1")
    assert op.status_code == 200 and "Repair instructions" in op.text

print("OK — all routes, JSON shapes, and both templates pass.")
