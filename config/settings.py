"""
config/settings.py
──────────────────
Central configuration loaded from environment variables.
All modules import from here — never read os.environ directly elsewhere.
"""

import os
import sys
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
VEO_MODEL       = os.getenv("VEO_MODEL", "veo-3.0-generate-001")
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
LOG_LEVEL                = os.getenv("LOG_LEVEL", "INFO")

# ── Scheduling ────────────────────────────────────────────────────────────────
POST_SCHEDULE_CRON = os.getenv("POST_SCHEDULE_CRON", "0 18 * * *")
POST_TIMEZONE      = os.getenv("POST_TIMEZONE", "America/Los_Angeles")

# ── Validation ────────────────────────────────────────────────────────────────

_REQUIRED = {
    "GOOGLE_CLOUD_PROJECT_ID": "GCP_PROJECT_ID",
    "GOOGLE_APPLICATION_CREDENTIALS": "GCP_CREDENTIALS",
    "TIKTOK_CLIENT_KEY": "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET": "TIKTOK_CLIENT_SECRET",
}

_GCP_VARS = {"GOOGLE_CLOUD_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"}
_TIKTOK_VARS = {"TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"}


def validate_config(*, dry_run=False):
    """Raise ValueError if any required setting is missing.

    In dry-run mode, only GCP vars are required (TikTok is skipped).
    """
    mod = sys.modules[__name__]
    required = _GCP_VARS if dry_run else _GCP_VARS | _TIKTOK_VARS
    missing = [
        env_name for env_name in sorted(required)
        if not getattr(mod, _REQUIRED[env_name], "")
    ]

    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in your .env file or shell environment."
        )
