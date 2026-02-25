"""
publishers/token_store.py
─────────────────────────
Persistent storage for TikTok OAuth tokens.

Reads/writes tokens to credentials/tiktok_tokens.json so that refreshed
tokens survive process restarts. Called by TikTokPublisher.refresh_token().
"""

import json
from pathlib import Path
from config import settings


def _token_path() -> Path:
    return settings.TOKEN_FILE


def load_tokens() -> dict:
    """
    Load tokens from disk.

    Returns:
        dict with keys: access_token, refresh_token, expires_at (ISO string).
        Returns empty dict if file doesn't exist.
    """
    path = _token_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_tokens(access_token: str, refresh_token: str, expires_at: str,
                *, open_id: str = None) -> None:
    """
    Persist tokens to disk.

    Args:
        access_token:  Current OAuth access token.
        refresh_token: Current OAuth refresh token.
        expires_at:    ISO-8601 timestamp when access_token expires.
        open_id:       TikTok user ID (optional, saved if provided).
    """
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }
    if open_id is not None:
        data["open_id"] = open_id
    path.write_text(json.dumps(data, indent=2) + "\n")
