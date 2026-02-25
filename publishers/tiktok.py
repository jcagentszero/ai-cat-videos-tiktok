"""
publishers/tiktok.py
────────────────────
TikTok video publishing via TikTok Content Posting API.

Responsibilities:
  - Authenticate with TikTok API (OAuth 2.0)
  - Upload video file
  - Set caption, hashtags, privacy settings
  - Publish post
  - Return post URL / video ID

API reference:
  https://developers.tiktok.com/doc/content-posting-api-get-started
  Scopes required: video.upload, video.publish

TODO: implement
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from config import settings
from publishers import token_store
from utils.logger import logger

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
REFRESH_BUFFER_SECONDS = 300


class TikTokPublisher:
    """Handles video publishing to TikTok via Content Posting API."""

    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self):
        # TODO: validate access token exists
        # TODO: check token expiry and refresh if needed
        self.access_token = settings.TIKTOK_ACCESS_TOKEN
        self.open_id      = settings.TIKTOK_OPEN_ID
        raise NotImplementedError

    def publish(self, video_path: Path, caption: str, hashtags: list[str]) -> dict:
        """
        Upload and publish a video to TikTok.

        Args:
            video_path: Local path to the video file.
            caption:    Post caption text.
            hashtags:   List of hashtag strings (without #).

        Returns:
            dict with publish_id, share_url, status.

        TODO:
          1. Initialize upload (POST /video/init/)
          2. Upload video chunks (PUT to upload_url)
          3. Create post (POST /video/publish/)
          4. Poll for publish status
          5. Return result
        """
        raise NotImplementedError

    def _init_upload(self, file_size: int) -> dict:
        """Call TikTok init upload endpoint. TODO: implement."""
        raise NotImplementedError

    def _upload_video(self, upload_url: str, video_path: Path) -> bool:
        """PUT video bytes to TikTok upload URL. TODO: implement."""
        raise NotImplementedError

    def _create_post(self, publish_id: str, caption: str) -> dict:
        """Submit post creation. TODO: implement."""
        raise NotImplementedError

    def _check_status(self, publish_id: str) -> dict:
        """Poll publish status until live or failed. TODO: implement."""
        raise NotImplementedError

    def refresh_token(self) -> str:
        tokens = token_store.load_tokens()

        current_refresh = tokens.get("refresh_token")
        if not current_refresh:
            raise RuntimeError(
                "No refresh token available — run OAuth flow first "
                "(python main.py --auth)"
            )

        expires_at_str = tokens.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if expires_at - now > timedelta(seconds=REFRESH_BUFFER_SECONDS):
                    logger.debug(
                        "Access token still valid until {}, skipping refresh",
                        expires_at_str,
                    )
                    return tokens["access_token"]
            except ValueError:
                logger.warning(
                    "Could not parse expires_at '{}', forcing refresh",
                    expires_at_str,
                )

        logger.info("Refreshing TikTok access token...")

        payload = {
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": current_refresh,
        }

        try:
            resp = requests.post(TOKEN_URL, data=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Token refresh HTTP request failed: {}", exc)
            raise RuntimeError(f"Token refresh request failed: {exc}") from exc

        data = resp.json()

        if data.get("error"):
            error_desc = data.get("error_description", data["error"])
            logger.error("TikTok token refresh failed: {}", error_desc)
            raise RuntimeError(f"TikTok token refresh failed: {error_desc}")

        new_access = data["access_token"]
        new_refresh = data["refresh_token"]
        open_id = data.get("open_id") or tokens.get("open_id")
        expires_in = data.get("expires_in", 86400)

        new_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        ).isoformat()

        token_store.save_tokens(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_at=new_expires_at,
            open_id=open_id,
        )

        logger.info(
            "Token refreshed, expires at {} (in {}s)",
            new_expires_at, expires_in,
        )

        return new_access
