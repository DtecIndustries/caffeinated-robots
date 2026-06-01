#!/usr/bin/env bash
# Expose the vision app over the wifi hotspot via ngrok.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a

NGROK="$(command -v ngrok || echo "$HERE/ngrok")"
if [[ ! -x "$NGROK" ]]; then
  echo "ngrok not found. Run deploy/setup.sh first." >&2
  exit 1
fi

if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
  "$NGROK" config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
fi

PORT="${STREAM_PORT:-8000}"
echo "==> Tunnelling http://localhost:${PORT} via ngrok"
if [[ -n "${NGROK_DOMAIN:-}" ]]; then
  exec "$NGROK" http --domain="$NGROK_DOMAIN" "$PORT"
else
  exec "$NGROK" http "$PORT"
fi
