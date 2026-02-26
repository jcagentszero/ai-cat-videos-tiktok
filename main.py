"""
main.py
───────
Entry point for the AI cat videos pipeline.

Usage:
  python main.py                  # run one video with scheduled prompt
  python main.py --prompt "..."   # override the prompt
  python main.py --dry-run        # generate but don't post
  python main.py --category funny # use a specific prompt category
  python main.py --digest         # print daily run summary
  python main.py --analytics      # fetch TikTok analytics for recent posts
"""

import argparse
import sys

from config.settings import validate_config
from utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(description="AI Cat Videos → TikTok Pipeline")
    parser.add_argument("--prompt",   type=str,  default=None, help="Override generation prompt")
    parser.add_argument("--category", type=str,  default=None, help="Prompt category: funny|playful|cute")
    parser.add_argument("--dry-run",  action="store_true",      help="Generate video but skip posting")
    parser.add_argument("--auth",     action="store_true",      help="Run TikTok OAuth flow to get tokens")
    parser.add_argument("--count",    type=int,  default=1,     help="Number of videos to generate")
    parser.add_argument("--schedule", action="store_true",      help="Run as daemon on POST_SCHEDULE_CRON schedule")
    parser.add_argument("--digest",   action="store_true",      help="Print daily run summary digest")
    parser.add_argument("--analytics", action="store_true",     help="Fetch TikTok analytics for recent posts")
    return parser.parse_args()


def main():
    args = parse_args()

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

    if args.prompt and args.category:
        logger.error("--prompt and --category are mutually exclusive")
        sys.exit(1)

    try:
        validate_config(dry_run=args.dry_run)
    except ValueError as e:
        logger.error("Configuration error: {}", e)
        sys.exit(1)

    if args.dry_run:
        import config.settings as _settings
        _settings.DRY_RUN = True

    prompt = args.prompt
    if args.category:
        from prompts.prompt_manager import PromptManager, VALID_CATEGORIES
        if args.category.lower() not in VALID_CATEGORIES:
            logger.error("Unknown category '{}'. Valid: {}",
                         args.category, ", ".join(sorted(VALID_CATEGORIES)))
            sys.exit(1)
        pm = PromptManager()
        prompt, _ = pm.consume_prompt(args.category.lower())
        logger.info("Selected prompt from category '{}'", args.category)

    from pipeline.runner import Pipeline
    for i in range(args.count):
        try:
            result = Pipeline().run(prompt=prompt)
            logger.info("Run {}/{} complete (status={})",
                        i + 1, args.count, result["status"])
        except Exception as e:
            logger.error("Run {}/{} failed: {}", i + 1, args.count, e)
            sys.exit(1)


if __name__ == "__main__":
    main()
