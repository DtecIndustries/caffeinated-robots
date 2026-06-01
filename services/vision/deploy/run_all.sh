#!/usr/bin/env bash
# Bring up the full pipeline: vLLM -> vision app -> ngrok tunnel.
#
# Starts vLLM first and waits for it to report healthy before launching the
# vision app (so the first VLM call doesn't race the server warming up).
# Logs go to deploy/logs/. Ctrl-C tears everything down.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a

LOG_DIR="$HERE/logs"
mkdir -p "$LOG_DIR"
PIDS=()

cleanup() {
  echo
  echo "==> Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 1. vLLM ----------------------------------------------------------------
echo "==> Starting vLLM (log: $LOG_DIR/vllm.log)"
bash "$HERE/run_vllm.sh" >"$LOG_DIR/vllm.log" 2>&1 &
PIDS+=($!)

VLLM_PORT="${VLLM_PORT:-8001}"
echo -n "==> Waiting for vLLM on :$VLLM_PORT (model load can take a few minutes)"
for _ in $(seq 1 180); do
  if curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null 2>&1; then
    echo " ready."
    break
  fi
  if ! kill -0 "${PIDS[-1]}" 2>/dev/null; then
    echo
    echo "!! vLLM exited early. Last log lines:" >&2
    tail -n 30 "$LOG_DIR/vllm.log" >&2
    exit 1
  fi
  echo -n "."
  sleep 2
done

# --- 2. Vision app ----------------------------------------------------------
echo "==> Starting vision app (log: $LOG_DIR/vision.log)"
bash "$HERE/run_vision.sh" >"$LOG_DIR/vision.log" 2>&1 &
PIDS+=($!)

# --- 3. ngrok tunnel --------------------------------------------------------
if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
  echo "==> Starting ngrok tunnel (log: $LOG_DIR/tunnel.log)"
  bash "$HERE/run_tunnel.sh" >"$LOG_DIR/tunnel.log" 2>&1 &
  PIDS+=($!)
  sleep 3
  echo "    public URL:"
  curl -sf http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | grep -o '"public_url":"[^"]*"' | head -1 || echo "    (check $LOG_DIR/tunnel.log)"
else
  echo "==> NGROK_AUTHTOKEN unset; skipping tunnel (LAN only on :${STREAM_PORT:-8000})"
fi

echo
echo "==> Up. Endpoints:"
echo "    http://localhost:${STREAM_PORT:-8000}/health"
echo "    http://localhost:${STREAM_PORT:-8000}/stream      (raw MJPEG)"
echo "    http://localhost:${STREAM_PORT:-8000}/annotated   (YOLO overlay MJPEG)"
echo "    http://localhost:${STREAM_PORT:-8000}/detections  (YOLO metadata JSON)"
echo "    http://localhost:${STREAM_PORT:-8000}/scene       (VLM scene JSON)"
echo "    Ctrl-C to stop everything."
wait
