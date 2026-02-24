# Implementation Plan — ai-cat-videos-tiktok

## Priority Queue

<!-- Ordered by dependency. Top task should be worked on next. -->

1. ~~**Config validation** — raise clear errors if required env vars missing at startup~~ ✅
2. ~~**Structured logging** — configure loguru with file rotation and console output~~ ✅
3. ~~**StorageManager methods** — next_video_path, save_run, get_recent_prompts~~ ✅
4. **Veo 3 integration** — initialize client, poll jobs, download videos
5. **TikTok publishing** — OAuth flow, token persistence, upload + post
6. **Pipeline assembly** — wire generator + publisher + storage, add DRY_RUN mode
7. **Scheduling** — cron/APScheduler, cleanup, daily digest

## Discoveries

<!-- Architectural insights, risks, blockers found during planning/building -->

- `config/settings.py` uses aligned-assignment style (E221); pre-existing, not worth reformatting
- `validate_config()` reads module attrs at call time via `sys.modules` so values can be patched in tests
- `setup_logging()` runs at import time of `utils/logger.py`; call again to reconfigure (idempotent via `logger.remove()`)

## Completed

<!-- Tasks that have been finished -->

- **Config validation** — `validate_config()` in `config/settings.py`, wired into `main.py`, 9 tests in `tests/test_config.py`
- **Structured logging** — `setup_logging()` in `utils/logger.py`, console (stderr, LOG_LEVEL) + file rotation (daily, 30-day retention, DEBUG), 5 tests in `tests/test_logger.py`
- **StorageManager.next_video_path** — date-stamped `video_YYYYMMDD_NNN.mp4` naming with auto-incrementing sequence, 6 tests in `tests/test_storage.py`
- **StorageManager.save_run** — appends run records (timestamp, prompt, video_path, result) to `logs/run_history.json` with corrupt-file recovery, 6 tests in `tests/test_storage.py`
- **StorageManager.get_recent_prompts** — reads last N prompts from run history with corrupt-file and malformed-record resilience, 6 tests in `tests/test_storage.py`
