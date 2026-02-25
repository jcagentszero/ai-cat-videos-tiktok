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

import random
from datetime import datetime

from config import settings
from generators.veo import VeoGenerator
from prompts.cat_prompts import ALL_PROMPTS, CATEGORY_MAP, DAY_SCHEDULE
from publishers.tiktok import TikTokPublisher
from storage.manager import StorageManager
from utils.logger import logger


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

    def __init__(self, dry_run=None):
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN

        try:
            self.storage = StorageManager()
            self.generator = VeoGenerator()
            self.publisher = None if self.dry_run else TikTokPublisher()
            logger.info(
                "Pipeline initialized (dry_run={})", self.dry_run,
            )
        except Exception as e:
            logger.error("Failed to initialize Pipeline: {}", e)
            raise

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
        recent = set(self.storage.get_recent_prompts())

        day = datetime.now().weekday()
        category_name = DAY_SCHEDULE[day]
        pool = CATEGORY_MAP[category_name]

        available = [p for p in pool if p not in recent]
        if available:
            prompt = random.choice(available)
            logger.info("Selected prompt from '{}' ({} available)",
                        category_name, len(available))
            return prompt

        all_available = [p for p in ALL_PROMPTS if p not in recent]
        if all_available:
            prompt = random.choice(all_available)
            logger.info("Category '{}' exhausted, fell back to all prompts "
                        "({} available)", category_name, len(all_available))
            return prompt

        prompt = random.choice(pool)
        logger.warning("All prompts used recently, reusing from '{}'",
                       category_name)
        return prompt

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
