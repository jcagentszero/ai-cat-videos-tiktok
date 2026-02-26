"""
generators/veo.py
─────────────────
Google Veo 3 video generation.

Responsibilities:
  - Accept a text prompt and generation parameters
  - Submit generation job to Veo 3 API
  - Poll for completion
  - Download the resulting video to output/
  - Return a local file path

API reference:
  https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-text

SDK: google-genai (import google.genai)
  - client = genai.Client()  (uses GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI env vars)
  - client.models.generate_videos(model=..., prompt=..., config=GenerateVideosConfig(...))
  - client.operations.get(operation)  — poll until operation.done
  - video.video.save("out.mp4")  — download result

"""

import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.api_core import exceptions as google_exceptions
from google.cloud import storage as gcs
from google.genai import types
from google.oauth2 import service_account
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.logger import logger

_TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.TooManyRequests,
    google_exceptions.InternalServerError,
    google_exceptions.GatewayTimeout,
    google_exceptions.DeadlineExceeded,
)


def _log_retry(retry_state):
    logger.warning(
        "Retrying {} (attempt {}): {}",
        retry_state.fn.__name__,
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    )


_api_retry = retry(
    retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
    sleep=lambda s: time.sleep(s),
)


class VeoGenerator:
    """Wraps Google Veo 3 video generation API."""

    def __init__(self):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GCP_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            self._credentials = credentials
            self.client = genai.Client(
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=settings.VEO_REGION,
                credentials=credentials,
            )
            self.model = settings.VEO_MODEL
            logger.info(
                "VeoGenerator initialized (project={}, region={}, model={})",
                settings.GCP_PROJECT_ID, settings.VEO_REGION, self.model,
            )
        except Exception as e:
            logger.error("Failed to initialize VeoGenerator: {}", e)
            raise

    def generate(self, prompt: str, duration_seconds: int = 8) -> Path:
        """
        Generate a video from a text prompt.

        Args:
            prompt: Text description of the video to generate.
            duration_seconds: Length of video (Veo 3 max: 8s per clip).

        Returns:
            Path to the downloaded video file in output/.

        """
        logger.info(
            "Starting video generation (duration={}s) for prompt: {!r}",
            duration_seconds, prompt[:80],
        )

        operation = self._submit_job(prompt, duration_seconds)

        logger.info("Veo job submitted, polling for completion")
        video = self._poll_job(operation)

        dest = settings.OUTPUT_DIR / "video_{}.mp4".format(
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Try GCS download if URI is available, otherwise use SDK save method
        gcs_uri = video.video.uri if video.video else None
        if gcs_uri:
            self._download_video(gcs_uri, dest)
        else:
            logger.info("No GCS URI, saving video via SDK save()")
            video.video.save(str(dest))

        logger.info("Video generation complete: {} ({} bytes)", dest, dest.stat().st_size)
        return dest

    @_api_retry
    def _submit_job(self, prompt, duration_seconds):
        return self.client.models.generate_videos(
            model=self.model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=duration_seconds,
                aspect_ratio="9:16",
                resolution="720p",
                generate_audio=True,
            ),
        )

    def _poll_job(self, operation, timeout=300):
        """Poll Veo job until complete, return video URI."""
        interval = 10
        max_interval = 30
        start = time.monotonic()

        while not operation.done:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Veo generation timed out after {timeout}s"
                )

            logger.debug(
                "Polling Veo job (elapsed={:.0f}s, next_poll={:.0f}s)",
                elapsed, interval,
            )
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)

            operation = self._poll_once(operation)

        elapsed = time.monotonic() - start

        if operation.error:
            err = operation.error
            msg = err.get("message", str(err)) if isinstance(err, dict) else getattr(err, "message", str(err))
            raise RuntimeError(f"Veo generation failed: {msg}")

        generated_videos = operation.result.generated_videos
        if not generated_videos:
            raise RuntimeError(
                "Veo job completed but no videos were generated"
            )

        logger.info("Veo job completed in {:.1f}s", elapsed)
        return generated_videos[0]

    @_api_retry
    def _poll_once(self, operation):
        return self.client.operations.get(operation)

    @_api_retry
    def _download_video(self, gcs_uri: str, dest: Path) -> Path:
        """Download video from GCS URI to local path."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        parts = gcs_uri[5:].split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        bucket_name, blob_name = parts

        storage_client = gcs.Client(
            credentials=self._credentials,
            project=settings.GCP_PROJECT_ID,
        )
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))

        logger.info(
            "Downloaded video to {} ({} bytes)",
            dest, dest.stat().st_size,
        )
        return dest
