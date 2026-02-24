"""
pipeline/runner.py
──────────────────
Main pipeline orchestrator. Wires together:
  prompts → Veo generator → storage → TikTok publisher

Usage:
  from pipeline.runner import Pipeline
  Pipeline().run()

TODO: implement
"""

from pathlib import Path
from config import settings


class Pipeline:
    """
    End-to-end pipeline: generate video → store → publish.

    Execution order:
      1. Select prompt (scheduled or random)
      2. Generate video via Veo 3
      3. Save metadata to run log
      4. Optionally process/resize video
      5. Build caption and hashtags
      6. Publish to TikTok (unless DRY_RUN=true)
      7. Log result and notify

    TODO: implement each step
    """

    def __init__(self):
        # TODO: initialize generator, publisher, storage
        raise NotImplementedError

    def run(self, prompt: str | None = None) -> dict:
        """
        Execute the full pipeline for one video.

        Args:
            prompt: Override prompt. If None, uses scheduled selector.

        Returns:
            Result dict: {prompt, video_path, publish_id, share_url, status}

        TODO: implement
        """
        raise NotImplementedError

    def _select_prompt(self) -> str:
        """Pick prompt for this run. TODO: implement."""
        raise NotImplementedError

    def _build_caption(self, prompt: str) -> tuple[str, list[str]]:
        """
        Generate a TikTok caption and hashtag list from the prompt.
        Returns (caption_text, [hashtags]).
        TODO: implement — consider LLM-generated captions
        """
        raise NotImplementedError

    def _handle_error(self, step: str, error: Exception) -> None:
        """Log error, send notification if configured. TODO: implement."""
        raise NotImplementedError
