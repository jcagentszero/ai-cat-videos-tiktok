# AI Cat Videos — TikTok Pipeline

Automated pipeline for generating and posting AI cat videos using **Google Veo 3** and the **TikTok Content Posting API**.

## Architecture

```
prompts/cat_prompts.py      → curated Veo 3 prompt library
         ↓
generators/veo.py           → Google Veo 3 video generation
         ↓
storage/manager.py          → local file management + run history
         ↓
publishers/tiktok.py        → TikTok Content Posting API
         ↓
pipeline/runner.py          → orchestrates all of the above
         ↓
main.py                     → CLI entry point + scheduling
```

## Setup

```bash
# 1. Clone repo
git clone git@github.com:jcagentszero/ai-cat-videos-tiktok.git
cd ai-cat-videos-tiktok

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your GCP project ID, Veo credentials, and TikTok API keys

# 5. Run (dry run first)
python main.py --dry-run
```

## Requirements

- Python 3.11+
- Google Cloud project with Veo 3 API access
- TikTok Developer account with `video.upload` + `video.publish` scopes
- Credentials:
  - `credentials/google_service_account.json` — GCP service account key
  - TikTok OAuth tokens in `.env`

## Status

🚧 **In development.** See [TASKS.md](TASKS.md) for build plan.

## Planned Expansion

- [ ] Instagram Reels
- [ ] YouTube Shorts
- [ ] X (Twitter)
