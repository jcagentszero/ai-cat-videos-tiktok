"""
pipeline/runner.py
──────────────────
Two-lane pipeline orchestrator.

AI lane (Agent Opus is UI-only — see specs/opus-api-notes.md):
  prepare()        scripts → handoff/pending/ package for manual rendering
  publish_inbox()  handoff/inbox/ videos → validate → TikTok → archive

Real-footage lane:
  clip_footage()   local video → OpusClip API → downloaded clips

Scheduler entry point:
  run()            publish_inbox(), then prepare() if nothing is pending
"""

import smtplib
import time
import traceback
from email.message import EmailMessage
from pathlib import Path

from config import settings
from characters.persona import NIKA
from clippers.opusclip import OpusClipClient
from pipeline.handoff import (
    archive_handoff,
    find_inbox_video,
    list_pending,
    load_pending_script,
    prepare_handoff,
)
from prompts.script import Script
from prompts.script_manager import ScriptManager
from publishers.tiktok import TikTokPublisher
from storage.manager import StorageManager
from utils.reference_photos import load_reference_photos
from utils.video_validator import validate_video
from utils.logger import logger


class Pipeline:
    """Two-lane pipeline: AI handoff lane + real-footage clipping lane."""

    BASE_HASHTAGS = ["catvideos", "catsoftiktok", "aiart", "aigenerated"]

    def __init__(self, dry_run=None):
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        try:
            self.storage = StorageManager()
            self.script_manager = ScriptManager()
            self.publisher = None if self.dry_run else TikTokPublisher()
            logger.info("Pipeline initialized (dry_run={})", self.dry_run)
        except Exception as e:
            logger.error("Failed to initialize Pipeline: {}", e)
            raise

    # ── AI lane ──────────────────────────────────────────────────────────

    def prepare(self, script_id: str | None = None) -> dict:
        """Stage the next script + Nika's photos for manual Agent Opus render."""
        try:
            if self.dry_run:
                script = self.script_manager.peek_script(script_id)
            else:
                script = self.script_manager.consume_script(script_id)
            photos = load_reference_photos()
            dest = prepare_handoff(script, photos)
        except Exception as e:
            self._handle_error("prepare", e)
            raise

        result = {
            "script_id": script.id,
            "title": script.title,
            "handoff_dir": str(dest),
            "status": "prepared",
        }
        self.storage.save_run(script.title, dest, result)
        logger.info("Prepared handoff for '{}' — render it in Agent Opus, "
                    "then drop the mp4 in handoff/inbox/", script.id)
        return result

    def publish_inbox(self) -> list[dict]:
        """Publish every pending script whose rendered video has arrived."""
        results = []
        for script_id in list_pending():
            video_path = find_inbox_video(script_id)
            if video_path is None:
                logger.debug("No inbox video yet for '{}'", script_id)
                continue

            script = None
            try:
                script = load_pending_script(script_id)
                validate_video(video_path)
                caption, hashtags = self._build_caption(script)

                if self.dry_run:
                    logger.info("DRY_RUN: would publish {} for '{}'",
                                video_path, script_id)
                    publish_result, status = None, "dry_run"
                else:
                    publish_result = self.publisher.publish(
                        video_path, caption, hashtags,
                    )
                    status = "published"
                    archive_handoff(script_id, video_path)
            except Exception as e:
                self._handle_error("publish_inbox", e)
                self._save_failure(script, script_id, video_path, e)
                raise

            result = {
                "prompt": script.title,
                "script_id": script.id,
                "title": script.title,
                "video_path": str(video_path),
                "caption": caption,
                "hashtags": hashtags,
                "publish_result": publish_result,
                "status": status,
            }
            self.storage.save_run(script.title, video_path, result)
            results.append(result)
        return results

    # ── Real-footage lane ────────────────────────────────────────────────

    def clip_footage(self, video: Path) -> dict:
        """Upload local footage, let OpusClip cut it, download the clips."""
        try:
            client = OpusClipClient()
            upload_id = client.upload_video(video)
            project_id = client.create_clip_project(
                upload_id,
                topic_keywords=("cat", NIKA.name.lower()),
            )
            clips = self._poll_clips(client, project_id)

            downloads = []
            for clip in clips:
                if not clip.video_url:
                    logger.warning("Clip {} has no video URL, skipping", clip.id)
                    continue
                dest = settings.OUTPUT_DIR / "clips" / project_id / f"{clip.id}.mp4"
                downloads.append(str(client.download(clip.video_url, dest)))
        except Exception as e:
            self._handle_error("clip_footage", e)
            raise

        result = {
            "prompt": f"clip:{video.name}",
            "project_id": project_id,
            "clips": downloads,
            "status": "clipped",
        }
        self.storage.save_run(f"clip:{video.name}", video, result)
        logger.info("Clipping complete: {} clips in output/clips/{}",
                    len(downloads), project_id)
        return result

    def _poll_clips(self, client, project_id: str):
        """Poll exportable clips until curation finishes. Raises TimeoutError."""
        timeout = settings.OPUS_POLL_TIMEOUT
        interval = float(settings.OPUS_POLL_INTERVAL)
        max_interval = 120.0
        start = time.monotonic()

        while True:
            clips = client.get_clips(project_id)
            if clips:
                logger.info("Project {} produced {} clips in {:.0f}s",
                            project_id, len(clips), time.monotonic() - start)
                return clips
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"OpusClip project {project_id} produced no clips "
                    f"after {timeout}s"
                )
            logger.debug("Waiting for clips (elapsed={:.0f}s)", elapsed)
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)

    # ── Scheduler entry point ────────────────────────────────────────────

    def run(self) -> dict:
        """Daily routine: post anything ready, then stage the next script."""
        published = self.publish_inbox()
        prepared = None
        if not list_pending():
            prepared = self.prepare()
        return {"published": published, "prepared": prepared, "status": "ok"}

    # ── Shared helpers ───────────────────────────────────────────────────

    def _build_caption(self, script: Script) -> tuple[str, list[str]]:
        caption = script.caption or script.hook or script.title
        hashtags = list(dict.fromkeys(
            [*self.BASE_HASHTAGS, *NIKA.hashtags, *script.hashtags]
        ))
        logger.info("Built caption ({} chars, {} hashtags) for script '{}'",
                    len(caption), len(hashtags), script.id)
        return caption, hashtags

    def _save_failure(self, script, script_id, video_path, error):
        fail_result = {
            "prompt": script.title if script else script_id,
            "script_id": script_id,
            "video_path": str(video_path) if video_path else None,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
        }
        try:
            self.storage.save_run(
                script.title if script else script_id,
                video_path or Path("."),
                fail_result,
            )
        except Exception as save_err:
            logger.debug("Could not save failure record: {}", save_err)

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
