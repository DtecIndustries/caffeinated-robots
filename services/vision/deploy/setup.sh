#!/usr/bin/env bash
# One-time setup for the vision inference box.
#
#   1. App venv (.venv)      -> FastAPI + OpenCV + Ultralytics (YOLO) + torch
#   2. vLLM venv (.venv-vllm) -> vLLM serving Qwen2.5-VL-3B-AWQ (isolated pins)
#   3. ngrok                 -> downloaded locally if missing
#   4. Model warm-pull       -> YOLO weights + Qwen VLM weights
#
# vLLM and Ultralytics pin torch differently, so they live in separate venvs.
# Both processes share the single GPU at runtime via gpu-memory-utilization.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [[ ! -f .env ]]; then
  log "Creating .env from .env.example (edit it to add NGROK_AUTHTOKEN)"
  cp .env.example .env
fi
set -a; source .env; set +a

# ---------------------------------------------------------------------------
log "1/4  App venv: FastAPI + OpenCV + Ultralytics (YOLO)"
uv sync

# ---------------------------------------------------------------------------
log "2/4  vLLM venv (.venv-vllm): vLLM + Qwen2.5-VL support"
# Qwen2.5-VL needs vLLM >= 0.7.2 and a recent transformers.
uv venv --python 3.11 .venv-vllm
VLLM_PY=".venv-vllm/bin/python"
uv pip install --python "$VLLM_PY" --upgrade pip
uv pip install --python "$VLLM_PY" "vllm>=0.7.2"
# AWQ kernels for the quantized checkpoint.
uv pip install --python "$VLLM_PY" autoawq || \
  echo "    (autoawq optional install failed; vLLM has a built-in AWQ path)"

# ---------------------------------------------------------------------------
log "3/4  ngrok"
if ! command -v ngrok >/dev/null 2>&1 && [[ ! -x "$HERE/ngrok" ]]; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) NG_ARCH=amd64 ;;
    aarch64|arm64) NG_ARCH=arm64 ;;
    *) echo "Unsupported arch $ARCH for ngrok auto-download" >&2; NG_ARCH="" ;;
  esac
  if [[ -n "$NG_ARCH" ]]; then
    URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-${NG_ARCH}.tgz"
    echo "    downloading ngrok ($NG_ARCH)"
    curl -fsSL "$URL" -o /tmp/ngrok.tgz
    tar -xzf /tmp/ngrok.tgz -C "$HERE"
    chmod +x "$HERE/ngrok"
  fi
else
  echo "    ngrok already available"
fi

# ---------------------------------------------------------------------------
log "4/4  Pre-pull model weights"
# YOLO weights (small, fast).
.venv/bin/python - <<PY
from ultralytics import YOLO
import os
YOLO(os.getenv("YOLO_MODEL", "yolo11n-seg.pt"))
print("YOLO weights ready")
PY
# Qwen VLM weights (a few GB over the hotspot — be patient).
echo "    pulling ${VLLM_MODEL} (this is the big one on a hotspot)"
.venv-vllm/bin/python - <<PY
from huggingface_hub import snapshot_download
import os
snapshot_download(os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"))
print("VLM weights ready")
PY

log "Setup complete. Launch everything with: deploy/run_all.sh"
