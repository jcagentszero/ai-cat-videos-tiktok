"""
pipeline/digest.py
──────────────────
Daily digest report summarizing pipeline runs (posted videos, failures).

Usage:
  python main.py --digest
"""

import smtplib
from datetime import datetime
from email.message import EmailMessage

from config import settings
from storage.manager import StorageManager
from utils.logger import logger


def generate_daily_digest(date_str=None, storage=None):
    if storage is None:
        storage = StorageManager()

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    runs = storage.get_runs_for_date(date_str)

    total = len(runs)
    successful = [
        r for r in runs
        if r.get("result", {}).get("status") in ("published", "dry_run")
    ]
    failed = [
        r for r in runs
        if r.get("result", {}).get("status") == "failed"
    ]

    lines = [
        f"=== Daily Digest: {date_str} ===",
        f"Total runs: {total}",
        f"Successful: {len(successful)}",
        f"Failed: {len(failed)}",
    ]

    if successful:
        lines.append("")
        lines.append("--- Posted Videos ---")
        for run in successful:
            result = run.get("result", {})
            lines.append(
                f"  [{result.get('status', '?')}] {result.get('caption', 'N/A')}"
                f" -- {run.get('video_path', 'N/A')}"
            )

    if failed:
        lines.append("")
        lines.append("--- Failures ---")
        for run in failed:
            result = run.get("result", {})
            lines.append(
                f"  [{result.get('error', 'unknown error')}]"
                f" prompt={run.get('prompt', 'N/A')!r}"
            )

    if not runs:
        lines.append("")
        lines.append("No pipeline runs recorded for this date.")

    report = "\n".join(lines)

    logger.info("Daily digest for {}:\n{}", date_str, report)

    if settings.NOTIFY_EMAIL:
        _send_digest_email(date_str, report)

    return {
        "date": date_str,
        "total": total,
        "successful": len(successful),
        "failed": len(failed),
        "report": report,
    }


def _send_digest_email(date_str, report):
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Pipeline Daily Digest: {date_str}"
        msg["From"] = "pipeline@localhost"
        msg["To"] = settings.NOTIFY_EMAIL
        msg.set_content(report)
        with smtplib.SMTP("localhost") as smtp:
            smtp.send_message(msg)
        logger.info("Daily digest email sent to {}", settings.NOTIFY_EMAIL)
    except Exception as e:
        logger.warning(
            "Failed to send digest email: [{}] {}",
            type(e).__name__, e,
        )
