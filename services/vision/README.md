# Vision Service

Python service that handles camera capture, computer vision, and data persistence.

## What it does

- Captures live camera feed and exposes it as an MJPEG stream (via ngrok tunnel for remote access)
- Uses OpenCV to detect objects and station states — e.g. box present at position X
- Reads robot joint state via the LeRobot library
- Writes detection events to a local table and replicates to an online DB via Soda Straw

## Stack

- Python
- OpenCV — object/state detection
- LeRobot — robot state reader
- Flask or FastAPI — MJPEG stream server
- Soda Straw — online DB sync

## Running

```bash
pip install -r requirements.txt
cp ../../.env.example .env
python main.py
```
