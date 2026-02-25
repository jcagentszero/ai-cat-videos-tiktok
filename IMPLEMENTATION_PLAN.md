# Implementation Plan — ai-cat-videos-tiktok

## Priority Queue

<!-- Ordered by dependency. Top task should be worked on next. -->

1. ~~**Config validation** — raise clear errors if required env vars missing at startup~~ ✅
2. ~~**Structured logging** — configure loguru with file rotation and console output~~ ✅
3. ~~**StorageManager methods** — next_video_path, save_run, get_recent_prompts~~ ✅
4. ~~**Veo 3 integration** — initialize client, poll jobs, download videos, generate end-to-end~~ ✅
5. **TikTok Developer App setup** — create app at developers.tiktok.com, get client key/secret ⏳ (manual — needs human)
6. **TikTok publishing** — ~~OAuth flow~~, ~~token persistence~~, ~~token refresh~~, ~~init upload~~, chunk upload + post
7. **Pipeline assembly** — wire generator + publisher + storage, add DRY_RUN mode
8. **Scheduling** — cron/APScheduler, cleanup, daily digest

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
- `_poll_job` accepts an operation object (not a string name) — `operations.get()` accepts both but passing the object preserves typed result access
- `google-cloud-storage` is a transitive dependency of `google-genai` (already installed), but added explicitly to requirements.txt for `_download_video`
- `__init__` stores `self._credentials` so GCS download can reuse the same service account credentials without re-loading from disk
- `generate()` reads `settings.OUTPUT_DIR` at call time — tests must keep the patch active during the call, not just during `__init__`
- `google.genai.types.GenerateVideosConfig` accepts snake_case params (`number_of_videos`, `duration_seconds`, `aspect_ratio`, `generate_audio`)
- Tenacity retry uses `sleep=lambda s: time.sleep(s)` to route through the module-level `time` import — tests that patch `generators.veo.time` automatically mock out tenacity's wait, avoiding real sleeps in tests
- Smoke tests use `pytest.mark.smoke` + `skipif` on credential env vars; run with `pytest -m smoke` to target only integration tests
- `_api_retry` decorator retries `ConnectionError` and Google API 429/5xx exceptions (3 attempts, exponential backoff 2-30s); non-transient errors propagate immediately
- **TikTok Developer App setup**: requires manual registration at developers.tiktok.com; Content Posting API needs `video.upload` + `video.publish` scopes; new apps start in sandbox mode; app review required for public posting; OAuth redirect URI needed for token flow
- **TikTok OAuth flow**: authorization URL is `https://www.tiktok.com/v2/auth/authorize/`, token exchange is `POST https://open.tiktokapis.com/v2/oauth/token/`; redirect URI must be registered in TikTok app settings (default: `http://localhost:8080/callback`); token exchange returns `access_token`, `refresh_token`, `open_id`, `expires_in`; `token_store.save_tokens` now accepts optional `open_id` kwarg
- `PosixPath` attributes (`read_text`, `write_text`) are read-only in Python 3.14 — use `os.chmod` or filesystem-level techniques instead of `patch.object` for testing I/O errors
- **TikTok token refresh**: same endpoint as exchange (`POST https://open.tiktokapis.com/v2/oauth/token/`) with `grant_type=refresh_token`; response shape matches initial exchange (`access_token`, `refresh_token`, `open_id`, `expires_in`); `TikTokPublisher.__init__` still raises `NotImplementedError` — use `object.__new__(TikTokPublisher)` to test `refresh_token` in isolation
- **TikTok init upload**: `POST /v2/post/publish/video/init/` with `Authorization: Bearer {token}` header; body: `{"source_info": {"source": "FILE_UPLOAD", "video_size": N, "chunk_size": N, "total_chunk_count": N}}`; response wraps data in `{"data": {...}, "error": {"code": "ok", ...}}`; `upload_url` valid for 1 hour; rate limit: 6 req/min per user; direct post endpoint (not inbox) requires `video.publish` scope; error codes include `spam_risk_too_many_pending_share` (max 5 pending in 24h)

