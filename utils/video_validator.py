import json
import subprocess
from pathlib import Path

from utils.logger import logger

TIKTOK_MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB
TIKTOK_MIN_DURATION = 1.0    # seconds
TIKTOK_MAX_DURATION = 600.0  # 10 minutes


class VideoValidationError(Exception):
    pass


def validate_video(video_path: Path) -> None:
    video_path = Path(video_path)

    if not video_path.exists():
        raise VideoValidationError(f"Video file not found: {video_path}")

    file_size = video_path.stat().st_size
    if file_size == 0:
        raise VideoValidationError(f"Video file is empty: {video_path}")

    _check_mp4_header(video_path)

    if file_size > TIKTOK_MAX_FILE_SIZE:
        raise VideoValidationError(
            f"Video file too large for TikTok: {file_size} bytes "
            f"(max {TIKTOK_MAX_FILE_SIZE} bytes)"
        )

    _check_duration(video_path)

    logger.info(
        "Video validated: {} ({} bytes)",
        video_path.name, file_size,
    )


def _check_mp4_header(video_path: Path) -> None:
    try:
        with open(video_path, "rb") as f:
            header = f.read(8)
    except OSError as exc:
        raise VideoValidationError(
            f"Cannot read video file: {exc}"
        ) from exc

    if len(header) < 8 or header[4:8] != b"ftyp":
        raise VideoValidationError(
            f"Invalid MP4 file (missing ftyp header): {video_path}"
        )


def _check_duration(video_path: Path) -> None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found, skipping duration check")
        return
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timed out, skipping duration check")
        return

    if result.returncode != 0:
        logger.warning(
            "ffprobe failed (rc={}), skipping duration check: {}",
            result.returncode, result.stderr.strip(),
        )
        return

    try:
        probe = json.loads(result.stdout)
        duration = float(probe["format"]["duration"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.warning("Could not parse ffprobe output, skipping duration check: {}", exc)
        return

    if duration < TIKTOK_MIN_DURATION:
        raise VideoValidationError(
            f"Video too short for TikTok: {duration:.1f}s "
            f"(min {TIKTOK_MIN_DURATION}s)"
        )

    if duration > TIKTOK_MAX_DURATION:
        raise VideoValidationError(
            f"Video too long for TikTok: {duration:.1f}s "
            f"(max {TIKTOK_MAX_DURATION}s)"
        )

    logger.debug("Video duration: {:.1f}s", duration)
