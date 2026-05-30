"""Smoke test for the web layer — no database needed.

Stubs the db module with the same row shape db.py returns from faulty_parts
(validated live against the caffeinated DB), then drives every route through
FastAPI's TestClient: JSON shapes, the repair playbook lookup, the line strip,
and both HTML templates.
"""

from datetime import datetime, timezone

import db
import main

_NOW = datetime(2026, 5, 30, 14, 48, 52, tzinfo=timezone.utc)

# Shape mirrors db._FAULTY_SQL output.
SEED = [
    {"defect_id": 4, "detected_at": _NOW, "station_pos": 1, "fault": "bad paint",
     "confidence": 0.88, "status": "ticketed", "station_id": 1,
     "station_name": "intake", "has_image": True},
    {"defect_id": 5, "detected_at": _NOW, "station_pos": 4, "fault": "label misaligned",
     "confidence": 0.71, "status": "ticketed", "station_id": 4,
     "station_name": "packaging", "has_image": True},
    {"defect_id": 6, "detected_at": _NOW, "station_pos": 5, "fault": "surface damage",
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
    return None  # no decodable image -> dashboard hides the capture block


async def _summary():
    return {"faulty_count": len(SEED),
            "by_station": {"intake": 1, "packaging": 1, "station 5": 1},
            "by_severity": {"major": 1, "minor": 2}}


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

    by_id = {x["product_id"]: x for x in d["defects"]}
    assert by_id[4]["severity"] == "major", by_id[4]      # confidence 0.88
    assert by_id[5]["severity"] == "minor", by_id[5]      # confidence 0.71
    assert by_id[6]["severity"] == "minor", by_id[6]      # no confidence
    assert by_id[6]["station_name"] == "station 5", by_id[6]   # name fallback
    assert by_id[4]["defect"] == "bad paint", by_id[4]

    det = c.get("/api/defects/4").json()
    assert det["repair"]["est_minutes"] == 5, det["repair"]    # "bad paint" playbook
    here = [x for x in det["line"] if x["is_here"]]
    assert len(here) == 1 and here[0]["position"] == 1, det["line"]
    assert det["has_capture"] is False and det["capture_url"] is None, det
    assert c.get("/api/defects/999").status_code == 404

    ov = c.get("/")
    assert ov.status_code == 200 and "Live defect feed" in ov.text

    op = c.get("/operator?product_id=4")
    assert op.status_code == 200 and "Repair instructions" in op.text

print("OK — all routes, JSON shapes, line strip, and both templates pass.")
