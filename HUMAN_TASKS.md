# Human Tasks — Manual Steps Required

These tasks require human action (account creation, credentials, config) and cannot be completed by wiggum. They are listed in roughly the order they'll be needed.

---

## Phase 1 — Foundation

- [x] Create `.env` file from `.env.example` and fill in real values

---

## Phase 2 — Video Generation (Agent Opus handoff + OpusClip)

- [ ] Get an Opus (opus.pro) account/API key and set `AGENT_OPUS_API_KEY` (+ `OPUS_ORG_ID` for multi-org accounts) in `.env` — used by both the Agent Opus UI handoff and the OpusClip real-footage lane (`--clip`)
- [ ] Drop Nika's reference photos into `reference/nika/` for the manual handoff package

---

## Phase 3 — TikTok Publishing

- [x] Create TikTok Developer account at developers.tiktok.com
- [x] Create TikTok app and obtain client key / client secret
- [x] Set `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env`
- [ ] Complete initial OAuth flow to obtain access + refresh tokens
- [ ] Verify token storage is working (check `tokens.json` after first auth)

---

## Phase 5 — Scheduling & Automation

- [ ] Set up deployment environment (VPS, cloud VM, or always-on machine)
- [ ] Configure cron or systemd timer for scheduled runs
- [ ] Verify logs are rotating and disk space is managed

---

## Ongoing

- [ ] Monitor TikTok API rate limits and adjust posting schedule if needed
- [ ] Renew TikTok app review / permissions if required by TikTok policy changes
