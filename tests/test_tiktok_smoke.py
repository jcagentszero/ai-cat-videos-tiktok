import os
import shutil
import subprocess
from pathlib import Path

import pytest

from publishers.tiktok import TikTokPublisher
from publishers import token_store


_SKIP_REASON = (
    "TikTok smoke tests require credentials "
    "(set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, and run OAuth flow)"
)

_SKIP_FFMPEG = "ffmpeg not found (required for test video generation)"


def _has_tiktok_credentials():
    client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
    if not client_key or not client_secret:
        return False
    tokens = token_store.load_tokens()
    return bool(tokens.get("refresh_token"))


def _has_ffmpeg():
    return shutil.which("ffmpeg") is not None


def _create_test_video(directory: Path) -> Path:
    video_path = directory / "test_upload.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=1:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "1",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "64k",
            "-pix_fmt", "yuv420p",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    return video_path


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not _has_tiktok_credentials(), reason=_SKIP_REASON),
    pytest.mark.skipif(not _has_ffmpeg(), reason=_SKIP_FFMPEG),
]


class TestTikTokSmoke:
    def test_upload_video_to_drafts(self, tmp_path):
        video_path = _create_test_video(tmp_path)
        assert video_path.exists(), "Test video was not created"
        assert video_path.stat().st_size > 0, "Test video is empty"

        pub = object.__new__(TikTokPublisher)
        pub.access_token = ""

        result = pub.publish(
            video_path=video_path,
            caption="Smoke test — auto-delete",
            hashtags=["test"],
        )

        assert "publish_id" in result
        assert result["status"] in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")
        assert result["video_path"] == str(video_path)
