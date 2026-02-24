# Human Tasks — Manual Steps Required

These tasks require human action (account creation, credentials, config) and cannot be completed by wiggum. They are listed in roughly the order they'll be needed.

---

## Phase 1 — Foundation

- [ ] Create `.env` file from `.env.example` and fill in real values

---

## Phase 2 — Video Generation (Veo 3)

- [ ] Set up GCP project with Vertex AI / Imagen / Veo 3 API enabled
- [ ] Create GCP service account and download credentials JSON
- [ ] Set `GOOGLE_APPLICATION_CREDENTIALS` path in `.env`
- [ ] Confirm Veo 3 quota limits and billing are active

---

## Phase 3 — TikTok Publishing

- [ ] Create TikTok Developer account at developers.tiktok.com
- [ ] Create TikTok app and obtain client key / client secret
- [ ] Set `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env`
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
