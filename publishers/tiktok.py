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

import time
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
        self.access_token = settings.TIKTOK_ACCESS_TOKEN
        self.open_id      = settings.TIKTOK_OPEN_ID
        logger.info("TikTokPublisher initialized")

    def publish(self, video_path: Path, caption: str, hashtags: list[str]) -> dict:
        logger.info("Publishing video to TikTok: {}", video_path)

        self.access_token = self.refresh_token()

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = video_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Video file is empty: {video_path}")

        if hashtags:
            tag_str = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
            full_caption = f"{caption} {tag_str}"
        else:
            full_caption = caption

        try:
            post_data = self._create_post(file_size, full_caption)
        except RuntimeError:
            logger.error("Failed to create TikTok post for {}", video_path)
            raise

        publish_id = post_data["publish_id"]
        upload_url = post_data["upload_url"]

        try:
            self._upload_video(upload_url, video_path)
        except RuntimeError:
            logger.error(
                "Failed to upload video {} (publish_id={})",
                video_path, publish_id,
            )
            raise

        try:
            status_result = self._check_status(publish_id)
        except (RuntimeError, TimeoutError):
            logger.error(
                "Publish status check failed (publish_id={})", publish_id,
            )
            raise

        video_id = None
        post_ids = status_result.get("publicaly_available_post_id", [])
        if post_ids:
            video_id = post_ids[0]

        logger.info(
            "Video published successfully (publish_id={}, status={}, video_id={})",
            publish_id, status_result.get("status"), video_id,
        )

        return {
            "publish_id": publish_id,
            "video_id": video_id,
            "status": status_result.get("status"),
            "video_path": str(video_path),
        }

    def _init_upload(self, file_size: int) -> dict:
        url = f"{self.BASE_URL}/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        logger.debug("Initializing TikTok upload (file_size={})", file_size)

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Init upload request failed: {}", exc)
            raise RuntimeError(f"Init upload request failed: {exc}") from exc

        data = resp.json()

        error = data.get("error", {})
        if error.get("code") != "ok":
            error_msg = error.get("message") or error.get("code", "unknown")
            logger.error("TikTok init upload failed: {}", error_msg)
            raise RuntimeError(f"TikTok init upload failed: {error_msg}")

        result = data.get("data", {})
        publish_id = result.get("publish_id")
        upload_url = result.get("upload_url")

        if not publish_id or not upload_url:
            raise RuntimeError(
                "TikTok init upload response missing publish_id or upload_url"
            )

        logger.info(
            "Upload initialized (publish_id={}, file_size={})",
            publish_id, file_size,
        )

        return result

    def _upload_video(self, upload_url: str, video_path: Path) -> bool:
        try:
            video_bytes = video_path.read_bytes()
        except OSError as exc:
            logger.error("Failed to read video file {}: {}", video_path, exc)
            raise RuntimeError(f"Failed to read video file {video_path}: {exc}") from exc

        file_size = len(video_bytes)
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }

        logger.debug(
            "Uploading video to TikTok (file_size={}, url={})",
            file_size, upload_url,
        )

        try:
            resp = requests.put(
                upload_url, headers=headers, data=video_bytes, timeout=300,
            )
        except requests.RequestException as exc:
            logger.error("Upload request failed: {}", exc)
            raise RuntimeError(f"Upload request failed: {exc}") from exc

        if resp.status_code not in (200, 201):
            logger.error(
                "TikTok upload failed with status {}: {}",
                resp.status_code, resp.text,
            )
            raise RuntimeError(
                f"TikTok upload failed with status {resp.status_code}"
            )

        logger.info("Video uploaded successfully (file_size={})", file_size)
        return True

    def _create_post(self, file_size: int, caption: str,
                     privacy_level: str = "SELF_ONLY") -> dict:
        url = f"{self.BASE_URL}/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "post_info": {
                "title": caption,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "is_aigc": True,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        logger.debug(
            "Creating TikTok post (caption_len={}, privacy={})",
            len(caption), privacy_level,
        )

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Create post request failed: {}", exc)
            raise RuntimeError(f"Create post request failed: {exc}") from exc

        data = resp.json()

        error = data.get("error", {})
        if error.get("code") != "ok":
            error_msg = error.get("message") or error.get("code", "unknown")
            logger.error("TikTok create post failed: {}", error_msg)
            raise RuntimeError(f"TikTok create post failed: {error_msg}")

        result = data.get("data", {})
        publish_id = result.get("publish_id")
        upload_url = result.get("upload_url")

        if not publish_id or not upload_url:
            raise RuntimeError(
                "TikTok create post response missing publish_id or upload_url"
            )

        logger.info(
            "Post created (publish_id={}, privacy={})",
            publish_id, privacy_level,
        )

        return result

    def _check_status(self, publish_id: str, timeout=120) -> dict:
        url = f"{self.BASE_URL}/post/publish/status/fetch/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {"publish_id": publish_id}

        interval = 5
        max_interval = 15
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Publish status check timed out after {timeout}s "
                    f"(publish_id={publish_id})"
                )

            logger.debug(
                "Polling publish status (publish_id={}, elapsed={:.0f}s)",
                publish_id, elapsed,
            )

            try:
                resp = requests.post(
                    url, headers=headers, json=body, timeout=30,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Status check request failed: {}", exc)
                raise RuntimeError(
                    f"Status check request failed: {exc}"
                ) from exc

            data = resp.json()

            error = data.get("error", {})
            if error.get("code") != "ok":
                error_msg = (
                    error.get("message") or error.get("code", "unknown")
                )
                logger.error("TikTok status check failed: {}", error_msg)
                raise RuntimeError(
                    f"TikTok status check failed: {error_msg}"
                )

            result = data.get("data", {})
            status = result.get("status")

            if status == "PUBLISH_COMPLETE":
                logger.info(
                    "Post published successfully (publish_id={})",
                    publish_id,
                )
                return result

            if status == "SEND_TO_USER_INBOX":
                logger.info(
                    "Post sent to user inbox (publish_id={})",
                    publish_id,
                )
                return result

            if status == "FAILED":
                fail_reason = result.get("fail_reason", "unknown")
                logger.error(
                    "Post publish failed (publish_id={}, reason={})",
                    publish_id, fail_reason,
                )
                raise RuntimeError(
                    f"TikTok publish failed: {fail_reason}"
                )

            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)

    def fetch_video_analytics(self, video_ids: list[str]) -> dict:
        if not video_ids:
            return {}

        url = (
            f"{self.BASE_URL}/video/query/"
            f"?fields=id,title,view_count,like_count,comment_count,share_count"
        )
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "filters": {
                "video_ids": video_ids,
            },
        }

        logger.debug("Fetching analytics for {} video(s)", len(video_ids))

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Analytics fetch request failed: {}", exc)
            raise RuntimeError(f"Analytics fetch request failed: {exc}") from exc

        data = resp.json()

        error = data.get("error", {})
        if error.get("code") != "ok":
            error_msg = error.get("message") or error.get("code", "unknown")
            logger.error("TikTok analytics query failed: {}", error_msg)
            raise RuntimeError(f"TikTok analytics query failed: {error_msg}")

        videos = data.get("data", {}).get("videos", [])
        result = {}
        for video in videos:
            vid = video.get("id")
            if vid:
                result[vid] = {
                    "view_count": video.get("view_count", 0),
                    "like_count": video.get("like_count", 0),
                    "comment_count": video.get("comment_count", 0),
                    "share_count": video.get("share_count", 0),
                }

        logger.info("Fetched analytics for {}/{} video(s)", len(result), len(video_ids))
        return result

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
