import os

from dotenv import load_dotenv

load_dotenv()

# --- Soda Straw MCP gateway (scoped agent API key) ---
STRAW_MCP_URL = os.getenv("STRAW_MCP_URL", "https://kustex.straw.demo.soda.io/mcp")
STRAW_API_KEY = os.environ["STRAW_API_KEY"]
POSTGRES_STRAW = os.getenv("POSTGRES_STRAW", "postgres")
DISCORD_STRAW = os.getenv("DISCORD_STRAW", "discord-bot")
DB_NAME = os.getenv("DB_NAME", "caffeinated")

# --- Discord ---
DISCORD_CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
DISCORD_BOT_USER_ID = os.getenv("DISCORD_BOT_USER_ID", "")

# --- Anthropic (supervisor assistant) ---
# ANTHROPIC_API_KEY is read from the environment by the SDK directly.
ANTHROPIC_MODEL = os.getenv("SUPERVISOR_MODEL", "claude-opus-4-8")
ANTHROPIC_EFFORT = os.getenv("SUPERVISOR_EFFORT", "medium")

# --- Loop cadence (seconds) ---
MONITOR_INTERVAL = float(os.getenv("MONITOR_INTERVAL", "5"))
DISCORD_POLL_INTERVAL = float(os.getenv("DISCORD_POLL_INTERVAL", "4"))

STATE_FILE = os.getenv("SUPERVISOR_STATE_FILE", ".supervisor_state.json")
