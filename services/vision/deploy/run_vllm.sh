#!/usr/bin/env bash
# Launch the vLLM OpenAI-compatible server hosting Qwen2.5-VL-3B-AWQ.
#
# Memory budget on the 8 GB card is shared with YOLO:
#   - VLLM_GPU_MEM_UTIL caps vLLM to ~55% of VRAM (~4.4 GB), leaving the
#     rest for the YOLO-seg model + driver/Xorg overhead.
#   - --enforce-eager skips CUDA graph capture to save more VRAM.
#   - --max-num-seqs 1 + small --max-model-len keeps the KV cache tiny.
#   - max_pixels caps image tokens so a single frame can't blow the cache.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a

VLLM_PY=".venv-vllm/bin/python"
PORT="${VLLM_PORT:-8001}"
MEM="${VLLM_GPU_MEM_UTIL:-0.60}"
MAXLEN="${VLLM_MAX_MODEL_LEN:-4096}"
MAXSEQ="${VLLM_MAX_NUM_SEQS:-1}"
MAXPIX="${VLLM_MM_MAX_PIXELS:-602112}"

echo "==> vLLM serving ${VLLM_MODEL} on :${PORT} (gpu-mem-util=${MEM})"
exec "$VLLM_PY" -m vllm.entrypoints.openai.api_server \
  --model "$VLLM_MODEL" \
  --served-model-name "$VLLM_MODEL" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --quantization awq_marlin \
  --dtype float16 \
  --gpu-memory-utilization "$MEM" \
  --max-model-len "$MAXLEN" \
  --max-num-seqs "$MAXSEQ" \
  --enforce-eager \
  --limit-mm-per-prompt '{"image": 1}' \
  --mm-processor-kwargs "{\"max_pixels\": ${MAXPIX}}"
