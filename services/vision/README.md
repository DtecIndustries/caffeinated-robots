# Vision Service

Python service that handles camera capture, computer vision, and data persistence.

## What it does

- Captures live camera feed and exposes it as an MJPEG stream (via ngrok tunnel for remote access)
- Uses OpenCV to detect objects and station states — e.g. box present at position X
- Reads robot joint state via the LeRobot library
- Writes detection events to a local table and replicates to an online DB via Soda Straw

## Stack

- Python + uv
- OpenCV — object/state detection
- LeRobot — robot state reader
- FastAPI + uvicorn — MJPEG stream server
- Soda Straw — online DB sync

## Running

```bash
cp .env.example .env
uv run main.py
```

Live feed: `http://localhost:8000/stream`

## Finding your camera index

```bash
uv run list_cams.py
```

Scans indices 0–9, saves a snapshot per detected camera to `.cam_check/`, and prints which indices worked. Open the images to identify your USB cam, then set `CAMERA_INDEX` in `.env`.

## Running without a local camera (teammate / remote mode)

If you don't have a camera but want to run the full service against a teammate's live feed exposed via ngrok, set `CAMERA_URL` in `.env` instead of `CAMERA_INDEX`:

```env
CAMERA_URL=https://xxxx.ngrok-free.app/stream
```

Leave `CAMERA_INDEX` commented out. The service will pull frames from the remote MJPEG stream transparently — no other code changes needed.
