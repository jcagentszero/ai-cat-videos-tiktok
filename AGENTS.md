# AGENTS.md — ai-cat-videos-tiktok

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run pipeline
python main.py

# Run with dry-run (no publishing)
python main.py --dry-run

# Run as scheduled daemon
python main.py --schedule
```

## Validation

```bash
# Lint
python -m flake8 --max-line-length=120 .

# Type check (if mypy installed)
python -m mypy --ignore-missing-imports .

# Tests
python -m pytest tests/ -v
```

## Codebase Patterns

- **Config**: `config/settings.py` — env-based configuration via python-dotenv
- **Generators**: `generators/veo.py` — Veo 3 video generation (Google Cloud AI)
- **Captions**: `generators/caption.py` — LLM-powered caption generation (Anthropic Claude)
- **Publishers**: `publishers/tiktok.py` — TikTok Content Posting API
- **Publishers (stubs)**: `publishers/instagram.py`, `publishers/youtube_shorts.py` — future platform stubs (NotImplementedError)
- **Pipeline**: `pipeline/runner.py` — orchestrates generate -> store -> publish
- **Storage**: `storage/manager.py` — local file management and run history
- **Prompts**: `prompts/cat_prompts.py` — prompt library for cat video generation
- **Utils**: `utils/logger.py` — structured logging with loguru
- **Validation**: `utils/video_validator.py` — MP4 integrity + TikTok size/duration checks (ffprobe optional)
- **Digest**: `pipeline/digest.py` — daily run summary report (successes + failures, optional email)
- **Analytics**: `pipeline/analytics_collector.py` — fetches TikTok view/like counts and logs to run history
- **Scheduler**: `scheduler/cron.py` — APScheduler daemon with CronTrigger from POST_SCHEDULE_CRON
- **Entry point**: `main.py` — CLI argument parsing and pipeline invocation

## Conventions

- Use loguru for all logging (not stdlib logging)
- Env vars loaded from `.env` via python-dotenv
- Video output goes to `output/` directory (date-stamped filenames)
- Run history stored in `logs/run_history.json`

## Operational Notes

- Veo 3 API requires GCP service account credentials
- TikTok OAuth tokens stored in `publishers/token_store.py`
- Rate limits: Veo 3 has per-minute quotas, TikTok has daily post limits
- `validate_config(dry_run=True)` skips TikTok var checks — use when testing GCP-only flows
- Use `.venv/bin/python` to run lint/tests (system python lacks project deps)
- Veo 3 SDK is `google-genai` (not `google-cloud-aiplatform`); model ID is `veo-3.0-generate-001`
- Smoke tests (`pytest -m smoke`) hit real APIs and require GCP credentials; unit tests auto-skip them
- TikTok OAuth: `python main.py --auth` or `python -m publishers.oauth`; requires `http://localhost:8080/callback` registered as redirect URI in TikTok app settings
- TikTok API has no separate "publish" endpoint — `post_info` (caption, privacy) goes in the same `/v2/post/publish/video/init/` call as `source_info`; use `_create_post` (not `_init_upload`) for direct posting
- **Caption LLM**: `generators/caption.py` uses Anthropic Claude; falls back to first-comma-clause if `ANTHROPIC_API_KEY` not set; default model is `claude-haiku-4-5-20251001`
- **Analytics**: `python main.py --analytics` fetches TikTok stats; scheduler runs every 6h; requires `video.list` TikTok scope
