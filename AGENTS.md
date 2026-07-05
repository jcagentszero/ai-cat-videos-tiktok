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
- **AI lane**: `pipeline/handoff.py` — stages scripts + Nika's reference photos for manual Agent Opus rendering, picks up the finished mp4 from `handoff/inbox/`
- **Real-footage lane**: `clippers/opusclip.py` — OpusClip REST client (upload → clip project → poll → download)
- **Captions**: `Pipeline._build_caption` in `pipeline/runner.py` — builds caption + deduped hashtags from the script's own caption/hook/hashtags plus `BASE_HASHTAGS` and Nika's brand hashtags
- **Publishers**: `publishers/tiktok.py` — TikTok Content Posting API
- **Publishers (stubs)**: `publishers/instagram.py`, `publishers/youtube_shorts.py` — future platform stubs (NotImplementedError)
- **Pipeline**: `pipeline/runner.py` — two-lane orchestrator: `prepare`/`publish_inbox` (AI lane) + `clip_footage` (real-footage lane)
- **Storage**: `storage/manager.py` — local file management and run history
- **Scripts**: `prompts/script.py` (parser) + `prompts/script_manager.py` (pool of markdown scripts in `prompts/scripts/available/`, consume-on-use into `prompts/scripts/used/`)
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

- Agent Opus has no rendering API (UI-only) — see `specs/opus-api-notes.md`; the AI lane is a manual handoff (`--prepare` → render in the Agent Opus UI → drop the mp4 in `handoff/inbox/<id>.mp4` → `--publish`)
- TikTok OAuth tokens stored in `publishers/token_store.py`
- Rate limits: TikTok has daily post limits; OpusClip polling backs off up to `OPUS_POLL_TIMEOUT`
- `validate_config(dry_run=True)` skips TikTok var checks — use when testing the AI lane without posting
- Use `.venv/bin/python` to run lint/tests (system python lacks project deps)
- Smoke tests (`pytest -m smoke`) hit real APIs and require TikTok credentials; unit tests auto-skip them
- TikTok OAuth: `python main.py --auth` or `python -m publishers.oauth`; requires `http://localhost:8080/callback` registered as redirect URI in TikTok app settings
- TikTok API has no separate "publish" endpoint — `post_info` (caption, privacy) goes in the same `/v2/post/publish/video/init/` call as `source_info`; use `_create_post` (not `_init_upload`) for direct posting
- **Analytics**: `python main.py --analytics` fetches TikTok stats; scheduler runs every 6h; requires `video.list` TikTok scope
