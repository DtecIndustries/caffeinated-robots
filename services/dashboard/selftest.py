"""Smoke test for the web layer — no database needed.

Stubs the db module with the same row shape db.py returns from faulty_parts
(validated live against the caffeinated DB), then drives every route through
FastAPI's TestClient: JSON shapes, the on-hold logic, the line strip, and both
HTML templates.

The "latest-ticket-resolved clears the whole board" rule lives in _FAULTY_SQL
and is verified live against the database, not here (db is stubbed).
"""

from datetime import datetime, timezone

import db
import main

_NOW = datetime(2026, 5, 30, 14, 48, 52, tzinfo=timezone.utc)

# Shape mirrors db._FAULTY_SQL output — only unresolved (on-hold) defects ever
# reach the dashboard.
SEED = [
    {"defect_id": 4, "detected_at": _NOW, "station_pos": 1, "fault": "paint NOK",
     "confidence": 0.88, "status": "ticketed", "station_id": 1,
     "station_name": "intake", "has_image": True},
    {"defect_id": 5, "detected_at": _NOW, "station_pos": 5, "fault": "paint NOK",
     "confidence": None, "status": "open", "station_id": None,
     "station_name": None, "has_image": False},
]

LINE = [
    {"id": 1, "name": "intake", "position": 1, "status": "idle"},
    {"id": 2, "name": "inspection", "position": 2, "status": "idle"},
    {"id": 3, "name": "qc_gate", "position": 3, "status": "idle"},
    {"id": 4, "name": "packaging", "position": 4, "status": "idle"},
    {"id": None, "name": "station 5", "position": 5, "status": "idle"},
]


async def _noop():
    pass


async def _list():
    return list(SEED)


async def _get(did):
    return next((r for r in SEED if r["defect_id"] == did), None)


async def _line():
    return list(LINE)


async def _img_meta(did):
    return None


async def _history():
    return [
        {"defect_id": 2, "detected_at": _NOW, "station_pos": 3, "fault": "paint NOK",
         "resolution": "no_go", "resolution_note": "scrap", "resolved_by": "sven",
         "resolved_at": _NOW, "robot_acked": True, "station_name": "qc_gate", "has_image": True},
        {"defect_id": 1, "detected_at": _NOW, "station_pos": 2, "fault": "paint NOK",
         "resolution": "go", "resolution_note": "false positive", "resolved_by": "sven",
         "resolved_at": _NOW, "robot_acked": False, "station_name": "inspection", "has_image": False},
    ]


async def _summary():
    return {"faulty_count": 2, "awaiting_resolution": 2, "on_hold": True,
            "by_station": {"intake": 1, "station 5": 1},
            "by_severity": {"major": 1, "minor": 1}}


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
    assert s["faulty_count"] == 2 and s["on_hold"] is True, s

    d = c.get("/api/defects").json()
    assert d["count"] == 2 and d["on_hold"] is True, d
    by_id = {x["product_id"]: x for x in d["defects"]}
    assert by_id[4]["defect"] == "paint NOK", by_id[4]
    assert all(x["phase"] == "awaiting_resolution" and x["on_hold"] for x in d["defects"]), d
    assert by_id[4]["severity"] == "major", by_id[4]              # confidence 0.88
    assert by_id[5]["severity"] == "minor", by_id[5]              # no confidence
    assert by_id[5]["station_name"] == "station 5", by_id[5]      # name fallback

    det = c.get("/api/defects/4").json()
    assert "repair" not in det, "mocked repair instructions must be gone"
    assert det["phase"] == "awaiting_resolution" and det["phase_message"], det
    assert det["has_capture"] is False and det["capture_url"] is None, det
    here = [x for x in det["line"] if x["is_here"]]
    assert len(here) == 1 and here[0]["position"] == 1, det["line"]
    assert c.get("/api/defects/999").status_code == 404

    ov = c.get("/")
    assert ov.status_code == 200 and 'id="linestatus"' in ov.text and "Live defect feed" in ov.text

    op = c.get("/operator?product_id=4")
    assert op.status_code == 200 and ">Status<" in op.text and "Repair instructions" not in op.text

print("OK — routes, on-hold logic, line strip, and both templates pass; no mocked repair.")
