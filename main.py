"""
main.py
───────
Entry point for the AI cat videos pipeline.

Usage:
  python main.py                        # run one daily pipeline pass
  python main.py --dry-run              # peek/validate but don't post
  python main.py --digest               # print daily run summary
  python main.py --analytics            # fetch TikTok analytics for recent posts
  python main.py --sandbox              # use TikTok sandbox credentials
  python main.py --prepare              # stage next script + photos for Opus rendering
  python main.py --prepare --script ID  # stage a specific script by id
  python main.py --publish              # publish rendered videos from handoff/inbox to TikTok
  python main.py --clip <video.mp4>     # upload a local video and let OpusClip cut it into clips
"""

import argparse
import sys

from config.settings import validate_config
from utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(description="AI Cat Videos → TikTok Pipeline")
    parser.add_argument("--dry-run",  action="store_true",      help="Generate video but skip posting")
    parser.add_argument("--auth",     action="store_true",      help="Run TikTok OAuth flow to get tokens")
    parser.add_argument("--count",    type=int,  default=1,     help="Number of videos to generate")
    parser.add_argument("--schedule", action="store_true",      help="Run as daemon on POST_SCHEDULE_CRON schedule")
    parser.add_argument("--digest",   action="store_true",      help="Print daily run summary digest")
    parser.add_argument("--analytics", action="store_true",     help="Fetch TikTok analytics for recent posts")
    parser.add_argument("--sandbox",   action="store_true",     help="Use TikTok sandbox credentials")
    parser.add_argument("--prepare",  action="store_true",      help="Stage the next script + photos for Agent Opus rendering")
    parser.add_argument("--publish",  action="store_true",      help="Publish rendered videos from handoff/inbox to TikTok")
    parser.add_argument("--clip",     type=str,  default=None,  help="Upload a local video and let OpusClip cut it into clips")
    parser.add_argument("--script",   type=str,  default=None,  help="Specific script id (with --prepare)")
    # Retired flags — old cron entries fail loudly with guidance:
    parser.add_argument("--prompt",   type=str,  default=None,  help=argparse.SUPPRESS)
    parser.add_argument("--category", type=str,  default=None,  help=argparse.SUPPRESS)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.sandbox:
        from config.settings import activate_sandbox
        activate_sandbox()
        logger.info("Using TikTok sandbox credentials")

    if args.auth:
        from publishers.oauth import run_oauth_flow
        try:
            run_oauth_flow()
        except Exception as e:
            logger.error("OAuth flow failed: {}", e)
            sys.exit(1)
        return

    if args.schedule:
        try:
            validate_config(dry_run=False)
        except ValueError as e:
            logger.error("Configuration error: {}", e)
            sys.exit(1)
        from scheduler.cron import run_scheduler
        run_scheduler()
        return

    if args.digest:
        from pipeline.digest import generate_daily_digest
        generate_daily_digest()
        return

    if args.analytics:
        from pipeline.analytics_collector import collect_analytics
        try:
            result = collect_analytics()
            logger.info(
                "Analytics collection done: {} collected, {} failed",
                result["collected"], result["failed"],
            )
        except Exception as e:
            logger.error("Analytics collection failed: {}", e)
            sys.exit(1)
        return

    if args.prompt or args.category:
        logger.error(
            "--prompt/--category were replaced by the script pipeline. "
            "Use --prepare [--script <id>], --publish, or --clip <video>."
        )
        sys.exit(1)

    if args.script and not args.prepare:
        logger.error("--script requires --prepare")
        sys.exit(1)

    try:
        validate_config(dry_run=args.dry_run)
    except ValueError as e:
        logger.error("Configuration error: {}", e)
        sys.exit(1)

    if args.dry_run:
        import config.settings as _settings
        _settings.DRY_RUN = True

    from pipeline.runner import Pipeline

    if args.clip:
        from pathlib import Path
        video = Path(args.clip)
        if not video.is_file():
            logger.error("Video not found: {}", video)
            sys.exit(1)
        try:
            result = Pipeline().clip_footage(video)
            logger.info("Clipping done: {} clips (project {})",
                        len(result["clips"]), result["project_id"])
        except Exception as e:
            logger.error("Clipping failed: {}", e)
            sys.exit(1)
        return

    if args.publish:
        try:
            results = Pipeline().publish_inbox()
            logger.info("Published {} video(s)", len(results))
        except Exception as e:
            logger.error("Publish failed: {}", e)
            sys.exit(1)
        return

    if args.prepare:
        for i in range(args.count):
            try:
                result = Pipeline().prepare(script_id=args.script)
                logger.info("Prepared {}/{}: '{}' — {}",
                            i + 1, args.count,
                            result["script_id"], result.get("handoff_dir", ""))
            except Exception as e:
                logger.error("Prepare {}/{} failed: {}", i + 1, args.count, e)
                sys.exit(1)
        return

    # Default: daily routine (used by --schedule too)
    for i in range(args.count):
        try:
            result = Pipeline().run()
            logger.info("Run {}/{} complete (status={})",
                        i + 1, args.count, result["status"])
        except Exception as e:
            logger.error("Run {}/{} failed: {}", i + 1, args.count, e)
            sys.exit(1)


if __name__ == "__main__":
    main()
