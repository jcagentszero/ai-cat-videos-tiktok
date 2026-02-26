"""
pipeline/analytics_collector.py
───────────────────────────────
Fetches TikTok video analytics (views, likes, etc.) for published videos
after a configurable delay (default 24h) and logs results to run history.

Usage:
  python main.py --analytics
"""

from config import settings
from publishers.tiktok import TikTokPublisher
from storage.manager import StorageManager
from utils.logger import logger


def collect_analytics(storage=None):
    if storage is None:
        storage = StorageManager()

    delay = settings.ANALYTICS_DELAY_HOURS
    runs = storage.get_runs_needing_analytics(delay_hours=delay)

    if not runs:
        logger.info("No runs need analytics collection (delay={}h)", delay)
        return {"collected": 0, "failed": 0}

    logger.info("Found {} run(s) needing analytics", len(runs))

    publisher = TikTokPublisher()
    publisher.access_token = publisher.refresh_token()

    video_id_map = {}
    for run in runs:
        result = run.get("result", {})
        publish_result = result.get("publish_result", {})
        video_id = publish_result.get("video_id")
        publish_id = publish_result.get("publish_id")
        if video_id and publish_id:
            video_id_map[video_id] = publish_id

    video_ids = list(video_id_map.keys())

    try:
        stats = publisher.fetch_video_analytics(video_ids)
    except RuntimeError as exc:
        logger.error("Failed to fetch analytics: {}", exc)
        return {"collected": 0, "failed": len(video_ids)}

    collected = 0
    failed = 0

    for video_id, analytics in stats.items():
        publish_id = video_id_map.get(video_id)
        if not publish_id:
            continue

        if storage.update_run_analytics(publish_id, analytics):
            logger.info(
                "Analytics for video_id={}: views={}, likes={}",
                video_id,
                analytics.get("view_count", 0),
                analytics.get("like_count", 0),
            )
            collected += 1
        else:
            logger.warning("Failed to update analytics for publish_id={}", publish_id)
            failed += 1

    not_found = len(video_ids) - len(stats)
    if not_found > 0:
        logger.warning("{} video(s) not found in TikTok API response", not_found)
        failed += not_found

    logger.info("Analytics collection complete: {} collected, {} failed", collected, failed)
    return {"collected": collected, "failed": failed}
