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

from pathlib import Path
from config import settings


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
        """Refresh OAuth access token. TODO: implement."""
        raise NotImplementedError
