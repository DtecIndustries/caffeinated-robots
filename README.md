# Caffeinated Robots

Hackers & Ravers submission — bringing the factory floor into the agentic stack.
A physical assembly line mockup, monitored through computer vision, feeding part presence, defect state, and robot state live into a 3D digital twin. The SO101 robot arm closes the loop; agents don't just observe, they can act in the physical world.
Soda Straw is built to unify data sources and software tools under a single MCP layer. We pushed it one step further and also connected it to the physical world. Query what's actually happening on the factory floor. Approve or reject flagged parts. Trigger the production line to physically move parts, straight from Claude, Cursor or your AI agent of choice.

## Running

**vision + detection + DB sync**
```bash
cd services/vision
cp .env.example .env
uv run main.py
```

**autonomous robot runner**
```bash
cd services/vision
uv run runner.py
```

**digital twin**
```bash
cd services/twin
npm install && npm run dev
```

## Vision service endpoints

| Endpoint | Description |
|---|---|
| `GET /stream` | Raw MJPEG camera feed |
| `GET /debug` | Annotated feed with station overlays and HUD |
| `GET /status` | Current station states as JSON |
| `POST /stations/force` | Override a station's detected state |
| `POST /robot/state` | Update robot display state (called by routine) |

## Database tables (PostgreSQL)

| Table | Purpose |
|---|---|
| `production_line` | Singleton row — current state of all 5 stations + robot |
| `faulty_parts` | One row per detected defect, with image snapshot |

Local SQLite (`local.db`) mirrors the same structure and syncs upstream on change.

## Structure

```
├── README.md
├── .gitignore
│
└── services/
    │
    ├── vision/                          # Python — camera, CV, robot, DB
    │   ├── main.py                      # FastAPI entry point
    │   ├── config.py                    # All env vars
    │   ├── routine.py                   # Robot action sequences (3_4, 3_5, 5_4, 5_R)
    │   ├── pyproject.toml
    │   │
    │   ├── camera/
    │   │   ├── capture.py               # OpenCV webcam capture
    │   │   └── stream.py                # MJPEG stream endpoint
    │   │
    │   ├── detection/
    │   │   ├── detector.py              # Brightness/range threshold detection → good/faulty
    │   │   └── station.py               # ROI definitions + crop_roi helper
    │   │
    │   ├── robot/
    │   │   └── servo_client.py          # Feetech servo protocol over serial
    │   │
    │   ├── db/
    │   │   ├── sodastraw_client.py      # PostgreSQL — production_line + faulty_parts
    │   │   ├── sqlite_client.py         # Local SQLite buffer (vision, robot, vision_calculated)
    │   │   ├── upstream_sync.py         # Event-driven SQLite → PostgreSQL sync
    │   │   ├── robot_writer.py          # Sync robot state to SQLite + PostgreSQL
    │   │   └── rules.py                 # Business logic (robot pos overrides CV)
    │   │
    │   └── (util scripts)
    │       ├── find_port.py             # Detect robot serial port by unplugging
    │       ├── list_cams.py             # Snapshot all cameras to find index
    │       ├── read_servos.py           # Live servo position reader
    │       ├── move_test.py             # Move single servo by delta
    │       ├── move_to.py               # Move all servos to a pose
    │       └── torque_off.py            # Emergency motor release
    │
    ├── twin/                            # JS — Three.js digital twin
    │   ├── index.html
    │   ├── package.json
    │   │
    │   ├── src/
    │   │   ├── main.js
    │   │   ├── config.js
    │   │   ├── scene/                   # Three.js scene
    │   │   ├── data/                    # StateSync, mock data, robot state
    │   │   └── ui/                      # StatusPanel, DebugPanel
    │   │
    │   └── server/                      # Vite middleware — DB proxy
    │       ├── fetch-state.mjs
    │       └── map-state.mjs
    │
    ├── dashboard/                       # Python — QC web dashboards (operator + overview)
    │   ├── main.py
    │   ├── config.py
    │   ├── db.py
    │   └── templates/
    │       ├── operator.html
    │       └── overview.html
    │
    └── supervisor/                      # Python — Claude supervisor agent via Soda Straw
        ├── run.py
        ├── supervisor_agent.py          # Claude agent — reviews flagged parts, sets resolution
        ├── monitor.py                   # Polls faulty_parts, triggers agent
        ├── sodastraw.py                 # Soda Straw straw client
        └── tools/
            └── make_test_ticket.py
```