## Completed

<!-- Tasks that have been finished -->

- **Config validation** — `validate_config()` in `config/settings.py`, wired into `main.py`, 9 tests in `tests/test_config.py`
- **Structured logging** — `setup_logging()` in `utils/logger.py`, console (stderr, LOG_LEVEL) + file rotation (daily, 30-day retention, DEBUG), 5 tests in `tests/test_logger.py`
- **StorageManager.next_video_path** — date-stamped `video_YYYYMMDD_NNN.mp4` naming with auto-incrementing sequence, 6 tests in `tests/test_storage.py`
- **StorageManager.save_run** — appends run records (timestamp, prompt, video_path, result) to `logs/run_history.json` with corrupt-file recovery, 6 tests in `tests/test_storage.py`
- **StorageManager.get_recent_prompts** — reads last N prompts from run history with corrupt-file and malformed-record resilience, 6 tests in `tests/test_storage.py`
- **VeoGenerator.__init__** — loads service account credentials via `google.oauth2.service_account`, creates `genai.Client(vertexai=True)` with explicit project/region/credentials, stores `self.client` and `self.model`, 6 tests in `tests/test_veo.py`
- **VeoGenerator._poll_job** — polls `client.operations.get(operation)` with exponential backoff (10s initial, 1.5x factor, 30s cap), raises `TimeoutError` on timeout, `RuntimeError` on operation error or empty results, returns first video URI, 7 tests in `tests/test_veo.py`
- **VeoGenerator._download_video** — parses GCS URI into bucket/blob, downloads via `google-cloud-storage` using stored credentials, creates parent dirs, logs file size, 7 tests in `tests/test_veo.py`
- **VeoGenerator.generate** — end-to-end: submits prompt to Veo 3 with 9:16 aspect ratio and audio, polls for completion, downloads to `settings.OUTPUT_DIR/video_YYYYMMDD_HHMMSS.mp4`, 6 tests in `tests/test_veo.py`
- **Veo retry logic** — tenacity `@_api_retry` on `_submit_job`, `_poll_once`, `_download_video` for transient API errors (ConnectionError, 429, 5xx); 3 attempts with exponential backoff (2-30s); 4 tests in `tests/test_veo.py`
- **Veo smoke test** — end-to-end integration test that calls real Veo API, validates output exists and has valid MP4 ftyp header; auto-skips when GCP credentials unavailable; `pytest.mark.smoke` marker; 1 test in `tests/test_veo_smoke.py`
- **TikTok OAuth flow** — `publishers/oauth.py`: `build_auth_url(state)`, `exchange_code(code)`, `run_oauth_flow()` with local callback server, CSRF state validation, and token persistence; `--auth` flag in `main.py`; `token_store.save_tokens` extended with optional `open_id`; 23 tests in `tests/test_oauth.py`
- **Token persistence** — `publishers/token_store.py`: `load_tokens()` and `save_tokens()` with JSON file read/write to `credentials/tiktok_tokens.json`; structured logging via loguru; corrupt-file recovery on load (returns `{}`); write-error propagation with logging; 12 tests in `tests/test_token_store.py`
- **Token refresh** — `TikTokPublisher.refresh_token()` in `publishers/tiktok.py`: loads tokens from `token_store`, checks `expires_at` against 5-minute buffer (`REFRESH_BUFFER_SECONDS=300`), skips if still valid, POSTs to TikTok refresh endpoint with `grant_type=refresh_token`, persists new tokens via `token_store.save_tokens()`, preserves `open_id` from stored tokens if not in refresh response; 14 tests in `tests/test_tiktok.py`
- **Init upload** — `TikTokPublisher._init_upload(file_size)` in `publishers/tiktok.py`: POSTs to `/v2/post/publish/video/init/` with `FILE_UPLOAD` source and single-chunk strategy (chunk_size=file_size), validates `error.code == "ok"` and presence of `publish_id`/`upload_url` in response, returns `data` dict; 10 tests in `tests/test_tiktok.py`
