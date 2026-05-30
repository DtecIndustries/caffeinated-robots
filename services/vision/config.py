import os
from dotenv import load_dotenv

load_dotenv()

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
CAMERA_URL = os.getenv("CAMERA_URL", "")  # set this to use a remote MJPEG stream instead of local cam
STREAM_HOST = os.getenv("STREAM_HOST", "0.0.0.0")
STREAM_PORT = int(os.getenv("STREAM_PORT", 8000))
STREAM_FPS = int(os.getenv("STREAM_FPS", 30))
STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", 640))
STREAM_HEIGHT = int(os.getenv("STREAM_HEIGHT", 480))

DB_URL = os.getenv("DB_URL", "")  # postgresql://user:pass@host/db
DETECTION_INTERVAL = float(os.getenv("DETECTION_INTERVAL", 0.5))
DETECTION_RATIO_THRESHOLD = float(os.getenv("DETECTION_RATIO_THRESHOLD", 0.02))  # min fraction of ROI pixels that must be object
DETECTION_BRIGHT_THRESH = int(os.getenv("DETECTION_BRIGHT_THRESH", 180))  # grayscale value above which = white object
DETECTION_DARK_THRESH = int(os.getenv("DETECTION_DARK_THRESH", 50))   # grayscale value below which = black object
