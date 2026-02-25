"""
scheduler/cron.py
─────────────────
APScheduler-based daemon that runs Pipeline on POST_SCHEDULE_CRON schedule.

Usage:
  python main.py --schedule
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from utils.logger import logger


def _parse_cron(expr: str) -> dict:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(
            f"Expected 5-field cron expression, got {len(fields)}: {expr!r}"
        )
    return {
        "minute": fields[0],
        "hour": fields[1],
        "day": fields[2],
        "month": fields[3],
        "day_of_week": fields[4],
    }


def _run_pipeline():
    from pipeline.runner import Pipeline
    try:
        result = Pipeline().run()
        logger.info("Scheduled run complete (status={})", result["status"])
    except Exception as e:
        logger.error("Scheduled run failed: {}", e)


def run_scheduler():
    cron_kwargs = _parse_cron(settings.POST_SCHEDULE_CRON)
    trigger = CronTrigger(timezone=settings.POST_TIMEZONE, **cron_kwargs)

    scheduler = BlockingScheduler(timezone=settings.POST_TIMEZONE)
    scheduler.add_job(
        _run_pipeline,
        trigger,
        id="pipeline_run",
        name="AI Cat Video Pipeline",
    )

    logger.info(
        "Scheduler started — cron={}, timezone={}",
        settings.POST_SCHEDULE_CRON,
        settings.POST_TIMEZONE,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
