#!/usr/bin/env bash
# Launch the FastAPI vision app (camera + YOLO-gated VLM pipeline).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a

echo "==> Vision app on :${STREAM_PORT:-8000}"
exec uv run main.py
