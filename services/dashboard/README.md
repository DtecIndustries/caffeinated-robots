# Quality Dashboards

Two web dashboards over one defect rule, reading the same straw-backed Postgres
the vision service writes to.

## What it does

- **Overview dashboard** (`/`) — the control-room view. Live count of faulty
  parts on the line, severity/station rollups, and a feed of defect cards that
  flashes when a new defect appears. The alert surfaces here, on the dashboard
  (no Discord). Each card links to the operator view for that part.
- **Operator repair dashboard** (`/operator`) — a different, focused template
  meant to be opened at the line. For one part it shows **what** is defective
  (defect, severity, reason), the **camera capture** taken at detect time (only
  when one is stored), **where** it is on the line (station strip with the
  current station pinned), and **how to fix it** (tools, a tap-to-check step
  list, and disposition). Open it for a specific defect with
  `/operator?product_id=<id>`; with no id it auto-selects the most urgent one.

## Defect source

Defects come from the vision service's **`faulty_parts`** table. A part is
**faulty** (still needs attention) while its `status` is anything other than
`resolved`. The query lives in [db.py](db.py) (`_FAULTY_SQL`), joined to
`stations` by `station_pos` for the line location.

The camera snapshot is stored by the vision service as a base64-encoded JPEG in
`faulty_parts.image_b64`. The dashboard decodes it on demand, sniffs the type
(JPEG/PNG), and serves the raw bytes — and only shows the image when the column
holds a real, decodable image (legacy/placeholder rows are skipped).

Repair guidance isn't a DB column — it's derived in [repair.py](repair.py),
keyed first by the `fault` text, then by station, then a generic fallback.

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
