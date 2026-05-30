import os

from dotenv import load_dotenv

load_dotenv()

# postgresql://user:pass@host:5432/dbname  (same straw-backed DB the vision service writes to)
DB_URL = os.getenv("DB_URL", "")

HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", 8050))

# How often the browser dashboards re-poll the API, in milliseconds.
POLL_INTERVAL_MS = int(os.getenv("DASHBOARD_POLL_MS", 2000))

# A product is "faulty" if it has a failed QC detection OR its status is one of these.
# (verdict='fail' OR status in FAULTY_STATUSES)  -- matches the agreed defect rule.
FAULTY_STATUSES = ("rejected", "hold")
