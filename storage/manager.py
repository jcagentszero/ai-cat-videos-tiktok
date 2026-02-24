"""
storage/manager.py
──────────────────
Manages local video file storage and run history.

Responsibilities:
  - Create and organize output/ directory
  - Save run metadata (prompt, video path, publish result, timestamp)
  - Provide history lookup to avoid duplicate prompts
  - Clean up old videos to manage disk space

TODO: implement
"""

import json
from datetime import datetime
from pathlib import Path
from config import settings
from utils.logger import logger

RUN_LOG = settings.ROOT_DIR / "logs" / "run_history.json"


class StorageManager:

    def __init__(self):
        settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def save_run(self, prompt: str, video_path: Path, result: dict) -> None:
        """
        Append a run record to run_history.json.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "video_path": str(video_path),
            "result": result,
        }

        try:
            if RUN_LOG.exists():
                history = json.loads(RUN_LOG.read_text())
            else:
                history = []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read {}, starting fresh: {}", RUN_LOG, exc)
            history = []

        history.append(record)

        try:
            RUN_LOG.write_text(json.dumps(history, indent=2) + "\n")
            logger.info("Saved run record for prompt: {!r}", prompt[:80])
        except OSError as exc:
            logger.error("Failed to write run history to {}: {}", RUN_LOG, exc)
            raise

    def get_recent_prompts(self, n: int = 10) -> list[str]:
        """
        Return the last n prompts used, to avoid repeats.
        """
        try:
            if not RUN_LOG.exists():
                return []
            history = json.loads(RUN_LOG.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read {}, returning empty history: {}", RUN_LOG, exc)
            return []

        prompts = [r["prompt"] for r in history if isinstance(r, dict) and "prompt" in r]
        return prompts[-n:]

    def next_video_path(self) -> Path:
        """
        Return the next output file path, e.g. output/video_20260224_001.mp4
        """
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"video_{today}_"

        existing = sorted(settings.OUTPUT_DIR.glob(f"{prefix}*.mp4"))
        if existing:
            last = existing[-1].stem
            try:
                seq = int(last.rsplit("_", 1)[1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1

        path = settings.OUTPUT_DIR / f"{prefix}{seq:03d}.mp4"
        logger.debug("Next video path: {}", path)
        return path

    def cleanup_old_videos(self, keep_last: int = 30) -> None:
        """
        Delete old video files keeping the most recent `keep_last`.
        TODO: implement
        """
        raise NotImplementedError
