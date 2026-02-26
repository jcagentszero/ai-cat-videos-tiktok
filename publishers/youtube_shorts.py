"""
publishers/youtube_shorts.py
────────────────────────────
YouTube Shorts publishing — stub for future expansion.
"""

from pathlib import Path


class YouTubeShortsPublisher:
    """Handles video publishing to YouTube Shorts."""

    def __init__(self):
        raise NotImplementedError("YouTubeShortsPublisher is not yet implemented")

    def publish(self, video_path: Path, caption: str, hashtags: list[str]) -> dict:
        raise NotImplementedError("YouTubeShortsPublisher.publish is not yet implemented")
