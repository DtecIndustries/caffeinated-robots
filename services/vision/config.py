import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---- video source -----------------------------------------------------------
# VIDEO_SOURCE may be a local camera index ("0") or a stream URL. On this box
# the feed comes from another machine on the wifi over an ngrok MJPEG stream,
# so VIDEO_SOURCE is that URL and we must send the ngrok skip-warning header.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
CAMERA_URL = os.getenv("CAMERA_URL", "")  # set this to use a remote MJPEG stream instead of local cam
_raw_source = os.getenv("VIDEO_SOURCE", "").strip()
if _raw_source == "":
    VIDEO_SOURCE: object = CAMERA_INDEX
elif _raw_source.isdigit():
    VIDEO_SOURCE = int(_raw_source)
else:
    VIDEO_SOURCE = _raw_source
# Extra HTTP headers for URL sources, FFMPEG "k;v" format pieces joined by \r\n.
STREAM_HTTP_HEADERS = os.getenv("STREAM_HTTP_HEADERS", "ngrok-skip-browser-warning: 1")

# ---- stream server ----------------------------------------------------------
STREAM_HOST = os.getenv("STREAM_HOST", "0.0.0.0")
STREAM_PORT = int(os.getenv("STREAM_PORT", 8000))
STREAM_FPS = int(os.getenv("STREAM_FPS", 30))
STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", 640))
STREAM_HEIGHT = int(os.getenv("STREAM_HEIGHT", 480))

DB_URL = os.getenv("DB_URL", "")  # postgresql://user:pass@host/db
DETECTION_INTERVAL = float(os.getenv("DETECTION_INTERVAL", 0.5))
DETECTION_CONFIRM_DELAY = float(os.getenv("DETECTION_CONFIRM_DELAY", 1.0))  # seconds object must be continuously detected before confirming
DETECTION_RATIO_THRESHOLD = float(os.getenv("DETECTION_RATIO_THRESHOLD", 0.02))  # min fraction of ROI pixels that must be object
DETECTION_BRIGHT_THRESH = int(os.getenv("DETECTION_BRIGHT_THRESH", 200))  # pixels above this = white/GOOD
DETECTION_RANGE_THRESH  = int(os.getenv("DETECTION_RANGE_THRESH",  40))   # min/max grey difference above this = object present but not white → FAULTY

# ---- YOLO segmentation ------------------------------------------------------
# yolo11n-seg.pt / yolov8n-seg.pt auto-download on first use. Nano fits 8 GB
# comfortably alongside the quantized VLM.
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolo11n-seg.pt")
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "cuda:0")
YOLO_IMGSZ = int(os.getenv("YOLO_IMGSZ", 640))
YOLO_CONF = float(os.getenv("YOLO_CONF", 0.35))
YOLO_HALF = _bool("YOLO_HALF", True)
# Run YOLO on every Nth captured frame (1 = every frame). On the 35W A2000
# laptop GPU, 2 leaves headroom for the VLM without hurting realtime feel.
YOLO_EVERY_N = int(os.getenv("YOLO_EVERY_N", 2))

# ---- vLLM / Qwen2.5-VL ------------------------------------------------------
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct-AWQ")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
VLM_MAX_TOKENS = int(os.getenv("VLM_MAX_TOKENS", 192))
VLM_TEMPERATURE = float(os.getenv("VLM_TEMPERATURE", 0.2))
VLM_JPEG_MAX_SIDE = int(os.getenv("VLM_JPEG_MAX_SIDE", 768))
VLM_JPEG_QUALITY = int(os.getenv("VLM_JPEG_QUALITY", 80))

# ---- pipeline gating --------------------------------------------------------
ENABLE_VLM = _bool("ENABLE_VLM", True)
# Never call the VLM more often than this (seconds), even if the scene changes.
VLM_MIN_INTERVAL_S = float(os.getenv("VLM_MIN_INTERVAL_S", 3.0))
# Re-query at least this often even if the scene looks unchanged (seconds).
VLM_HEARTBEAT_S = float(os.getenv("VLM_HEARTBEAT_S", 20.0))
