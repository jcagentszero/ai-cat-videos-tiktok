"""
publishers/instagram.py
───────────────────────
Instagram Reels publishing — stub for future expansion.
"""

from pathlib import Path


class InstagramPublisher:
    """Handles video publishing to Instagram Reels."""

    def __init__(self):
        raise NotImplementedError("InstagramPublisher is not yet implemented")

    def publish(self, video_path: Path, caption: str, hashtags: list[str]) -> dict:
        raise NotImplementedError("InstagramPublisher.publish is not yet implemented")
