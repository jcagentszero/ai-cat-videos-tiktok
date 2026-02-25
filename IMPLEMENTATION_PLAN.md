# Implementation Plan — ai-cat-videos-tiktok

## Priority Queue

<!-- Ordered by dependency. Top task should be worked on next. -->

1. ~~**Config validation** — raise clear errors if required env vars missing at startup~~ ✅
2. ~~**Structured logging** — configure loguru with file rotation and console output~~ ✅
3. ~~**StorageManager methods** — next_video_path, save_run, get_recent_prompts~~ ✅
4. ~~**Veo 3 integration** — initialize client, poll jobs, download videos, generate end-to-end~~ ✅
5. **TikTok Developer App setup** — create app at developers.tiktok.com, get client key/secret ⏳ (manual — needs human)
6. ~~**TikTok publishing** — ~~OAuth flow~~, ~~token persistence~~, ~~token refresh~~, ~~init upload~~, ~~chunk upload~~, ~~post~~, ~~status check~~, ~~publish (e2e)~~~ ✅
7. ~~**Pipeline.__init__** — wire generator + publisher + storage, DRY_RUN mode~~ ✅
7b. **Pipeline.run** — orchestrate generate → store → publish, with DRY_RUN skip
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
- **TikTok chunk upload**: `PUT {upload_url}` with `Content-Type: video/mp4`, `Content-Length`, `Content-Range: bytes 0-{size-1}/{size}`; single-chunk strategy sends entire file; response 201=complete, 206=partial (multi-chunk), 403=URL expired, 416=range mismatch; upload URL valid for 1 hour; 300s timeout recommended for large files
- **TikTok status check**: `POST /v2/post/publish/status/fetch/` with `{"publish_id": "..."}` body; terminal statuses: `PUBLISH_COMPLETE`, `SEND_TO_USER_INBOX`, `FAILED` (with `fail_reason`); non-terminal: `PROCESSING_UPLOAD`, `PROCESSING_DOWNLOAD`; rate limit 30 req/min per user; polling uses exponential backoff (5s initial, 1.5x factor, 15s cap) with 120s default timeout
- **TikTok create post**: TikTok API has NO separate "publish" endpoint — `post_info` must be included in the same `/v2/post/publish/video/init/` call alongside `source_info`; `_create_post` signature changed from `(publish_id, caption)` to `(file_size, caption, privacy_level)` since init returns `publish_id` rather than accepting it; `_init_upload` remains for upload-only (inbox) scenarios; `_create_post` handles direct posting with `post_info` (title, privacy_level, disable_duet/comment/stitch, is_aigc=True); default privacy is `SELF_ONLY` (required for unaudited apps); valid levels: `PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, `FOLLOWER_OF_CREATOR`, `SELF_ONLY`; `publish()` flow should use `_create_post` (not `_init_upload`) → `_upload_video` → `_check_status`
- **TikTok publish e2e**: `publish()` refreshes token first (updates `self.access_token`), validates file exists and is non-empty, formats hashtags into caption (strips leading `#` to avoid `##`), then calls `_create_post` → `_upload_video` → `_check_status`; returns `{"publish_id", "status", "video_path"}`
- **Pipeline.__init__**: `TikTokPublisher.__init__` `NotImplementedError` removed — it now loads `access_token` and `open_id` from settings (these get overwritten by `refresh_token()` in `publish()`); existing tests using `object.__new__` still work since they bypass `__init__` entirely; `Pipeline(dry_run=True)` sets `self.publisher = None` to skip TikTok init when credentials unavailable
- **Pipeline._select_prompt**: uses `DAY_SCHEDULE` (weekday → category) and `CATEGORY_MAP` (category → prompt list) from `cat_prompts.py`; deduplicates against `storage.get_recent_prompts()` (default last 10); three-tier fallback: 1) scheduled category minus recent, 2) all prompts minus recent, 3) reuse from scheduled category; `CATEGORY_MAP` and `DAY_SCHEDULE` extracted as module-level constants in `cat_prompts.py` (previously local vars inside functions)
- **Pipeline._build_caption**: extracts first comma-delimited clause of prompt as caption text (subject description without camera/lighting/audio directions); hashtags built from `BASE_HASHTAGS` (always included) + `CATEGORY_HASHTAGS` (added when prompt found in `CATEGORY_MAP`); hashtags are bare strings (no `#` prefix) — `TikTokPublisher.publish()` prepends `#` when formatting; unknown prompts (not in any category) get only base hashtags; 9 tests in `tests/test_pipeline.py`

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
- **Chunk upload** — `TikTokPublisher._upload_video(upload_url, video_path)` in `publishers/tiktok.py`: reads file bytes, PUTs to upload_url with `Content-Type: video/mp4`, `Content-Range`, `Content-Length` headers; validates 200/201 response; handles file read errors, HTTP errors, and non-success status codes; 10 tests in `tests/test_tiktok.py`
- **Create post** — `TikTokPublisher._create_post(file_size, caption, privacy_level)` in `publishers/tiktok.py`: POSTs to `/v2/post/publish/video/init/` with both `post_info` (title, privacy_level, disable_duet/comment/stitch, is_aigc=True) and `source_info` (FILE_UPLOAD, single-chunk); defaults to `SELF_ONLY` privacy for unaudited apps; validates `error.code == "ok"` and presence of `publish_id`/`upload_url`; 12 tests in `tests/test_tiktok.py`
- **Status check** — `TikTokPublisher._check_status(publish_id, timeout=120)` in `publishers/tiktok.py`: POSTs to `/v2/post/publish/status/fetch/` with exponential backoff polling (5s initial, 1.5x factor, 15s cap); returns result dict on `PUBLISH_COMPLETE` or `SEND_TO_USER_INBOX`; raises `RuntimeError` on `FAILED` (with `fail_reason`); raises `TimeoutError` on timeout; validates `error.code == "ok"` for API errors; 13 tests in `tests/test_tiktok.py`
- **Publish (e2e)** — `TikTokPublisher.publish(video_path, caption, hashtags)` in `publishers/tiktok.py`: refreshes token, validates file, formats hashtags into caption, orchestrates `_create_post` → `_upload_video` → `_check_status`; returns dict with `publish_id`, `status`, `video_path`; 13 tests in `tests/test_tiktok.py`
- **TikTok smoke test** — `tests/test_tiktok_smoke.py`: generates 1s test video via ffmpeg, uploads to TikTok with `SELF_ONLY` privacy via `publish()`, asserts terminal status; auto-skips when credentials or ffmpeg unavailable; `pytest.mark.smoke` marker; 1 test
- **Pipeline.__init__** — `pipeline/runner.py`: accepts optional `dry_run` param (defaults to `settings.DRY_RUN`), creates `StorageManager`, `VeoGenerator`, and conditionally `TikTokPublisher` (None when dry_run); `TikTokPublisher.__init__` updated to remove `NotImplementedError`; 11 tests in `tests/test_pipeline.py`
- **Pipeline._select_prompt** — `pipeline/runner.py`: scheduled category selection via `DAY_SCHEDULE` with three-tier dedup fallback (category → all → reuse); `CATEGORY_MAP` and `DAY_SCHEDULE` extracted as module-level constants in `prompts/cat_prompts.py`; 8 tests in `tests/test_pipeline.py`
- **Pipeline._build_caption** — `pipeline/runner.py`: extracts first comma-clause as caption, adds base + category-specific hashtags; 9 tests in `tests/test_pipeline.py`
