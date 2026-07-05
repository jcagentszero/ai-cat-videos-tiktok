# AI Cat Videos — TikTok Pipeline

Two-lane pipeline for posting Nika (a grumpy-faced, secretly sweet Exotic
Shorthair) videos to TikTok.

- **AI lane** — hand-written multi-shot markdown scripts are staged as a
  manual render package for [Agent Opus](https://agent.opus.pro) (no
  generation API exists — see `specs/opus-api-notes.md`), then published
  once the rendered video is dropped back in.
- **Real-footage lane** — a local video of your own cat is uploaded to
  [OpusClip](https://opus.pro) and auto-cut into short clips.

## Architecture

```
prompts/scripts/available/*.md  → script pool (id/title/logline/caption/hook/hashtags/duration)
         ↓
prompts/script_manager.py       → consume-on-use script pool
         ↓
pipeline/handoff.py             → stages script.txt + Nika's reference photos under handoff/pending/<id>/
         ↓                        (human renders in the Agent Opus UI)
handoff/inbox/<id>.mp4           → human drops the finished video here
         ↓
pipeline/runner.py               → validate video → build caption/hashtags → publish
         ↓
publishers/tiktok.py             → TikTok Content Posting API
         ↓
handoff/done/<id>/                → archived script package + video

clippers/opusclip.py            → real-footage lane: upload → OpusClip clip project → download clips
scheduler/cron.py                → daily: publish_inbox() then prepare() if nothing pending
main.py                          → CLI entry point
```

## Setup

```bash
# 1. Clone repo
git clone git@github.com:jcagentszero/ai-cat-videos-tiktok.git
cd ai-cat-videos-tiktok

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your Agent Opus / OpusClip and TikTok credentials

# 5. Add Nika's reference photos (see reference/nika/README.md)

# 6. Stage the first script (dry run — no side effects, just peeks the pool)
python main.py --prepare --dry-run
```

## The AI lane: manual Agent Opus handoff

Agent Opus has no rendering API — it's a UI-only tool — so the pipeline
stages everything a human needs to render the video there, then picks the
finished file back up:

```bash
# 1. Stage the next (or a specific) script + Nika's reference photos
python main.py --prepare
python main.py --prepare --script belly-rub-betrayal

# This writes handoff/pending/<id>/ containing:
#   script.txt        — full script text with [CAT] replaced by Nika's persona description
#   <id>.md            — a copy of the original script markdown
#   <reference photos>
#   INSTRUCTIONS.md    — step-by-step render instructions

# 2. Render it in the Agent Opus UI following INSTRUCTIONS.md

# 3. Save the finished video EXACTLY as handoff/inbox/<id>.mp4

# 4. Publish everything that has arrived in the inbox
python main.py --publish
```

`--publish` validates each video, builds the caption + hashtags from the
script, posts to TikTok, and archives the script package + video under
`handoff/done/<id>/`. Each script is isolated — if one video fails
validation or upload, it's logged and left pending for retry; the rest of
the batch still publishes.

## The real-footage lane: OpusClip

```bash
python main.py --clip path/to/raw-footage.mp4
```

Uploads the video, creates an OpusClip clip project tagged with `cat` +
Nika's name, polls until clips are ready, and downloads them to
`output/clips/<project_id>/`.

## Writing scripts

Scripts are markdown files with YAML frontmatter, one file per video, kept
in `prompts/scripts/available/`. See `prompts/scripts/available/*.md` for
working examples and `prompts/script.py` for the parser. Required
frontmatter keys: `id`, `title`, `logline`, `caption`, `hook`, `hashtags`,
`duration_seconds`. The body is a series of:

```
## Shot N — Label (m:ss–m:ss)

> Shot description. Use `[CAT]` as a placeholder — it's replaced with
> Nika's persona description at render time (characters/nika.md).

- **Audio:** ...
- **Text overlay:** "..."
```

Consuming a script (`--prepare`, non-dry-run) moves its file from
`prompts/scripts/available/` to `prompts/scripts/used/` so it's never
picked twice.

## Environment variables

See `.env.example` for the full list; the ones that matter most:

- `AGENT_OPUS_API_KEY` (or `OPUS_API_KEY`), `OPUS_ORG_ID` — Opus (opus.pro)
  credentials, shared by both the Agent Opus UI handoff and the OpusClip
  API
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, plus the OAuth tokens
  obtained via `python main.py --auth` — see `TIKTOK_SANDBOX_*` for the
  `--sandbox` flag
- `HANDOFF_DIR` — root of the `pending/`, `inbox/`, `done/` handoff folders
  (default `handoff`)
- `REFERENCE_PHOTOS_DIR` — Nika's reference photos for the handoff package
  (default `reference/nika`)
- `DRY_RUN` — `prepare` peeks the pool without consuming a script or
  writing anything; `publish_inbox` validates but skips the actual TikTok
  post and archive step

## Reference photos

Drop 3–10 clear photos of Nika in `reference/nika/` (`.jpg`/`.jpeg`/`.png`,
max 10MB each — gitignored, only the README there is committed). They're
attached to the Agent Opus handoff package for character consistency.

## Scheduling

```bash
python main.py --schedule
```

Runs `scheduler/cron.py` on `POST_SCHEDULE_CRON` (default 6 PM daily). Each
scheduled run publishes anything ready in the inbox, then stages the next
script if nothing is currently pending. TikTok analytics are collected
separately every 6 hours (`python main.py --analytics`).

## Requirements

- Python 3.11+
- Agent Opus (opus.pro) account for manual rendering + OpusClip API access
  for the real-footage lane
- TikTok Developer account with `video.upload` (+ `video.publish` in
  production; the TikTok sandbox only supports `video.upload`)

## CLI reference

```bash
python main.py                        # daily routine: publish inbox, then prepare next script
python main.py --dry-run              # peek/validate but don't post or mutate the pool
python main.py --schedule             # run as a daemon on POST_SCHEDULE_CRON
python main.py --prepare [--script ID]# stage next (or specific) script + photos for Opus rendering
python main.py --publish              # publish rendered videos from handoff/inbox to TikTok
python main.py --clip <video.mp4>     # upload local footage and let OpusClip cut it into clips
python main.py --digest               # print daily run summary
python main.py --analytics            # fetch TikTok analytics for recent posts
python main.py --auth                 # run the TikTok OAuth flow
python main.py --sandbox              # use TikTok sandbox credentials (combine with other flags)
```

## Planned Expansion

- [ ] Instagram Reels
- [ ] YouTube Shorts
- [ ] X (Twitter)
