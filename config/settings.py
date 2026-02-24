"""
config/settings.py
──────────────────
Central configuration loaded from environment variables.
All modules import from here — never read os.environ directly elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = ROOT_DIR / os.getenv("OUTPUT_DIR", "output")
LOGS_DIR   = ROOT_DIR / "logs"
CREDS_DIR  = ROOT_DIR / "credentials"

# ── Google Cloud / Veo 3 ─────────────────────────────────────────────────────
GCP_PROJECT_ID  = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
GCP_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
VEO_MODEL       = os.getenv("VEO_MODEL", "veo-003")
VEO_REGION      = os.getenv("VEO_REGION", "us-central1")

# ── TikTok ────────────────────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN  = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "")
TIKTOK_OPEN_ID       = os.getenv("TIKTOK_OPEN_ID", "")
TOKEN_FILE           = CREDS_DIR / "tiktok_tokens.json"

# ── Pipeline ──────────────────────────────────────────────────────────────────
VIDEOS_PER_RUN           = int(os.getenv("VIDEOS_PER_RUN", "1"))
DRY_RUN                  = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Scheduling ────────────────────────────────────────────────────────────────
POST_SCHEDULE_CRON = os.getenv("POST_SCHEDULE_CRON", "0 18 * * *")
POST_TIMEZONE      = os.getenv("POST_TIMEZONE", "America/Los_Angeles")

# ── Validation ────────────────────────────────────────────────────────────────
# TODO: implement validate_config() to fail fast on missing required values

def validate_config():
    """Raise ValueError if any required setting is missing."""
    # TODO: implement
    raise NotImplementedError
