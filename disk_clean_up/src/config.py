# config.py
from dotenv import load_dotenv
import os

load_dotenv()

# ── Discord ───────────────────────────────────────────────
DISCORD_BOT_TOKEN  = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID"))

# ── Ollama / LLM ──────────────────────────────────────────
OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL", "qwen2.5")
OLLAMA_HOST        = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# ── Folders ───────────────────────────────────────────────
MONITORED_FOLDER   = "monitored_folder"
DELETED_FOLDER     = "deleted_files"
REPORT_FOLDER      = "reports"

# ── Logging ───────────────────────────────────────────────
LOG_FILE           = "logs/cleanup.log"

# ── Scanner thresholds ────────────────────────────────────
THRESHOLD_DAYS     = int(os.getenv("THRESHOLD_DAYS", "180"))
MIN_FILE_SIZE_KB   = int(os.getenv("MIN_FILE_SIZE_KB", "100"))

# ── LLM behaviour ────────────────────────────────────────
BATCH_SIZE         = int(os.getenv("BATCH_SIZE", "50"))
CACHE_REANALYSIS_DAYS = int(os.getenv("CACHE_REANALYSIS_DAYS", "15"))