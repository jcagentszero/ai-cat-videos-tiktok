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

TODO: implement
"""

import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.cloud import storage as gcs
from google.genai import types
from google.oauth2 import service_account

from config import settings
from utils.logger import logger


class VeoGenerator:
    """Wraps Google Veo 3 video generation API."""

    def __init__(self):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GCP_CREDENTIALS
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

        TODO:
          1. Submit generation request to Veo 3 endpoint
          2. Poll job status until complete or timeout
          3. Download video to settings.OUTPUT_DIR / <unique_filename>.mp4
          4. Return the path
        """
        logger.info(
            "Starting video generation (duration={}s) for prompt: {!r}",
            duration_seconds, prompt[:80],
        )

        try:
            operation = self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=duration_seconds,
                    aspect_ratio="9:16",
                    generate_audio=True,
                ),
            )
        except Exception as e:
            logger.error("Failed to submit Veo generation request: {}", e)
            raise

        logger.info("Veo job submitted, polling for completion")
        gcs_uri = self._poll_job(operation)

        dest = settings.OUTPUT_DIR / "video_{}.mp4".format(
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self._download_video(gcs_uri, dest)

        logger.info("Video generation complete: {}", dest)
        return dest

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

            try:
                operation = self.client.operations.get(operation)
            except Exception as e:
                logger.error("Failed to poll Veo job: {}", e)
                raise

        elapsed = time.monotonic() - start

        if operation.error:
            raise RuntimeError(
                f"Veo generation failed: {operation.error.message}"
            )

        generated_videos = operation.result.generated_videos
        if not generated_videos:
            raise RuntimeError(
                "Veo job completed but no videos were generated"
            )

        logger.info("Veo job completed in {:.1f}s", elapsed)
        return generated_videos[0].video.uri

    def _download_video(self, gcs_uri: str, dest: Path) -> Path:
        """Download video from GCS URI to local path."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        parts = gcs_uri[5:].split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        bucket_name, blob_name = parts

        try:
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
        except Exception as e:
            logger.error("Failed to download video from {}: {}", gcs_uri, e)
            raise
