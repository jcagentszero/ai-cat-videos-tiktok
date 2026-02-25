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
import smtplib
import traceback
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

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
            Result dict: {prompt, video_path, caption, hashtags,
                          publish_result, status}
        """
        video_path = None

        try:
            # 1. Select prompt
            try:
                if prompt is None:
                    prompt = self._select_prompt()
                logger.info("Pipeline run started with prompt: {!r}", prompt[:80])
            except Exception as e:
                self._handle_error("select_prompt", e)
                raise

            # 2. Generate video
            try:
                video_path = self.generator.generate(prompt)
                logger.info("Video generated: {}", video_path)
            except Exception as e:
                self._handle_error("generate", e)
                raise

            # 3. Build caption and hashtags
            try:
                caption, hashtags = self._build_caption(prompt)
            except Exception as e:
                self._handle_error("build_caption", e)
                raise

            # 4. Publish (skip if dry_run)
            publish_result = None
            if self.dry_run:
                logger.info(
                    "DRY_RUN: skipping publish — would have posted: "
                    "video={}, caption={!r}, hashtags={}",
                    video_path, caption, hashtags,
                )
                status = "dry_run"
            else:
                try:
                    publish_result = self.publisher.publish(
                        video_path, caption, hashtags,
                    )
                    status = "published"
                except Exception as e:
                    self._handle_error("publish", e)
                    raise
        except Exception as e:
            self._save_failure(prompt, video_path, e)
            raise

        # 5. Save run record (only reached on success)
        result = {
            "prompt": prompt,
            "video_path": str(video_path),
            "caption": caption,
            "hashtags": hashtags,
            "publish_result": publish_result,
            "status": status,
        }
        try:
            self.storage.save_run(prompt, video_path, result)
        except Exception as e:
            self._handle_error("save_run", e)
            raise

        logger.info("Pipeline run complete (status={})", status)
        return result

    def _save_failure(self, prompt, video_path, error):
        fail_result = {
            "prompt": prompt,
            "video_path": str(video_path) if video_path else None,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
        }
        try:
            self.storage.save_run(
                prompt or "unknown",
                video_path or Path("."),
                fail_result,
            )
        except Exception as save_err:
            logger.debug("Could not save failure record: {}", save_err)

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

    BASE_HASHTAGS = ["catvideos", "catsoftiktok", "aiart", "aigenerated"]

    CATEGORY_HASHTAGS = {
        "cozy": ["cozycat", "sleepycat", "catlover"],
        "playful": ["playfulcat", "kitten", "catplay"],
        "dramatic": ["cinematic", "catmood", "aesthetic"],
        "funny": ["funnycat", "catmemes", "catsbeingcats"],
        "cute": ["cutecat", "kittenlife", "adorable"],
    }

    def _build_caption(self, prompt: str) -> tuple[str, list[str]]:
        caption = prompt.split(",")[0].strip()

        category = None
        for name, prompts in CATEGORY_MAP.items():
            if prompt in prompts:
                category = name
                break

        hashtags = list(self.BASE_HASHTAGS)
        if category:
            hashtags.extend(self.CATEGORY_HASHTAGS.get(category, []))

        logger.info("Built caption ({} chars, {} hashtags, category={})",
                    len(caption), len(hashtags), category or "unknown")
        return caption, hashtags

    def _handle_error(self, step: str, error: Exception) -> None:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        logger.error(
            "Pipeline error at step '{}': [{}] {}",
            step, type(error).__name__, error,
        )
        logger.debug("Traceback for '{}':\n{}", step, "".join(tb))

        if not settings.NOTIFY_EMAIL:
            return

        try:
            msg = EmailMessage()
            msg["Subject"] = f"Pipeline error: {step}"
            msg["From"] = "pipeline@localhost"
            msg["To"] = settings.NOTIFY_EMAIL
            msg.set_content(
                f"Step: {step}\n"
                f"Error: {type(error).__name__}: {error}\n\n"
                f"{''.join(tb)}"
            )
            with smtplib.SMTP("localhost") as smtp:
                smtp.send_message(msg)
            logger.info("Error notification sent to {}", settings.NOTIFY_EMAIL)
        except Exception as mail_err:
            logger.warning(
                "Failed to send error notification: [{}] {}",
                type(mail_err).__name__, mail_err,
            )
