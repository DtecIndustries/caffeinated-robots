# Quality Dashboards

Two web dashboards over one defect rule, reading the same straw-backed Postgres
the vision service writes to.

## What it does

- **Overview dashboard** (`/`) — the control-room view. A line-status headline
  (**LINE ON HOLD** while a defect awaits the supervisor's decision, **NO-GO
  removing** while the robot pulls a part, **LINE RUNNING** when clear), a live
  count, severity/station rollups, and a feed of defect cards that flashes when
  a new one appears. The alert surfaces here, on the dashboard (no Discord).
- **Operator dashboard** (`/operator`) — a focused template for the line. For
  one part it shows **what** is defective (the defect + severity), the **camera
  capture** taken at detect time (only when one is stored), **where** it is on
  the line (station strip with the current station pinned), and the **live
  status / required action** (awaiting GO-NO-GO, or NO-GO being removed by the
  robot). Open a specific defect with `/operator?product_id=<id>`; with no id it
  auto-selects the most urgent one. Both views **clear automatically** when no
  defect remains.

## Defect source & lifecycle

Defects come from the vision service's **`faulty_parts`** table. The only fault
the vision pipeline raises is **`paint NOK`** (the part isn't correctly painted).

A part is shown on the line while it still needs attention, and **drops off the
line** as soon as any of these is true:

- **GO** — supervisor ruled it a false positive (`resolution = 'go'`); the part
  continues.
- **robot handled** — the robot pulled it off the line (`robot_acked = true`,
  with `robot_acked_at`).
- it no longer exists.

While on the line a defect is in one of two phases:

- **awaiting resolution** (`resolution IS NULL`) → the report states **LINE ON
  HOLD**, and
- **NO-GO removing** (`resolution = 'no_go'`, not yet handled) → the robot is
  pulling it.

So the line filter is `robot_acked = false AND resolution IS DISTINCT FROM 'go'`.
The query lives in [db.py](db.py) (`_FAULTY_SQL`), joined to `stations` by
`station_pos` for the line location.

The camera snapshot is stored by the vision service as a base64-encoded JPEG
(the cropped station ROI) in `faulty_parts.image_b64`. The dashboard decodes it
on demand, sniffs the type (JPEG/PNG), and serves the raw bytes — and only shows
the image when the column holds a real, decodable image.

## API

| Endpoint | Returns |
| --- | --- |
| `GET /api/summary` | `{faulty_count, by_station, by_severity}` |
| `GET /api/defects` | `{count, defects: [...]}` |
| `GET /api/defects/{id}` | one defect + `repair` playbook + `line` stations |
| `GET /api/defects/{id}/image` | the captured camera frame (404 if none) |

`{id}` is the `faulty_parts` id (the JSON still calls it `product_id` so the
links and image route stay stable). Browsers poll `/api/defects` every
`DASHBOARD_POLL_MS` (default 2s), so a new defect shows up within a couple of
seconds with no page reload.

## Running

```bash
cd services/dashboard
uv venv && uv pip install -e .        # or: pip install -e .
cp .env.example .env                  # set DB_URL to your Postgres
python main.py                        # http://localhost:8050
```

`DB_URL` is the same `postgresql://…` connection the vision service uses.

## Self-test (no DB required)

```bash
uv pip install httpx        # test-only dependency for the FastAPI TestClient
python selftest.py
```

Exercises the routes, JSON shapes, and both templates against in-memory sample
data — the SQL itself is validated against the live database.
