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
  (label, SKU, defect, severity, reason, QC image), **where** it is on the line
  (station strip with the current station pinned), and **how to fix it**
  (tools, a tap-to-check step list, and disposition). Open it for a specific
  part with `/operator?product_id=<id>`; with no id it auto-selects the most
  urgent open defect.

## Defect rule

A product is **faulty** if it has a most-recent failed QC detection
(`detections.verdict = 'fail'`) **OR** its `products.status` is `rejected` or
`hold`. The rule lives in one SQL CTE in [db.py](db.py) so the count and the
detail view can never disagree.

Repair guidance isn't a DB column — it's derived in [repair.py](repair.py),
keyed first by the detection's `defect_code`, then by station, then a generic
fallback.

## API

| Endpoint | Returns |
| --- | --- |
| `GET /api/summary` | `{faulty_count, by_station, by_severity}` |
| `GET /api/defects` | `{count, defects: [...]}` |
| `GET /api/defects/{product_id}` | one defect + `repair` playbook + `line` stations |

Browsers poll `/api/defects` every `DASHBOARD_POLL_MS` (default 2s), so a new
defect shows up within a couple of seconds with no page reload.

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
