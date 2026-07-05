"""
pipeline/handoff.py
───────────────────
AI-lane manual handoff. The pipeline can't call Agent Opus generation
directly (no API access — see specs/opus-api-notes.md), so it stages
everything a human needs to render the video in the UI, and picks the
finished file back up from an inbox folder.

Layout under settings.HANDOFF_DIR:
  pending/<script-id>/   script.txt, <script-id>.md, reference photos, INSTRUCTIONS.md
  inbox/<script-id>.mp4  the human drops the rendered video here
  done/<script-id>/      archived package + video after publishing
"""

import shutil
from pathlib import Path
from typing import Sequence

from config import settings
from prompts.script import Script, parse_script
from utils.logger import logger


class HandoffError(Exception):
    """Raised on handoff staging/pickup problems."""


def _pending_dir() -> Path:
    return settings.HANDOFF_DIR / "pending"


def _inbox_dir() -> Path:
    return settings.HANDOFF_DIR / "inbox"


def _done_dir() -> Path:
    return settings.HANDOFF_DIR / "done"


def prepare_handoff(script: Script, photos: Sequence[Path]) -> Path:
    """Stage a render-ready package for the Agent Opus UI."""
    dest = _pending_dir() / script.id
    if dest.exists():
        raise HandoffError(f"Handoff already pending for script '{script.id}'")
    dest.mkdir(parents=True)
    _inbox_dir().mkdir(parents=True, exist_ok=True)

    (dest / "script.txt").write_text(script.render())
    shutil.copy2(script.path, dest / f"{script.id}.md")
    for photo in photos:
        shutil.copy2(photo, dest / photo.name)

    inbox_target = _inbox_dir() / f"{script.id}.mp4"
    (dest / "INSTRUCTIONS.md").write_text(
        f"# Agent Opus handoff — {script.title}\n\n"
        f"1. Open https://agent.opus.pro and start a new project.\n"
        f"2. Paste the contents of script.txt as the script.\n"
        f"3. Attach every photo in this folder (Nika's reference photos).\n"
        f"4. Aspect ratio 9:16, target ~{script.duration_seconds}s.\n"
        f"5. Download the finished video and save it EXACTLY as:\n"
        f"   {inbox_target}\n"
        f"6. Run: python main.py --publish\n"
    )

    logger.info("Handoff staged for '{}' at {}", script.id, dest)
    return dest


def list_pending() -> tuple[str, ...]:
    """Script ids currently staged and awaiting a rendered video."""
    d = _pending_dir()
    if not d.is_dir():
        return ()
    return tuple(sorted(p.name for p in d.iterdir() if p.is_dir()))


def find_inbox_video(script_id: str) -> Path | None:
    """The rendered video for a script, if the human has dropped it off."""
    p = _inbox_dir() / f"{script_id}.mp4"
    return p if p.exists() else None


def load_pending_script(script_id: str) -> Script:
    """Re-parse the staged script copy (caption/hashtags for publishing)."""
    md = _pending_dir() / script_id / f"{script_id}.md"
    if not md.exists():
        raise HandoffError(f"No pending handoff for '{script_id}'")
    return parse_script(md)


def archive_handoff(script_id: str, video_path: Path) -> Path:
    """Move the pending package and its video to done/. Returns the done dir."""
    done = _done_dir() / script_id
    _done_dir().mkdir(parents=True, exist_ok=True)
    shutil.move(str(_pending_dir() / script_id), str(done))
    shutil.move(str(video_path), str(done / f"{script_id}.mp4"))
    logger.info("Handoff archived for '{}'", script_id)
    return done
