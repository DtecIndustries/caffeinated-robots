# Digital Twin

JS frontend that visualizes the production line and robot state in real time.

## What it does

- Renders a 3D scene of the production line (conveyor, stations, boxes) using Three.js
- Displays robot arm state (joint positions, current action) synced from the vision service
- Overlays the live MJPEG camera feed from the vision service inside the scene
- Reads state from the online DB (via Soda Straw) or falls back to a local DB / mock data for offline dev

## Stack

- JavaScript
- Three.js — 3D scene
- Vite — dev server and bundler
- Soda Straw — DB client (online or local)

## Running

```bash
cd services/twin
npm install
cp .env.example .env
npm run dev
```

Opens at http://localhost:5173 with mock data (no vision service required).

## Phase 0 (current)

**Process:** CNC (Laser) → Assembly → QC → Packaging

**QC fail:** item diverted to **Holding** (pos5 / single bay). If holding is full, the **entire line halts** until human review clears it.

- 3D conveyor, 4 process stations, 1 holding bay (pos5), robot arm
- HUD: line status, QC, stations, holding slots
- **One box on the line** at a time (mock). Human review buttons in mock mode only.

## Database (read-only)

Polls PostgreSQL via Vite dev middleware `GET /api/state` — **no writes** from the twin.

```bash
npm run db:test      # connection check
npm run db:state     # print mapped world state JSON
```

Set in `.env`:

```env
VITE_USE_MOCK=false
DATABASE_URL=postgresql://...
```

Then `npm run dev` — HUD shows **Read-only — live data from database**; controls disabled.

Reads **only** `production_line` (latest row):

| DB column | Twin station |
|-----------|----------------|
| `pos1_item_present` / `pos1_item_status` | CNC (Laser) |
| `pos2_item_present` / `pos2_item_status` | Assembly |
| `pos3_item_present` / `pos3_item_status` | Quality Control |
| `pos4_item_present` / `pos4_item_status` | Packaging |
| `pos5_item_present` (+ optional `pos5_item_status`) | **Holding** (human review) |
| `robot_joints` | `integer[6]` joint angles (÷1000 → radians), telemetry |
| `robot_curr_pos` / `robot_next_pos` | **integer** slot index (`0` = home, `1`–`5` = CNC … Holding) |
| `robot_pose` | e.g. `pick`, `place`, `transfer`, `home_again` |

Box on belt = rightmost **pos1–pos4** where `present` is true. **pos5** is the single holding bay (not on the conveyor).

When `robot_next_pos` is set and differs from `robot_curr_pos`, the arm animates between those slots. With `pick` / `transfer` / `place` in `robot_pose`, a box is shown on the gripper.

**Holding (pos5) — when the crane should go there**

| Situation | Typical DB signal | Twin animation |
|-----------|-------------------|----------------|
| QC fail → divert for human review | `robot_curr_pos=3`, `robot_next_pos=5`, `pos5_item_present` becomes true, `robot_pose` includes `pick` | Base swivels toward holding; pick at QC, place into pos5 |
| Human approved → return to line | `robot_curr_pos=5`, `robot_next_pos=4`, `pos5_item_present` true until grip, `robot_pose` includes `place` | Base faces holding; **collect cube at pos5**, place on Packaging (pos4) |
| Holding full / halt | `pos5_item_present` + halt status | Line paused until review clears a slot |

Slot `5` is not on the belt; `pos5_item_present` is the source of truth for whether a cube is in the bay.

**Reject (no-go)** — opposite side of holding (same X, opposite Z). Items reach reject **from holding only**:

| DB signal | Twin |
|-----------|------|
| `robot_curr_pos=5`, `robot_next_pos=6` | Crane leg holding → reject |
| `pos6_item_present` (when column exists) | Cube in reject bay |
| `pos5_item_status` contains `no-go` / `nogo` (with present or after move) | Reject occupied; holding empty |

QC fail still goes to **holding** first (`3→5`). Human **Faulty** or PLC no-go runs **holding → reject** (`5→6`).

**Sync debugger** (bottom of HUD): last fetch time, latency, change list, recent poll history. Set `VITE_DEBUG_PANEL=false` to hide.

## Env

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_USE_MOCK` | `true` | Mock simulation + interactive buttons |
| `VITE_READ_ONLY_DB` | `true` | Mark DB mode read-only (no UI writes) |
| `VITE_DEBUG_PANEL` | `true` | Show sync debugger in HUD |
| `DATABASE_URL` | — | Postgres (server-side only, in `.env`) |
| `VITE_POLL_MS` | `500` | Poll interval (ms) |
| `VITE_DB_STATE_URL` | `/api/state` when mock off | Postgres via Vite (same port as UI) |
| `VITE_STATE_URL` | vision `/state` | **Mock mode only** — not used when `VITE_USE_MOCK=false` |
| `VITE_VISION_STREAM_URL` | `http://localhost:8000/stream` | Phase 1 camera |
