# Implementation Plan — ai-cat-videos-tiktok

## Priority Queue

<!-- Ordered by dependency. Top task should be worked on next. -->

1. ~~**Config validation** — raise clear errors if required env vars missing at startup~~ ✅
2. ~~**Structured logging** — configure loguru with file rotation and console output~~ ✅
3. ~~**StorageManager methods** — next_video_path, save_run, get_recent_prompts~~ ✅
4. **Veo 3 integration** — ~~initialize client~~, poll jobs, download videos
5. **TikTok publishing** — OAuth flow, token persistence, upload + post
6. **Pipeline assembly** — wire generator + publisher + storage, add DRY_RUN mode
7. **Scheduling** — cron/APScheduler, cleanup, daily digest

## Discoveries

<!-- Architectural insights, risks, blockers found during planning/building -->

- `config/settings.py` uses aligned-assignment style (E221); pre-existing, not worth reformatting
- `validate_config()` reads module attrs at call time via `sys.modules` so values can be patched in tests
- `setup_logging()` runs at import time of `utils/logger.py`; call again to reconfigure (idempotent via `logger.remove()`)
- **Veo 3 API confirmed (Feb 2025):**
  - SDK: `google-genai` (not `google-cloud-aiplatform`); `from google import genai`
  - Model ID: `veo-3.0-generate-001` (production), `veo-3.0-fast-generate-001` (fast variant)
  - Veo 3.1 also available: `veo-3.1-generate-001` (higher quota: 50 req/min vs 10)
  - Endpoint: `predictLongRunning` (async); poll with `fetchPredictOperation` (REST) or `client.operations.get()` (SDK)
  - Quota: 10 requests/min per region for Veo 3.0; up to 4 videos per request (production)
  - Durations: 4, 6, or 8 seconds; resolutions: 720p, 1080p; aspect ratios: 16:9, 9:16
  - Audio generation supported via `generateAudio: true` (Veo 3+ only)
  - Typical generation time: 2-5 minutes per video; poll every 10-15 seconds
  - Region default `us-central1` is fine; `global` endpoint also available
  - Env vars for SDK: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=True`

## Completed

<!-- Tasks that have been finished -->

- **Config validation** — `validate_config()` in `config/settings.py`, wired into `main.py`, 9 tests in `tests/test_config.py`
- **Structured logging** — `setup_logging()` in `utils/logger.py`, console (stderr, LOG_LEVEL) + file rotation (daily, 30-day retention, DEBUG), 5 tests in `tests/test_logger.py`
- **StorageManager.next_video_path** — date-stamped `video_YYYYMMDD_NNN.mp4` naming with auto-incrementing sequence, 6 tests in `tests/test_storage.py`
- **StorageManager.save_run** — appends run records (timestamp, prompt, video_path, result) to `logs/run_history.json` with corrupt-file recovery, 6 tests in `tests/test_storage.py`
- **StorageManager.get_recent_prompts** — reads last N prompts from run history with corrupt-file and malformed-record resilience, 6 tests in `tests/test_storage.py`
- **VeoGenerator.__init__** — loads service account credentials via `google.oauth2.service_account`, creates `genai.Client(vertexai=True)` with explicit project/region/credentials, stores `self.client` and `self.model`, 6 tests in `tests/test_veo.py`
