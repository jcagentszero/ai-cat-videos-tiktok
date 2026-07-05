"""
clippers/opusclip.py
────────────────────
OpusClip REST client for the real-footage lane:
local video → upload-links → GCS resumable upload → clip project → clips.

Endpoints verified against the documented OpenAPI (see specs/opus-api-notes.md).
Clip response field names are mapped defensively; `Clip.raw` keeps the payload.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.logger import logger

UPLOAD_LINKS_PATH = "/upload-links"
CLIP_PROJECTS_PATH = "/clip-projects"
EXPORTABLE_CLIPS_PATH = "/exportable-clips"

_REQUEST_TIMEOUT = 60           # per API call
_UPLOAD_TIMEOUT = 3600          # large file PUT


class OpusClipError(Exception):
    """Non-transient OpusClip API failure."""

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OpusClipTransientError(OpusClipError):
    """Retryable failure: 429 rate limit or 5xx server error."""


def _log_retry(retry_state):
    logger.warning(
        "Retrying OpusClip API call (attempt {}): {}",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    )


_api_retry = retry(
    retry=retry_if_exception_type((OpusClipTransientError, requests.ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
    sleep=lambda s: time.sleep(s),
)


@dataclass(frozen=True)
class Clip:
    id: str
    video_url: str | None
    title: str
    raw: dict


class OpusClipClient:
    """Authenticated wrapper around the documented OpusClip REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 org_id: str | None = None):
        self.api_key = api_key if api_key is not None else settings.OPUS_API_KEY
        if not self.api_key:
            raise ValueError("AGENT_OPUS_API_KEY is not set")
        self.base_url = (base_url or settings.OPUS_API_BASE).rstrip("/")
        self.org_id = org_id if org_id is not None else settings.OPUS_ORG_ID
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        if self.org_id:
            self._session.headers["x-opus-org-id"] = self.org_id

    @_api_retry
    def _request(self, method: str, path_or_url: str, **kwargs) -> requests.Response:
        url = path_or_url if path_or_url.startswith("http") \
            else f"{self.base_url}{path_or_url}"
        resp = self._session.request(method, url, timeout=_REQUEST_TIMEOUT, **kwargs)

        if resp.status_code == 429 or resp.status_code >= 500:
            raise OpusClipTransientError(
                f"OpusClip API {resp.status_code} on {method} {url}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        if resp.status_code >= 400:
            raise OpusClipError(
                f"OpusClip API {resp.status_code} on {method} {url}: {resp.text[:200]}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        return resp

    def upload_video(self, video: Path) -> str:
        """Three-step documented upload. Returns the uploadId for clip-projects."""
        resp = self._request(
            "POST", UPLOAD_LINKS_PATH, json={"video": {"usecase": "LocalUpload"}},
        )
        data = resp.json()
        url, upload_id = data.get("url"), data.get("uploadId")
        if not url or not upload_id:
            raise OpusClipError(
                "upload-links response missing url/uploadId", body=str(data)[:500],
            )

        # Signed GCS URL — plain requests, no Opus auth header
        init = requests.post(
            url,
            headers={"x-goog-resumable": "start", "Content-Length": "0"},
            timeout=_REQUEST_TIMEOUT,
        )
        if init.status_code not in (200, 201):
            raise OpusClipError(
                f"Resumable upload init failed ({init.status_code})",
                status_code=init.status_code,
            )
        location = init.headers.get("location")
        if not location:
            raise OpusClipError("Resumable init returned no location header")

        with open(video, "rb") as f:
            put = requests.put(
                location,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=_UPLOAD_TIMEOUT,
            )
        if put.status_code not in (200, 201):
            raise OpusClipError(
                f"Video upload failed ({put.status_code})", status_code=put.status_code,
            )

        logger.info("Uploaded {} ({} bytes) → uploadId {}",
                    video.name, video.stat().st_size, upload_id)
        return str(upload_id)

    def create_clip_project(
        self,
        upload_id: str,
        *,
        topic_keywords=(),
        clip_durations=((0, 90),),
        genre: str = "Auto",
    ) -> str:
        """Create a clipping project from an uploaded video. Returns projectId."""
        payload = {
            "videoUrl": upload_id,
            "curationPref": {
                "clipDurations": [list(d) for d in clip_durations],
                "topicKeywords": list(topic_keywords),
                "genre": genre,
                "skipCurate": False,
            },
            "importPref": {"sourceLang": "auto"},
        }
        resp = self._request("POST", CLIP_PROJECTS_PATH, json=payload)
        data = resp.json()
        project_id = data.get("projectId") or data.get("id")
        if not project_id:
            raise OpusClipError(
                "clip-projects response missing project id", body=str(data)[:500],
            )
        logger.info("Clip project created: {}", project_id)
        return str(project_id)

    def get_clips(self, project_id: str) -> tuple[Clip, ...]:
        """Fetch exportable clips for a project (empty tuple while processing)."""
        resp = self._request(
            "GET",
            f"{EXPORTABLE_CLIPS_PATH}?q=findByProjectId&projectId={project_id}",
        )
        items = resp.json()
        if isinstance(items, dict):
            items = items.get("data") or items.get("clips") or []
        return tuple(
            Clip(
                id=str(c.get("id") or c.get("clipId") or i),
                video_url=c.get("videoUrl") or c.get("downloadUrl") or c.get("exportUrl"),
                title=str(c.get("title") or c.get("caption") or ""),
                raw=c,
            )
            for i, c in enumerate(items)
        )

    def download(self, url: str, dest: Path) -> Path:
        """Stream a clip to dest."""
        resp = self._request("GET", url, stream=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        logger.info("Downloaded clip to {} ({} bytes)", dest, dest.stat().st_size)
        return dest
