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
VEO_MODEL       = os.getenv("VEO_MODEL", "veo-3.1-fast-generate-001")
VEO_REGION      = os.getenv("VEO_REGION", "us-central1")

# ── Agent Opus ────────────────────────────────────────────────────────────────
OPUS_API_KEY       = os.getenv("OPUS_API_KEY", "")
OPUS_API_BASE      = os.getenv("OPUS_API_BASE", "https://api.opus.pro/api")
OPUS_POLL_TIMEOUT  = int(os.getenv("OPUS_POLL_TIMEOUT", "1800"))
OPUS_POLL_INTERVAL = int(os.getenv("OPUS_POLL_INTERVAL", "15"))
# Escape hatch: pre-registered dashboard asset IDs, comma-separated.
# When set, reference photo upload is skipped entirely.
OPUS_REFERENCE_ASSET_IDS = tuple(
    x.strip() for x in os.getenv("OPUS_REFERENCE_ASSET_IDS", "").split(",") if x.strip()
)

# ── Reference photos (Nika) ──────────────────────────────────────────────────
REFERENCE_PHOTOS_DIR = ROOT_DIR / os.getenv("REFERENCE_PHOTOS_DIR", "reference/nika")

# ── TikTok ────────────────────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN  = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "")
TIKTOK_OPEN_ID       = os.getenv("TIKTOK_OPEN_ID", "")
TOKEN_FILE           = CREDS_DIR / "tiktok_tokens.json"

# ── TikTok Sandbox ───────────────────────────────────────────────────────────
TIKTOK_SANDBOX_CLIENT_KEY    = os.getenv("TIKTOK_SANDBOX_CLIENT_KEY", "")
TIKTOK_SANDBOX_CLIENT_SECRET = os.getenv("TIKTOK_SANDBOX_CLIENT_SECRET", "")
TIKTOK_SANDBOX_TOKEN_FILE    = CREDS_DIR / "tiktok_sandbox_tokens.json"
TIKTOK_SANDBOX               = False


def activate_sandbox():
    """Swap TikTok credentials to sandbox values."""
    mod = sys.modules[__name__]
    mod.TIKTOK_CLIENT_KEY = mod.TIKTOK_SANDBOX_CLIENT_KEY
    mod.TIKTOK_CLIENT_SECRET = mod.TIKTOK_SANDBOX_CLIENT_SECRET
    mod.TOKEN_FILE = mod.TIKTOK_SANDBOX_TOKEN_FILE
    mod.TIKTOK_SANDBOX = True

# ── Caption LLM (Anthropic Claude) ───────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CAPTION_MODEL     = os.getenv("CAPTION_MODEL", "claude-haiku-4-5-20251001")

# ── Pipeline ──────────────────────────────────────────────────────────────────
VIDEOS_PER_RUN           = int(os.getenv("VIDEOS_PER_RUN", "1"))
DRY_RUN                  = os.getenv("DRY_RUN", "false").lower() == "true"
LOG_LEVEL                = os.getenv("LOG_LEVEL", "INFO")
NOTIFY_EMAIL             = os.getenv("NOTIFY_EMAIL", "")

# ── Scheduling ────────────────────────────────────────────────────────────────
POST_SCHEDULE_CRON = os.getenv("POST_SCHEDULE_CRON", "0 18 * * *")
POST_TIMEZONE      = os.getenv("POST_TIMEZONE", "America/Los_Angeles")

# ── Analytics ────────────────────────────────────────────────────────────────
ANALYTICS_DELAY_HOURS = int(os.getenv("ANALYTICS_DELAY_HOURS", "24"))

# ── Validation ────────────────────────────────────────────────────────────────

_REQUIRED = {
    "TIKTOK_CLIENT_KEY": "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET": "TIKTOK_CLIENT_SECRET",
    "OPUS_API_KEY": "OPUS_API_KEY",
}

_TIKTOK_VARS = {"TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"}
_OPUS_VARS = {"OPUS_API_KEY"}


def validate_config(*, dry_run=False):
    """Raise ValueError if any required setting is missing.

    OPUS_API_KEY is always required; TikTok vars are skipped in dry-run mode.
    """
    mod = sys.modules[__name__]
    required = _OPUS_VARS if dry_run else _OPUS_VARS | _TIKTOK_VARS
    missing = [
        env_name for env_name in sorted(required)
        if not getattr(mod, _REQUIRED[env_name], "")
    ]

    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in your .env file or shell environment."
        )
