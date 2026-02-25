"""
main.py
───────
Entry point for the AI cat videos pipeline.

Usage:
  python main.py                  # run one video with scheduled prompt
  python main.py --prompt "..."   # override the prompt
  python main.py --dry-run        # generate but don't post
  python main.py --category funny # use a specific prompt category

TODO: implement argument parsing and pipeline invocation
"""

import argparse
import sys

from config.settings import validate_config
from utils.logger import logger


def parse_args():
    parser = argparse.ArgumentParser(description="AI Cat Videos → TikTok Pipeline")
    parser.add_argument("--prompt",   type=str,  default=None, help="Override generation prompt")
    parser.add_argument("--category", type=str,  default=None, help="Prompt category: cozy|playful|dramatic|funny|cute")
    parser.add_argument("--dry-run",  action="store_true",      help="Generate video but skip posting")
    parser.add_argument("--auth",     action="store_true",      help="Run TikTok OAuth flow to get tokens")
    parser.add_argument("--count",    type=int,  default=1,     help="Number of videos to generate")
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

    try:
        validate_config(dry_run=args.dry_run)
    except ValueError as e:
        logger.error("Configuration error: {}", e)
        sys.exit(1)

    # TODO: override DRY_RUN from args if --dry-run passed

    # TODO: initialize and run pipeline
    # from pipeline.runner import Pipeline
    # for _ in range(args.count):
    #     result = Pipeline().run(prompt=args.prompt)
    #     print(f"Done: {result}")

    print("Pipeline not yet implemented. See TASKS.md.")
    sys.exit(0)


if __name__ == "__main__":
    main()
