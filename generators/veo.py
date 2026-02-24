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
  https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos
  (Confirm Veo 3 endpoint and SDK method names when GA)

TODO: implement
"""

from pathlib import Path
from config import settings


class VeoGenerator:
    """Wraps Google Veo 3 video generation API."""

    def __init__(self):
        # TODO: initialize Google Cloud AI Platform client
        # from google.cloud import aiplatform
        # aiplatform.init(project=settings.GCP_PROJECT_ID, location=settings.VEO_REGION)
        raise NotImplementedError

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
        raise NotImplementedError

    def _poll_job(self, job_id: str, timeout: int = 300) -> str:
        """Poll Veo job until complete, return video URI. TODO: implement."""
        raise NotImplementedError

    def _download_video(self, gcs_uri: str, dest: Path) -> Path:
        """Download video from GCS URI to local path. TODO: implement."""
        raise NotImplementedError
