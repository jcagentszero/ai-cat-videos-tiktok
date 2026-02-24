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

RUN_LOG = settings.ROOT_DIR / "logs" / "run_history.json"


class StorageManager:

    def __init__(self):
        settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def save_run(self, prompt: str, video_path: Path, result: dict) -> None:
        """
        Append a run record to run_history.json.
        TODO: implement
        """
        raise NotImplementedError

    def get_recent_prompts(self, n: int = 10) -> list[str]:
        """
        Return the last n prompts used, to avoid repeats.
        TODO: implement
        """
        raise NotImplementedError

    def next_video_path(self) -> Path:
        """
        Return the next output file path, e.g. output/video_20260224_001.mp4
        TODO: implement
        """
        raise NotImplementedError

    def cleanup_old_videos(self, keep_last: int = 30) -> None:
        """
        Delete old video files keeping the most recent `keep_last`.
        TODO: implement
        """
        raise NotImplementedError
