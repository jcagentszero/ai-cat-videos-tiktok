# AI Cat Videos — TikTok Pipeline
## Task Queue (ordered by dependency)

Tasks are meant to be processed sequentially — each builds on the last.
Format: `- [ ] Task <!-- files: relevant/file.py -->`

---

## 🔴 Phase 0 — Repo Housekeeping

---

## 🔴 Phase 1 — Foundation (must complete before anything works)

---

## 🟡 Phase 2 — Video Generation (Veo 3)

- [ ] Add retry logic to Veo generation (tenacity) for transient API errors <!-- files: generators/veo.py -->
- [ ] Write smoke test: generate one video, confirm file exists and is valid MP4 <!-- files: generators/veo.py -->

---

## 🟡 Phase 3 — TikTok Publishing

- [ ] Create TikTok Developer account and app at developers.tiktok.com, obtain client key/secret <!-- files: .env.example -->
- [ ] Implement OAuth 2.0 authorization code flow to get initial access + refresh tokens <!-- files: publishers/tiktok.py -->
- [ ] Implement token_store.py — JSON file read/write for OAuth token persistence <!-- files: publishers/token_store.py -->
- [ ] Implement TikTokPublisher.refresh_token — auto-refresh before expiry, persist via token_store <!-- files: publishers/tiktok.py, publishers/token_store.py -->
- [ ] Implement TikTokPublisher._init_upload — call Content Posting API init endpoint <!-- files: publishers/tiktok.py -->
- [ ] Implement TikTokPublisher._upload_video — chunk upload to TikTok upload URL <!-- files: publishers/tiktok.py -->
- [ ] Implement TikTokPublisher._create_post — submit post with caption and privacy settings <!-- files: publishers/tiktok.py -->
- [ ] Implement TikTokPublisher._check_status — poll publish status until live or failed <!-- files: publishers/tiktok.py -->
- [ ] Implement TikTokPublisher.publish — full end-to-end wrapper <!-- files: publishers/tiktok.py -->
- [ ] Write smoke test: upload a short test video, confirm it appears in TikTok drafts <!-- files: publishers/tiktok.py -->

---

## 🟡 Phase 4 — Pipeline Assembly

- [ ] Implement Pipeline.__init__ — wire up generator, publisher, storage instances <!-- files: pipeline/runner.py -->
- [ ] Implement Pipeline._select_prompt — use scheduled selector with history deduplication <!-- files: pipeline/runner.py, prompts/cat_prompts.py -->
- [ ] Implement Pipeline._build_caption — generate caption text and hashtag list from prompt <!-- files: pipeline/runner.py -->
- [ ] Implement Pipeline._handle_error — structured error logging with optional email notification <!-- files: pipeline/runner.py, utils/logger.py -->
- [ ] Implement Pipeline.run — full end-to-end: prompt → generate → store → publish → log <!-- files: pipeline/runner.py -->
- [ ] Implement DRY_RUN mode — skip publishing step, log what would have been posted <!-- files: pipeline/runner.py, config/settings.py -->
- [ ] Wire up main.py argument parsing and Pipeline invocation <!-- files: main.py -->

---

## 🟢 Phase 5 — Scheduling & Automation

- [ ] Add cron job or APScheduler to run pipeline on POST_SCHEDULE_CRON schedule <!-- files: main.py -->
- [ ] Implement StorageManager.cleanup_old_videos — delete videos older than keep_last to manage disk space <!-- files: storage/manager.py -->
- [ ] Add run summary report (daily digest of what was posted, any failures) <!-- files: pipeline/runner.py, utils/logger.py -->

---

## 🟢 Phase 6 — Quality & Extras

- [ ] Expand prompt library — add 10+ prompts per category with Veo-optimized language <!-- files: prompts/cat_prompts.py -->
- [ ] LLM-generated captions — call Claude/GPT to write unique captions per video instead of static text <!-- files: pipeline/runner.py -->
- [ ] Add video validation step — confirm MP4 is non-corrupt and meets TikTok size/duration limits before upload <!-- files: pipeline/runner.py -->
- [ ] Add TikTok analytics fetching — pull view/like counts 24h after posting, log to run history <!-- files: publishers/tiktok.py, storage/manager.py -->
- [ ] Multi-platform scaffold — add publishers/instagram.py and publishers/youtube_shorts.py as empty stubs for future expansion <!-- files: publishers/ -->

---

## ✅ Done

- [x] Rename wiggum_loop.py → wiggum_glp1.py and update internal references <!-- files: wiggum_glp1.py -->
- [x] Create wiggum_cat_videos.py — wiggum loop targeting ai-cat-videos-tiktok/TASKS.md <!-- files: wiggum_cat_videos.py -->
- [x] Implement config validation — raise clear errors if required env vars are missing at startup <!-- files: config/settings.py -->
- [x] Set up structured logging — configure loguru with file rotation and console output <!-- files: utils/logger.py -->
- [x] Implement StorageManager.next_video_path — date-stamped output file naming <!-- files: storage/manager.py -->
- [x] Implement StorageManager.save_run — write run records to logs/run_history.json <!-- files: storage/manager.py -->
- [x] Implement StorageManager.get_recent_prompts — read history to avoid prompt repetition <!-- files: storage/manager.py -->
- [x] Research and confirm Veo 3 API endpoint, SDK method names, and quota limits in GCP console <!-- files: generators/veo.py -->
- [x] Implement VeoGenerator.__init__ — initialize Google Cloud AI Platform client with service account credentials <!-- files: generators/veo.py -->
- [x] Implement VeoGenerator._poll_job — poll generation job status with exponential backoff until complete or timeout <!-- files: generators/veo.py -->
- [x] Implement VeoGenerator._download_video — download finished video from GCS URI to local output/ <!-- files: generators/veo.py -->
- [x] Implement VeoGenerator.generate — full end-to-end: submit prompt, poll, download, return path <!-- files: generators/veo.py -->
<!-- Completed tasks moved here -->
