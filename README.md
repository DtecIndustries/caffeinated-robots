# Caffeinated Robots

Hackers & Ravers submission.

## Structure

```
│
├── README.md
├── .gitignore
├── .env.example
│
├── services/
│   │
│   ├── vision/                          # Python — Camera + CV + streaming
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── main.py                      # Entry point
│   │   ├── config.py                    # Env vars, camera IDs, thresholds
│   │   │
│   │   ├── camera/
│   │   │   ├── __init__.py
│   │   │   ├── stream.py                # MJPEG stream server (Flask/FastAPI)
│   │   │   └── capture.py               # OpenCV capture abstraction
│   │   │
│   │   ├── detection/
│   │   │   ├── __init__.py
│   │   │   ├── detector.py              # Box/object detection logic
│   │   │   ├── station.py               # Station state machine (pos x → status)
│   │   │   └── models/                  # Any CV model weights
│   │   │
│   │   ├── robot/
│   │   │   ├── __init__.py
│   │   │   └── lerobot_bridge.py        # LeRobot state reader
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       └── sodastraw_client.py      # Writes detection events to online DB
│   │
│   └── twin/                            # JS — Digital twin frontend
│       ├── README.md
│       ├── package.json
│       ├── vite.config.js
│       │
│       ├── src/
│       │   ├── main.js
│       │   ├── config.js                # DB endpoints, camera URLs, env
│       │   │
│       │   ├── scene/
│       │   │   ├── SceneManager.js      # Three.js setup, lights, camera
│       │   │   ├── ProductionLine.js    # Conveyor, stations, boxes in 3D
│       │   │   └── RobotModel.js        # Robot arm visualization
│       │   │
│       │   ├── data/
│       │   │   ├── DbClient.js          # Reads from online or local DB
│       │   │   ├── StateSync.js         # Polls/subscribes, drives scene updates
│       │   │   └── mock.js              # Local fallback data for offline dev
│       │   │
│       │   └── ui/
│       │       ├── CameraFeed.js        # Overlays MJPEG stream in the scene
│       │       ├── StatusPanel.js       # HUD — QC status, station states
│       │       └── RobotPanel.js        # Robot joint states, current action
│       │
│       └── public/
│           └── models/                  # GLTF/GLB assets for robot/line
│
├── shared/                              # Shared contracts between services
│   ├── schema.md                        # Canonical DB table/event schema
│   └── events.md                        # Event types (box_detected, qc_pass, etc.)
│
└── infra/
    ├── ngrok.yml                        # Ngrok tunnel config
    └── .env.example                     # Template for all services
```