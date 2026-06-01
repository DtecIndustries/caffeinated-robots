# Vision Service — Realtime AI Inference Pipeline

Consumes a live video stream and runs a two-stage AI pipeline on a single 8 GB
GPU: a **YOLO segmentation** model annotates every frame, and a **Qwen2.5-VL**
vision-language model (served by **vLLM**) interprets the operations floor — gated by YOLO
so the heavy model only fires when the situation changes.

The camera feed exposed as an MJPEG
stream over ngrok is pulled in rather than opening a local camera.
A local index still works if `VIDEO_SOURCE` is blank.

## Architecture

```
   ┌──────────────────────┐   ngrok MJPEG
   │ CameraCapture        │  https://...ngrok-free.dev/stream
   │ (other host)         │──────────────┐
   └──────────────────────┘              │
                       ┌─────────────────▼──────────────────────┐
                       │  StreamHandler                        │
                       └───────────────┬────────────────────────┘
                                       │ frames (BGR)
                       ┌───────────────▼─────────────────────────┐
                       │  InferencePipeline                      │
                       │                                         │
                       │  YOLO thread ─ every frame ──► metadata │
                       │       │  (boxes, masks, centroids)      │
                       │       │                                 │
                       │  scene signature changed / heartbeat?   │
                       │       │  yes                            │
                       │       ▼                                 │
                       │  VLM thread ── frame + YOLO hint ─ ────►│──► vLLM server
                       │       ◄──── scene description ──────────│◄── Qwen2.5-VL-3B-AWQ
                       └───────────────┬─────────────────────────┘    (OpenAI API, :8001)
                                       │
                       ┌───────────────▼─────────────────────────┐
                       │  FastAPI (:8000)                        │
                       │  /stream /annotated /detections /scene  │
                       └───────────────┬─────────────────────────┘
                                       │  ngrok tunnel
                                       ▼
                              public URL over wifi hotspot
```

Both models share the GPU. vLLM is capped to ~55% of VRAM
(`VLLM_GPU_MEM_UTIL`) so the YOLO-seg model and driver fit in the rest.

> YOLO runs every 2nd frame, and the VLM floor is 3s.
> On a beefier hardware you can lower `YOLO_EVERY_N`,
> shorten `VLM_MIN_INTERVAL_S`, and raise `VLLM_GPU_MEM_UTIL`.

## Stack

- **Ultralytics YOLO** (`yolo11n-seg` by default) — instance segmentation
- **vLLM** + **Qwen2.5-VL-3B-Instruct-AWQ** — scene understanding (4-bit AWQ)
- **FastAPI + uvicorn** — MJPEG stream + JSON endpoints
- **ngrok** — public tunnel over the hotspot
- **uv** — two isolated venvs (`.venv` for the app, `.venv-vllm` for vLLM)

## Setup

```bash
cd services/vision
cp .env.example .env        # then edit: set NGROK_AUTHTOKEN
deploy/setup.sh             # creates both venvs, installs ngrok, pulls weights
```

`setup.sh` pulls a few GB of model weights

## Run

```bash
deploy/run_all.sh           # vLLM -> vision app -> ngrok, with health gating
```

Or run the pieces individually (separate terminals):

```bash
deploy/run_vllm.sh          # vLLM server on :8001
deploy/run_vision.sh        # FastAPI app on :8000
deploy/run_tunnel.sh        # ngrok tunnel
```

Logs from `run_all.sh` land in `deploy/logs/`.

## Endpoints

| Endpoint       | What it returns                                        |
|----------------|--------------------------------------------------------|
| `/health`      | Pipeline status + whether vLLM is reachable            |
| `/stream`      | Raw camera MJPEG stream                                |
| `/annotated`   | MJPEG stream with YOLO boxes/labels drawn              |
| `/detections`  | Latest YOLO segmentation metadata (JSON)               |
| `/scene`       | Latest Qwen-VL scene interpretation (JSON)             |

## Tuning the VRAM budget

All in `.env`:

| Var                   | Default | Notes                                             |
|-----------------------|---------|---------------------------------------------------|
| `VLLM_GPU_MEM_UTIL`   | `0.60`  | Fraction of VRAM for vLLM. Lower if YOLO OOMs.     |
| `VLLM_MAX_MODEL_LEN`  | `4096`  | Smaller = smaller KV cache.                        |
| `VLLM_MM_MAX_PIXELS`  | `602112`| Caps image tokens per frame.                       |
| `VLM_JPEG_MAX_SIDE`   | `768`   | Frame downscale before sending to the VLM.         |
| `YOLO_MODEL`          | `yolo11n-seg.pt` | Use `yolov8n-seg.pt` or larger as VRAM allows. |
| `YOLO_EVERY_N`        | `2`     | Run YOLO on every Nth frame to save GPU.           |
| `VLM_MIN_INTERVAL_S`  | `3.0`   | Floor between VLM calls.                            |
| `VLM_HEARTBEAT_S`     | `20.0`  | Force a VLM refresh even if the scene is static.   |
| `ENABLE_VLM`          | `true`  | Set `false` to run YOLO-only (no GPU contention).  |

If vLLM fails to allocate, lower `VLLM_GPU_MEM_UTIL` to `0.5` (or `0.45`) and/or
`VLLM_MAX_MODEL_LEN` to `2048`.

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
