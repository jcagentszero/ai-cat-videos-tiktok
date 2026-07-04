# Agent Opus API — Phase 0 Spike Findings (2026-07-04)

## Verdict

**There is no API-key-accessible script-to-video generation endpoint.** Agent Opus
generation (s2v) is only reachable with a browser user-session JWT, not the org
API key. The documented API surface (help.opus.pro sitemap, fully enumerated)
covers clipping, censor jobs, thumbnail generative-jobs, collections, transcripts,
brand templates, and social posting — no s2v.

## What the API key CAN do (verified live, key from clip.opus.pro dashboard)

Base: `https://api.opus.pro/api`, header `Authorization: Bearer <AGENT_OPUS_API_KEY>`

| Endpoint | Result |
|---|---|
| `GET /quotas` | 200 — returns s2v/aimg/storyMode/promptEnhance quota state |
| `GET /ao-auth/user-info` | 200 — org id, user id, plan (PRO), permissions |
| `GET /collections?q=mine` | authenticated (param-validated) |
| `POST /clip-projects` (documented) | not re-verified, documented to work |
| Social posting endpoints (documented) | `POST /post-tasks`, `POST /publish-schedules`, `GET /social-accounts` |

Account facts (at spike time): plan PRO; org `org_1jrk1s4vlTotR4loN939N`;
s2v quota = 2 per 12h window + 3 sign-up bonus (expires 2026-07-21);
aimg = 3/day + 7 bonus.

## What the API key CANNOT do (verified live)

- `GET/POST /api/project` (the real Agent Opus generation route used by
  agent.opus.pro) → 401 "User not authenticated" even with
  `X-OPUS-ORG-ID`/`X-OPUS-USER-ID` headers. It requires the SPA's session JWT
  (obtained via cookie-authed `/api/ao-auth/bootstrap`).
- `POST /api/mcp` → 401 invalid_token (MCP endpoint expects OAuth, not API keys).

## How the web app generates (from agent.opus.pro JS bundles, for reference)

- `POST https://api.opus.pro/api/project` with payload:
  `{initialText, voice, attachmentIds, style, avatarId, bgmEnabled, createUseCase,
    hookTemplateName, enableCaption, isLongTake, longTakeInput, longTakeRatio, projectTier}`
- Progress: SSE `GET /api/agent/progress/watch-bulk/{projectId}`
- Status: `GET /api/agent/{projectId}/status`; mid-generation interaction:
  `POST /api/agent/{projectId}/send-text`
- Asset upload: `POST /api/media/generate-temp-upload-url` (presigned-URL pattern)
- Headers: `Authorization: Bearer <session JWT>`, `X-OPUS-ORG-ID`, `X-OPUS-USER-ID`

Reverse-engineering the session JWT is possible but fragile (breaks on logout /
auth changes) and against the grain of their auth design — not recommended for a
daily cron pipeline.

## Implications for the pipeline

Generation cannot be fully automated with the current PRO API key. Viable paths:

1. **Hybrid**: pipeline produces render-ready scripts + Nika reference photos;
   human pastes into Agent Opus UI (2 s2v/12h quota); pipeline watches a
   drop-folder for the finished mp4 → validates → posts to TikTok. Social posting
   could even go through Opus's own `POST /post-tasks` API.
2. **Ask Opus for API access**: `enterprise:key:*` permissions exist in their
   RBAC; their OpenClaw blog implies partner API access for Agent Opus. Support
   request may unlock a documented path (likely Business/Enterprise plan).
3. **Different generation backend with a real API** (Veo was removed 2026-07-04;
   Sora/Runway/Kling/Luma alternatives exist).
