# Amendment 2: Two-Lane Pipeline (AI handoff + real-footage clipping)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. This amendment REPLACES Tasks 6, 7, 9, 10 of `2026-07-04-opus-migration.md` (those sections are marked SUPERSEDED there). Tasks 1–5 and 8 of the original plan are unchanged; Task 8 still executes last.

**Why:** The Phase 0 spike (specs/opus-api-notes.md) proved Agent Opus script-to-video has no API-key access. Decision: two lanes. **AI lane** — pipeline stages script + Nika's photos into a handoff folder, the human renders in the Agent Opus UI and drops the mp4 into an inbox, pipeline validates + posts to TikTok. **Real lane** — local Nika footage is uploaded via the documented OpusClip REST API (upload-links → GCS resumable → clip-projects), clips retrieved and downloaded.

## Global Constraints (in addition to the original plan's)

- OpusClip REST facts (verified live / from OpenAPI docs — see specs/opus-api-notes.md):
  - Base `https://api.opus.pro/api`, `Authorization: Bearer <key>`; optional `x-opus-org-id` header.
  - `POST /upload-links` body `{"video": {"usecase": "LocalUpload"}}` → `{url, uploadId, ...}`.
  - Resumable init: `POST <url>` with headers `x-goog-resumable: start`, `Content-Length: 0` → 201 + `location` response header (NO auth header — it's a signed GCS URL).
  - File upload: `PUT <location>` with `Content-Type: application/octet-stream`.
  - `POST /clip-projects` body `{"videoUrl": "<uploadId>", "curationPref": {...}, "importPref": {"sourceLang": "auto"}}` → project representation with `projectId`.
  - `GET /exportable-clips?q=findByProjectId&projectId=<id>` (+ `x-opus-org-id` when set) → array of clips.
  - Clip field names are NOT fully documented — map defensively (`id`/`clipId`, `videoUrl`/`downloadUrl`/`exportUrl`, `title`/`caption`) and keep the raw dict.
- Run tests: `.venv/bin/python -m pytest`. Pre-push hook runs the full suite; every commit green.

---

### Task 6: OpusClipClient — real-footage clipping REST client

**Files:**
- Create: `clippers/__init__.py` (empty), `clippers/opusclip.py`
- Modify: `config/settings.py` (add `OPUS_ORG_ID`), `.env.example`
- Test: `tests/test_opusclip.py`

**Interfaces:**
- Consumes: `settings.OPUS_API_KEY`, `settings.OPUS_API_BASE` (Task 1)
- Produces: `OpusClipClient(api_key=None, base_url=None, org_id=None)` with `upload_video(video: Path) -> str` (returns uploadId), `create_clip_project(upload_id: str, *, topic_keywords=(), clip_durations=((0, 90),), genre="Auto") -> str` (returns projectId), `get_clips(project_id: str) -> tuple[Clip, ...]`, `download(url: str, dest: Path) -> Path`. `Clip` frozen dataclass (`id: str, video_url: str | None, title: str, raw: dict`). `OpusClipError(Exception)` (attrs `status_code`, `body`), `OpusClipTransientError(OpusClipError)`. Module constants `UPLOAD_LINKS_PATH = "/upload-links"`, `CLIP_PROJECTS_PATH = "/clip-projects"`, `EXPORTABLE_CLIPS_PATH = "/exportable-clips"`.

- [ ] **Step 1: Add the org-id setting**

In `config/settings.py`, inside the `# ── Agent Opus` block after `OPUS_API_BASE`:

```python
OPUS_ORG_ID        = os.getenv("OPUS_ORG_ID", "")
```

In `.env.example`, after `OPUS_API_BASE=...`:

```bash
# Optional: org id header for multi-org accounts (x-opus-org-id)
OPUS_ORG_ID=
```

(No validate_config change — the header is optional.)

- [ ] **Step 2: Write the failing tests**

Create `tests/test_opusclip.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clippers.opusclip import (
    CLIP_PROJECTS_PATH,
    EXPORTABLE_CLIPS_PATH,
    UPLOAD_LINKS_PATH,
    Clip,
    OpusClipClient,
    OpusClipError,
    OpusClipTransientError,
)


def _make_client(org_id="org_test"):
    return OpusClipClient(api_key="ok_test", base_url="https://api.test/api",
                          org_id=org_id)


def _mock_response(status=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    resp.headers = headers or {}
    resp.text = str(json_data)
    return resp


class TestInit:
    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="AGENT_OPUS_API_KEY"):
            OpusClipClient(api_key="")

    def test_org_header_set_when_provided(self):
        client = _make_client(org_id="org_9")
        assert client._session.headers["x-opus-org-id"] == "org_9"

    def test_org_header_absent_when_empty(self):
        client = _make_client(org_id="")
        assert "x-opus-org-id" not in client._session.headers


class TestUploadVideo:
    def test_three_step_upload(self, tmp_path):
        video = tmp_path / "nika.mp4"
        video.write_bytes(b"\x00" * 128)
        client = _make_client()
        link_resp = _mock_response(200, {"url": "https://gcs.test/up", "uploadId": "up_1"})
        init_resp = _mock_response(201, headers={"location": "https://gcs.test/resume"})
        put_resp = _mock_response(200)
        with patch.object(client._session, "request", return_value=link_resp) as api, \
             patch("clippers.opusclip.requests.post", return_value=init_resp) as init, \
             patch("clippers.opusclip.requests.put", return_value=put_resp) as put:
            upload_id = client.upload_video(video)

        assert upload_id == "up_1"
        method, url = api.call_args[0]
        assert (method, url) == ("POST", f"https://api.test/api{UPLOAD_LINKS_PATH}")
        assert api.call_args[1]["json"] == {"video": {"usecase": "LocalUpload"}}
        assert init.call_args[0][0] == "https://gcs.test/up"
        assert init.call_args[1]["headers"]["x-goog-resumable"] == "start"
        assert put.call_args[0][0] == "https://gcs.test/resume"

    def test_missing_location_header_raises(self, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")
        client = _make_client()
        link_resp = _mock_response(200, {"url": "https://gcs.test/up", "uploadId": "up_1"})
        init_resp = _mock_response(201, headers={})
        with patch.object(client._session, "request", return_value=link_resp), \
             patch("clippers.opusclip.requests.post", return_value=init_resp):
            with pytest.raises(OpusClipError, match="location"):
                client.upload_video(video)

    def test_missing_upload_id_raises(self, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, {"url": "x"})):
            with pytest.raises(OpusClipError, match="uploadId"):
                client.upload_video(video)


class TestCreateClipProject:
    def test_posts_payload_returns_project_id(self):
        client = _make_client()
        resp = _mock_response(201, {"projectId": "P123"})
        with patch.object(client._session, "request", return_value=resp) as req:
            pid = client.create_clip_project(
                "up_1", topic_keywords=("cat",), clip_durations=((0, 60),),
            )
        assert pid == "P123"
        payload = req.call_args[1]["json"]
        assert payload["videoUrl"] == "up_1"
        assert payload["curationPref"]["topicKeywords"] == ["cat"]
        assert payload["curationPref"]["clipDurations"] == [[0, 60]]
        assert payload["importPref"] == {"sourceLang": "auto"}

    def test_missing_project_id_raises(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(201, {})):
            with pytest.raises(OpusClipError, match="project"):
                client.create_clip_project("up_1")


class TestGetClips:
    def test_maps_clip_fields_defensively(self):
        client = _make_client()
        items = [
            {"id": "c1", "videoUrl": "https://cdn/c1.mp4", "title": "Funny 1"},
            {"clipId": "c2", "downloadUrl": "https://cdn/c2.mp4", "caption": "Funny 2"},
        ]
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, items)) as req:
            clips = client.get_clips("P123")
        assert clips[0] == Clip(id="c1", video_url="https://cdn/c1.mp4",
                                title="Funny 1", raw=items[0])
        assert clips[1].id == "c2"
        assert clips[1].video_url == "https://cdn/c2.mp4"
        assert clips[1].title == "Funny 2"
        _, url = req.call_args[0]
        assert url == (f"https://api.test/api{EXPORTABLE_CLIPS_PATH}"
                       "?q=findByProjectId&projectId=P123")

    def test_empty_list(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, [])):
            assert client.get_clips("P123") == ()


class TestErrors:
    def test_429_is_transient_and_retried(self):
        client = _make_client()
        responses = [_mock_response(429, {}), _mock_response(200, [])]
        with patch.object(client._session, "request", side_effect=responses), \
             patch("time.sleep"):
            assert client.get_clips("P1") == ()

    def test_4xx_raises_non_transient(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(403, {})):
            with pytest.raises(OpusClipError) as exc:
                client.get_clips("P1")
            assert not isinstance(exc.value, OpusClipTransientError)


class TestDownload:
    def test_streams_to_dest(self, tmp_path):
        client = _make_client()
        resp = _mock_response(200)
        resp.iter_content.return_value = [b"a", b"b"]
        dest = tmp_path / "out" / "c.mp4"
        with patch.object(client._session, "request", return_value=resp):
            assert client.download("https://cdn/c.mp4", dest) == dest
        assert dest.read_bytes() == b"ab"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_opusclip.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clippers'`

- [ ] **Step 4: Implement**

Create empty `clippers/__init__.py`. Create `clippers/opusclip.py`:

```python
"""
clippers/opusclip.py
────────────────────
OpusClip REST client for the real-footage lane:
local video → upload-links → GCS resumable upload → clip project → clips.

Endpoints verified against the documented OpenAPI (see specs/opus-api-notes.md).
Clip response field names are mapped defensively; `Clip.raw` keeps the payload.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.logger import logger

UPLOAD_LINKS_PATH = "/upload-links"
CLIP_PROJECTS_PATH = "/clip-projects"
EXPORTABLE_CLIPS_PATH = "/exportable-clips"

_REQUEST_TIMEOUT = 60           # per API call
_UPLOAD_TIMEOUT = 3600          # large file PUT


class OpusClipError(Exception):
    """Non-transient OpusClip API failure."""

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OpusClipTransientError(OpusClipError):
    """Retryable failure: 429 rate limit or 5xx server error."""


def _log_retry(retry_state):
    logger.warning(
        "Retrying OpusClip API call (attempt {}): {}",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    )


_api_retry = retry(
    retry=retry_if_exception_type((OpusClipTransientError, requests.ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
    sleep=lambda s: time.sleep(s),
)


@dataclass(frozen=True)
class Clip:
    id: str
    video_url: str | None
    title: str
    raw: dict


class OpusClipClient:
    """Authenticated wrapper around the documented OpusClip REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 org_id: str | None = None):
        self.api_key = api_key if api_key is not None else settings.OPUS_API_KEY
        if not self.api_key:
            raise ValueError("AGENT_OPUS_API_KEY is not set")
        self.base_url = (base_url or settings.OPUS_API_BASE).rstrip("/")
        self.org_id = org_id if org_id is not None else settings.OPUS_ORG_ID
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        if self.org_id:
            self._session.headers["x-opus-org-id"] = self.org_id

    @_api_retry
    def _request(self, method: str, path_or_url: str, **kwargs) -> requests.Response:
        url = path_or_url if path_or_url.startswith("http") \
            else f"{self.base_url}{path_or_url}"
        resp = self._session.request(method, url, timeout=_REQUEST_TIMEOUT, **kwargs)

        if resp.status_code == 429 or resp.status_code >= 500:
            raise OpusClipTransientError(
                f"OpusClip API {resp.status_code} on {method} {url}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        if resp.status_code >= 400:
            raise OpusClipError(
                f"OpusClip API {resp.status_code} on {method} {url}: {resp.text[:200]}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        return resp

    def upload_video(self, video: Path) -> str:
        """Three-step documented upload. Returns the uploadId for clip-projects."""
        resp = self._request(
            "POST", UPLOAD_LINKS_PATH, json={"video": {"usecase": "LocalUpload"}},
        )
        data = resp.json()
        url, upload_id = data.get("url"), data.get("uploadId")
        if not url or not upload_id:
            raise OpusClipError(
                "upload-links response missing url/uploadId", body=str(data)[:500],
            )

        # Signed GCS URL — plain requests, no Opus auth header
        init = requests.post(
            url,
            headers={"x-goog-resumable": "start", "Content-Length": "0"},
            timeout=_REQUEST_TIMEOUT,
        )
        if init.status_code not in (200, 201):
            raise OpusClipError(
                f"Resumable upload init failed ({init.status_code})",
                status_code=init.status_code,
            )
        location = init.headers.get("location")
        if not location:
            raise OpusClipError("Resumable init returned no location header")

        with open(video, "rb") as f:
            put = requests.put(
                location,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=_UPLOAD_TIMEOUT,
            )
        if put.status_code not in (200, 201):
            raise OpusClipError(
                f"Video upload failed ({put.status_code})", status_code=put.status_code,
            )

        logger.info("Uploaded {} ({} bytes) → uploadId {}",
                    video.name, video.stat().st_size, upload_id)
        return str(upload_id)

    def create_clip_project(
        self,
        upload_id: str,
        *,
        topic_keywords=(),
        clip_durations=((0, 90),),
        genre: str = "Auto",
    ) -> str:
        """Create a clipping project from an uploaded video. Returns projectId."""
        payload = {
            "videoUrl": upload_id,
            "curationPref": {
                "clipDurations": [list(d) for d in clip_durations],
                "topicKeywords": list(topic_keywords),
                "genre": genre,
                "skipCurate": False,
            },
            "importPref": {"sourceLang": "auto"},
        }
        resp = self._request("POST", CLIP_PROJECTS_PATH, json=payload)
        data = resp.json()
        project_id = data.get("projectId") or data.get("id")
        if not project_id:
            raise OpusClipError(
                "clip-projects response missing project id", body=str(data)[:500],
            )
        logger.info("Clip project created: {}", project_id)
        return str(project_id)

    def get_clips(self, project_id: str) -> tuple[Clip, ...]:
        """Fetch exportable clips for a project (empty tuple while processing)."""
        resp = self._request(
            "GET",
            f"{EXPORTABLE_CLIPS_PATH}?q=findByProjectId&projectId={project_id}",
        )
        items = resp.json()
        if isinstance(items, dict):
            items = items.get("data") or items.get("clips") or []
        return tuple(
            Clip(
                id=str(c.get("id") or c.get("clipId") or i),
                video_url=c.get("videoUrl") or c.get("downloadUrl") or c.get("exportUrl"),
                title=str(c.get("title") or c.get("caption") or ""),
                raw=c,
            )
            for i, c in enumerate(items)
        )

    def download(self, url: str, dest: Path) -> Path:
        """Stream a clip to dest."""
        resp = self._request("GET", url, stream=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        logger.info("Downloaded clip to {} ({} bytes)", dest, dest.stat().st_size)
        return dest
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_opusclip.py tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add clippers/ tests/test_opusclip.py config/settings.py .env.example
git commit -m "feat: add OpusClipClient for real-footage upload and clipping"
git push
```

---

### Task 7: AI-lane handoff — pending exports and inbox pickup

**Files:**
- Create: `pipeline/handoff.py`
- Modify: `config/settings.py` (add `HANDOFF_DIR`), `.env.example`, `.gitignore`
- Test: `tests/test_handoff.py`

**Interfaces:**
- Consumes: `Script`, `parse_script` (Task 4)
- Produces: `prepare_handoff(script: Script, photos: Sequence[Path]) -> Path`, `list_pending() -> tuple[str, ...]`, `find_inbox_video(script_id: str) -> Path | None`, `load_pending_script(script_id: str) -> Script`, `archive_handoff(script_id: str, video_path: Path) -> Path`, `HandoffError(Exception)`. Layout: `handoff/pending/<script-id>/` (script.txt rendered, `<script-id>.md` source copy, photos, INSTRUCTIONS.md), `handoff/inbox/<script-id>.mp4`, `handoff/done/<script-id>/`.

- [ ] **Step 1: Add the setting**

`config/settings.py`, after the reference photos block:

```python
# ── AI-lane handoff (Agent Opus manual render) ───────────────────────────────
HANDOFF_DIR = ROOT_DIR / os.getenv("HANDOFF_DIR", "handoff")
```

`.env.example`:

```bash
# Folder for the Agent Opus manual handoff (pending/, inbox/, done/)
HANDOFF_DIR=handoff
```

`.gitignore`:

```
# Manual handoff working area (scripts staged for Agent Opus + rendered videos)
handoff/
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_handoff.py`:

```python
from pathlib import Path

import pytest

from pipeline import handoff
from prompts.script import parse_script


@pytest.fixture
def handoff_root(tmp_path, monkeypatch):
    from config import settings
    root = tmp_path / "handoff"
    monkeypatch.setattr(settings, "HANDOFF_DIR", root)
    return root


@pytest.fixture
def script(script_file):
    return parse_script(script_file)


@pytest.fixture
def photos(tmp_path):
    p = tmp_path / "nika1.jpg"
    p.write_bytes(b"\xff\xd8")
    return (p,)


class TestPrepareHandoff:
    def test_creates_pending_package(self, handoff_root, script, photos):
        dest = handoff.prepare_handoff(script, photos)
        assert dest == handoff_root / "pending" / script.id
        assert (dest / "script.txt").exists()
        assert (dest / f"{script.id}.md").exists()
        assert (dest / "nika1.jpg").exists()
        assert (dest / "INSTRUCTIONS.md").exists()

    def test_script_txt_is_rendered_with_persona(self, handoff_root, script, photos):
        from characters.persona import NIKA
        dest = handoff.prepare_handoff(script, photos)
        text = (dest / "script.txt").read_text()
        assert "[CAT]" not in text
        assert NIKA.description in text

    def test_duplicate_pending_raises(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        with pytest.raises(handoff.HandoffError, match=script.id):
            handoff.prepare_handoff(script, photos)


class TestPendingAndInbox:
    def test_list_pending_empty(self, handoff_root):
        assert handoff.list_pending() == ()

    def test_list_pending_sorted(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        assert handoff.list_pending() == (script.id,)

    def test_find_inbox_video_none(self, handoff_root, script):
        assert handoff.find_inbox_video(script.id) is None

    def test_find_inbox_video_found(self, handoff_root, script):
        inbox = handoff_root / "inbox"
        inbox.mkdir(parents=True)
        video = inbox / f"{script.id}.mp4"
        video.write_bytes(b"\x00")
        assert handoff.find_inbox_video(script.id) == video

    def test_load_pending_script_roundtrip(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        loaded = handoff.load_pending_script(script.id)
        assert loaded.id == script.id
        assert loaded.caption == script.caption

    def test_load_pending_unknown_raises(self, handoff_root):
        with pytest.raises(handoff.HandoffError, match="nope"):
            handoff.load_pending_script("nope")


class TestArchive:
    def test_archive_moves_pending_and_video(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        inbox = handoff_root / "inbox"
        inbox.mkdir(parents=True)
        video = inbox / f"{script.id}.mp4"
        video.write_bytes(b"\x00")

        done = handoff.archive_handoff(script.id, video)

        assert done == handoff_root / "done" / script.id
        assert (done / f"{script.id}.mp4").exists()
        assert not (handoff_root / "pending" / script.id).exists()
        assert not video.exists()
        assert handoff.list_pending() == ()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_handoff.py -v`
Expected: FAIL — `ImportError: cannot import name 'handoff'`

- [ ] **Step 4: Implement**

Create `pipeline/handoff.py`:

```python
"""
pipeline/handoff.py
───────────────────
AI-lane manual handoff. The pipeline can't call Agent Opus generation
directly (no API access — see specs/opus-api-notes.md), so it stages
everything a human needs to render the video in the UI, and picks the
finished file back up from an inbox folder.

Layout under settings.HANDOFF_DIR:
  pending/<script-id>/   script.txt, <script-id>.md, reference photos, INSTRUCTIONS.md
  inbox/<script-id>.mp4  the human drops the rendered video here
  done/<script-id>/      archived package + video after publishing
"""

import shutil
from pathlib import Path
from typing import Sequence

from config import settings
from prompts.script import Script, parse_script
from utils.logger import logger


class HandoffError(Exception):
    """Raised on handoff staging/pickup problems."""


def _pending_dir() -> Path:
    return settings.HANDOFF_DIR / "pending"


def _inbox_dir() -> Path:
    return settings.HANDOFF_DIR / "inbox"


def _done_dir() -> Path:
    return settings.HANDOFF_DIR / "done"


def prepare_handoff(script: Script, photos: Sequence[Path]) -> Path:
    """Stage a render-ready package for the Agent Opus UI."""
    dest = _pending_dir() / script.id
    if dest.exists():
        raise HandoffError(f"Handoff already pending for script '{script.id}'")
    dest.mkdir(parents=True)
    _inbox_dir().mkdir(parents=True, exist_ok=True)

    (dest / "script.txt").write_text(script.render())
    shutil.copy2(script.path, dest / f"{script.id}.md")
    for photo in photos:
        shutil.copy2(photo, dest / photo.name)

    inbox_target = _inbox_dir() / f"{script.id}.mp4"
    (dest / "INSTRUCTIONS.md").write_text(
        f"# Agent Opus handoff — {script.title}\n\n"
        f"1. Open https://agent.opus.pro and start a new project.\n"
        f"2. Paste the contents of script.txt as the script.\n"
        f"3. Attach every photo in this folder (Nika's reference photos).\n"
        f"4. Aspect ratio 9:16, target ~{script.duration_seconds}s.\n"
        f"5. Download the finished video and save it EXACTLY as:\n"
        f"   {inbox_target}\n"
        f"6. Run: python main.py --publish\n"
    )

    logger.info("Handoff staged for '{}' at {}", script.id, dest)
    return dest


def list_pending() -> tuple[str, ...]:
    """Script ids currently staged and awaiting a rendered video."""
    d = _pending_dir()
    if not d.is_dir():
        return ()
    return tuple(sorted(p.name for p in d.iterdir() if p.is_dir()))


def find_inbox_video(script_id: str) -> Path | None:
    """The rendered video for a script, if the human has dropped it off."""
    p = _inbox_dir() / f"{script_id}.mp4"
    return p if p.exists() else None


def load_pending_script(script_id: str) -> Script:
    """Re-parse the staged script copy (caption/hashtags for publishing)."""
    md = _pending_dir() / script_id / f"{script_id}.md"
    if not md.exists():
        raise HandoffError(f"No pending handoff for '{script_id}'")
    return parse_script(md)


def archive_handoff(script_id: str, video_path: Path) -> Path:
    """Move the pending package and its video to done/. Returns the done dir."""
    done = _done_dir() / script_id
    _done_dir().mkdir(parents=True, exist_ok=True)
    shutil.move(str(_pending_dir() / script_id), str(done))
    shutil.move(str(video_path), str(done / f"{script_id}.mp4"))
    logger.info("Handoff archived for '{}'", script_id)
    return done
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_handoff.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/handoff.py tests/test_handoff.py config/settings.py .env.example .gitignore
git commit -m "feat: add AI-lane handoff staging and inbox pickup"
git push
```

---

### Task 9: Pipeline — two-lane rewrite

**Files:**
- Modify: `pipeline/runner.py` (full rewrite of the class body)
- Test: `tests/test_pipeline.py` (full rewrite)

**Interfaces:**
- Consumes: `ScriptManager` (Task 5), handoff functions (Task 7), `OpusClipClient`/`Clip` (Task 6), `load_reference_photos` (Task 3), `NIKA` (Task 2), existing `validate_video`, `TikTokPublisher`, `StorageManager`, `settings.OPUS_POLL_TIMEOUT`, `settings.OPUS_POLL_INTERVAL`, `settings.OUTPUT_DIR`
- Produces:
  - `Pipeline(dry_run=None)`
  - `prepare(script_id: str | None = None) -> dict` — consume (peek when dry-run) a script, stage handoff. Result keys: `script_id`, `title`, `handoff_dir`, `status` ("prepared").
  - `publish_inbox() -> list[dict]` — for each pending id with an inbox video: validate → caption → publish → archive → save_run. Per-item result keys: `prompt` (= title, storage compat), `script_id`, `title`, `video_path`, `caption`, `hashtags`, `publish_result`, `status` ("published" | "dry_run").
  - `clip_footage(video: Path) -> dict` — upload, create clip project, poll `get_clips` until non-empty (timeout `OPUS_POLL_TIMEOUT`), download all clips to `OUTPUT_DIR/clips/<project-id>/`. Result keys: `project_id`, `clips` (list of downloaded paths as str), `status` ("clipped"). Does NOT auto-post (follow-up feature).
  - `run() -> dict` — daily routine for the scheduler: `publish_inbox()`, then `prepare()` only if nothing is pending afterward. Result: `{"published": [...], "prepared": dict | None, "status": "ok"}`.
  - `_build_caption(script) -> tuple[str, list[str]]` — caption = `script.caption or script.hook or script.title`; hashtags = order-preserving dedup of `BASE_HASHTAGS + NIKA.hashtags + script.hashtags`.

- [ ] **Step 1: Rewrite the test file (failing)**

Replace `tests/test_pipeline.py` entirely with:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.runner import Pipeline
from prompts.script import parse_script


@pytest.fixture
def sample_script(script_file):
    return parse_script(script_file)


@pytest.fixture
def mock_scripts(sample_script):
    mgr = MagicMock()
    mgr.consume_script.return_value = sample_script
    mgr.peek_script.return_value = sample_script
    with patch("pipeline.runner.ScriptManager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_handoff(sample_script):
    with patch("pipeline.runner.prepare_handoff",
               return_value=Path("/tmp/handoff/pending/x")) as prep, \
         patch("pipeline.runner.list_pending",
               return_value=(sample_script.id,)) as pending, \
         patch("pipeline.runner.find_inbox_video",
               return_value=Path("/tmp/handoff/inbox/x.mp4")) as find, \
         patch("pipeline.runner.load_pending_script",
               return_value=sample_script) as load, \
         patch("pipeline.runner.archive_handoff") as archive:
        yield {"prepare": prep, "pending": pending, "find": find,
               "load": load, "archive": archive}


@pytest.fixture
def mock_photos():
    with patch("pipeline.runner.load_reference_photos",
               return_value=(Path("/tmp/nika.jpg"),)):
        yield


@pytest.fixture
def mock_tiktok():
    pub = MagicMock()
    pub.publish.return_value = {"publish_id": "pub_1"}
    with patch("pipeline.runner.TikTokPublisher", return_value=pub):
        yield pub


@pytest.fixture
def mock_storage():
    mgr = MagicMock()
    with patch("pipeline.runner.StorageManager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_validate():
    with patch("pipeline.runner.validate_video") as v:
        yield v


@pytest.fixture
def mock_clipper():
    client = MagicMock()
    client.upload_video.return_value = "up_1"
    client.create_clip_project.return_value = "P123"
    from clippers.opusclip import Clip
    client.get_clips.return_value = (
        Clip(id="c1", video_url="https://cdn/c1.mp4", title="Funny 1", raw={}),
    )
    client.download.side_effect = lambda url, dest: dest
    with patch("pipeline.runner.OpusClipClient", return_value=client):
        yield client


ALL = ("mock_scripts", "mock_handoff", "mock_photos",
       "mock_tiktok", "mock_storage", "mock_validate", "mock_clipper")


@pytest.mark.usefixtures(*ALL)
class TestPrepare:
    def test_consumes_and_stages(self, mock_scripts, mock_handoff, mock_storage):
        result = Pipeline(dry_run=False).prepare()
        mock_scripts.consume_script.assert_called_once_with(None)
        mock_handoff["prepare"].assert_called_once()
        assert result["status"] == "prepared"
        assert result["script_id"] == "belly-rub-betrayal"
        mock_storage.save_run.assert_called_once()

    def test_dry_run_peeks(self, mock_scripts):
        Pipeline(dry_run=True).prepare()
        mock_scripts.peek_script.assert_called_once_with(None)
        mock_scripts.consume_script.assert_not_called()

    def test_script_id_forwarded(self, mock_scripts):
        Pipeline(dry_run=False).prepare(script_id="belly-rub-betrayal")
        mock_scripts.consume_script.assert_called_once_with("belly-rub-betrayal")


@pytest.mark.usefixtures(*ALL)
class TestPublishInbox:
    def test_publishes_ready_video(self, mock_handoff, mock_tiktok, mock_storage,
                                   sample_script):
        results = Pipeline(dry_run=False).publish_inbox()
        assert len(results) == 1
        r = results[0]
        assert r["status"] == "published"
        assert r["script_id"] == sample_script.id
        assert r["prompt"] == sample_script.title
        mock_tiktok.publish.assert_called_once()
        mock_handoff["archive"].assert_called_once()
        mock_storage.save_run.assert_called_once()

    def test_caption_from_script(self, mock_tiktok):
        Pipeline(dry_run=False).publish_inbox()
        _, caption, hashtags = mock_tiktok.publish.call_args[0]
        assert caption == "The belly was never an offer. It was a test."
        assert len(hashtags) == len(set(hashtags))

    def test_skips_when_no_inbox_video(self, mock_handoff, mock_tiktok):
        mock_handoff["find"].return_value = None
        results = Pipeline(dry_run=False).publish_inbox()
        assert results == []
        mock_tiktok.publish.assert_not_called()

    def test_dry_run_does_not_publish_or_archive(self, mock_handoff, mock_tiktok):
        results = Pipeline(dry_run=True).publish_inbox()
        assert results[0]["status"] == "dry_run"
        mock_tiktok.publish.assert_not_called()
        mock_handoff["archive"].assert_not_called()

    def test_validation_failure_recorded(self, mock_validate, mock_storage):
        mock_validate.side_effect = RuntimeError("bad video")
        with pytest.raises(RuntimeError):
            Pipeline(dry_run=False).publish_inbox()
        fail = mock_storage.save_run.call_args[0][2]
        assert fail["status"] == "failed"


@pytest.mark.usefixtures(*ALL)
class TestClipFootage:
    def test_full_clip_flow(self, mock_clipper, mock_storage, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        with patch("pipeline.runner.time.sleep"):
            result = Pipeline(dry_run=False).clip_footage(video)
        mock_clipper.upload_video.assert_called_once_with(video)
        mock_clipper.create_clip_project.assert_called_once()
        assert result["project_id"] == "P123"
        assert result["status"] == "clipped"
        assert len(result["clips"]) == 1

    def test_polls_until_clips_appear(self, mock_clipper, tmp_path):
        from clippers.opusclip import Clip
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        mock_clipper.get_clips.side_effect = [
            (), (),
            (Clip(id="c1", video_url="https://cdn/c1.mp4", title="t", raw={}),),
        ]
        with patch("pipeline.runner.time.sleep"):
            Pipeline(dry_run=False).clip_footage(video)
        assert mock_clipper.get_clips.call_count == 3

    def test_timeout_raises(self, mock_clipper, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        mock_clipper.get_clips.return_value = ()
        fake_clock = iter(range(0, 100000, 600))
        with patch("pipeline.runner.time.sleep"), \
             patch("pipeline.runner.time.monotonic",
                   side_effect=lambda: next(fake_clock)):
            with pytest.raises(TimeoutError):
                Pipeline(dry_run=False).clip_footage(video)


@pytest.mark.usefixtures(*ALL)
class TestRunDaily:
    def test_publishes_then_prepares_when_empty(self, mock_handoff, mock_scripts):
        # after publishing, nothing pending → prepare next
        mock_handoff["pending"].side_effect = [(mock_scripts.consume_script.return_value.id,), ()]
        result = Pipeline(dry_run=False).run()
        assert result["status"] == "ok"
        assert result["prepared"] is not None

    def test_no_prepare_while_pending(self, mock_handoff, mock_scripts):
        mock_handoff["find"].return_value = None      # video not dropped yet
        result = Pipeline(dry_run=False).run()
        assert result["prepared"] is None
        mock_scripts.consume_script.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — patch targets missing (`pipeline.runner` has no attribute `ScriptManager` etc.)

- [ ] **Step 3: Rewrite pipeline/runner.py**

Replace the file's imports and class entirely (keep `_handle_error` as-is):

```python
"""
pipeline/runner.py
──────────────────
Two-lane pipeline orchestrator.

AI lane (Agent Opus is UI-only — see specs/opus-api-notes.md):
  prepare()        scripts → handoff/pending/ package for manual rendering
  publish_inbox()  handoff/inbox/ videos → validate → TikTok → archive

Real-footage lane:
  clip_footage()   local video → OpusClip API → downloaded clips

Scheduler entry point:
  run()            publish_inbox(), then prepare() if nothing is pending
"""

import smtplib
import time
import traceback
from email.message import EmailMessage
from pathlib import Path

from config import settings
from characters.persona import NIKA
from clippers.opusclip import OpusClipClient
from pipeline.handoff import (
    archive_handoff,
    find_inbox_video,
    list_pending,
    load_pending_script,
    prepare_handoff,
)
from prompts.script import Script
from prompts.script_manager import ScriptManager
from publishers.tiktok import TikTokPublisher
from storage.manager import StorageManager
from utils.reference_photos import load_reference_photos
from utils.video_validator import validate_video
from utils.logger import logger


class Pipeline:
    """Two-lane pipeline: AI handoff lane + real-footage clipping lane."""

    BASE_HASHTAGS = ["catvideos", "catsoftiktok", "aiart", "aigenerated"]

    def __init__(self, dry_run=None):
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        try:
            self.storage = StorageManager()
            self.script_manager = ScriptManager()
            self.publisher = None if self.dry_run else TikTokPublisher()
            logger.info("Pipeline initialized (dry_run={})", self.dry_run)
        except Exception as e:
            logger.error("Failed to initialize Pipeline: {}", e)
            raise

    # ── AI lane ──────────────────────────────────────────────────────────

    def prepare(self, script_id: str | None = None) -> dict:
        """Stage the next script + Nika's photos for manual Agent Opus render."""
        try:
            if self.dry_run:
                script = self.script_manager.peek_script(script_id)
            else:
                script = self.script_manager.consume_script(script_id)
            photos = load_reference_photos()
            dest = prepare_handoff(script, photos)
        except Exception as e:
            self._handle_error("prepare", e)
            raise

        result = {
            "script_id": script.id,
            "title": script.title,
            "handoff_dir": str(dest),
            "status": "prepared",
        }
        self.storage.save_run(script.title, dest, result)
        logger.info("Prepared handoff for '{}' — render it in Agent Opus, "
                    "then drop the mp4 in handoff/inbox/", script.id)
        return result

    def publish_inbox(self) -> list[dict]:
        """Publish every pending script whose rendered video has arrived."""
        results = []
        for script_id in list_pending():
            video_path = find_inbox_video(script_id)
            if video_path is None:
                logger.debug("No inbox video yet for '{}'", script_id)
                continue

            script = None
            try:
                script = load_pending_script(script_id)
                validate_video(video_path)
                caption, hashtags = self._build_caption(script)

                if self.dry_run:
                    logger.info("DRY_RUN: would publish {} for '{}'",
                                video_path, script_id)
                    publish_result, status = None, "dry_run"
                else:
                    publish_result = self.publisher.publish(
                        video_path, caption, hashtags,
                    )
                    status = "published"
                    archive_handoff(script_id, video_path)
            except Exception as e:
                self._handle_error("publish_inbox", e)
                self._save_failure(script, script_id, video_path, e)
                raise

            result = {
                "prompt": script.title,
                "script_id": script.id,
                "title": script.title,
                "video_path": str(video_path),
                "caption": caption,
                "hashtags": hashtags,
                "publish_result": publish_result,
                "status": status,
            }
            self.storage.save_run(script.title, video_path, result)
            results.append(result)
        return results

    # ── Real-footage lane ────────────────────────────────────────────────

    def clip_footage(self, video: Path) -> dict:
        """Upload local footage, let OpusClip cut it, download the clips."""
        try:
            client = OpusClipClient()
            upload_id = client.upload_video(video)
            project_id = client.create_clip_project(
                upload_id,
                topic_keywords=("cat", NIKA.name.lower()),
            )
            clips = self._poll_clips(client, project_id)

            downloads = []
            for clip in clips:
                if not clip.video_url:
                    logger.warning("Clip {} has no video URL, skipping", clip.id)
                    continue
                dest = settings.OUTPUT_DIR / "clips" / project_id / f"{clip.id}.mp4"
                downloads.append(str(client.download(clip.video_url, dest)))
        except Exception as e:
            self._handle_error("clip_footage", e)
            raise

        result = {
            "prompt": f"clip:{video.name}",
            "project_id": project_id,
            "clips": downloads,
            "status": "clipped",
        }
        self.storage.save_run(f"clip:{video.name}", video, result)
        logger.info("Clipping complete: {} clips in output/clips/{}",
                    len(downloads), project_id)
        return result

    def _poll_clips(self, client, project_id: str):
        """Poll exportable clips until curation finishes. Raises TimeoutError."""
        timeout = settings.OPUS_POLL_TIMEOUT
        interval = float(settings.OPUS_POLL_INTERVAL)
        max_interval = 120.0
        start = time.monotonic()

        while True:
            clips = client.get_clips(project_id)
            if clips:
                logger.info("Project {} produced {} clips in {:.0f}s",
                            project_id, len(clips), time.monotonic() - start)
                return clips
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"OpusClip project {project_id} produced no clips "
                    f"after {timeout}s"
                )
            logger.debug("Waiting for clips (elapsed={:.0f}s)", elapsed)
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)

    # ── Scheduler entry point ────────────────────────────────────────────

    def run(self) -> dict:
        """Daily routine: post anything ready, then stage the next script."""
        published = self.publish_inbox()
        prepared = None
        if not list_pending():
            prepared = self.prepare()
        return {"published": published, "prepared": prepared, "status": "ok"}

    # ── Shared helpers ───────────────────────────────────────────────────

    def _build_caption(self, script: Script) -> tuple[str, list[str]]:
        caption = script.caption or script.hook or script.title
        hashtags = list(dict.fromkeys(
            [*self.BASE_HASHTAGS, *NIKA.hashtags, *script.hashtags]
        ))
        logger.info("Built caption ({} chars, {} hashtags) for script '{}'",
                    len(caption), len(hashtags), script.id)
        return caption, hashtags

    def _save_failure(self, script, script_id, video_path, error):
        fail_result = {
            "prompt": script.title if script else script_id,
            "script_id": script_id,
            "video_path": str(video_path) if video_path else None,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
        }
        try:
            self.storage.save_run(
                script.title if script else script_id,
                video_path or Path("."),
                fail_result,
            )
        except Exception as save_err:
            logger.debug("Could not save failure record: {}", save_err)

    def _handle_error(self, step: str, error: Exception) -> None:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        logger.error(
            "Pipeline error at step '{}': [{}] {}",
            step, type(error).__name__, error,
        )
        logger.debug("Traceback for '{}':\n{}", step, "".join(tb))

        if not settings.NOTIFY_EMAIL:
            return

        try:
            msg = EmailMessage()
            msg["Subject"] = f"Pipeline error: {step}"
            msg["From"] = "pipeline@localhost"
            msg["To"] = settings.NOTIFY_EMAIL
            msg.set_content(
                f"Step: {step}\n"
                f"Error: {type(error).__name__}: {error}\n\n"
                f"{''.join(tb)}"
            )
            with smtplib.SMTP("localhost") as smtp:
                smtp.send_message(msg)
            logger.info("Error notification sent to {}", settings.NOTIFY_EMAIL)
        except Exception as mail_err:
            logger.warning(
                "Failed to send error notification: [{}] {}",
                type(mail_err).__name__, mail_err,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Full suite except smoke**

Run: `.venv/bin/python -m pytest -m "not smoke" -q`
Expected: everything passes EXCEPT tests/test_main.py CLI tests tied to the old `run(prompt=...)` contract (fixed in Task 10). If ONLY those fail, commit with `--no-verify` is NOT allowed — instead fix trivial breakage or coordinate: commit AFTER confirming the only failures are the known Task 10 ones is not acceptable for the pre-push hook, so implement the minimal `main.py` compatibility in Task 10 BEFORE pushing. To keep this task self-contained and green: update the failing `tests/test_main.py` expectations minimally here if needed (e.g. `run()` no longer takes `prompt`) and note it in the report — Task 10 completes the CLI work.

- [ ] **Step 6: Commit**

```bash
git add pipeline/runner.py tests/test_pipeline.py tests/test_main.py
git commit -m "feat: two-lane pipeline — AI handoff prepare/publish + real-footage clipping"
git push
```

---

### Task 10: CLI — two-lane flags

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `Pipeline.prepare/publish_inbox/clip_footage/run` (Task 9)
- Produces: CLI flags `--prepare`, `--publish`, `--clip <path>`, `--script <id>` (only with `--prepare`); `--prompt`/`--category` removed with a migration error; no lane flag → `Pipeline.run()` daily routine. `--count` repeats `--prepare` N times.

- [ ] **Step 1: Update tests (failing)**

In `tests/test_main.py`, replace the prompt/category tests with:

```python
    def test_prepare_invokes_prepare(self):
        with patch("sys.argv", ["main.py", "--prepare"]):
            main()
        self.pipeline_instance.prepare.assert_called_once_with(script_id=None)

    def test_prepare_with_script_id(self):
        with patch("sys.argv", ["main.py", "--prepare", "--script", "belly-rub-betrayal"]):
            main()
        self.pipeline_instance.prepare.assert_called_once_with(
            script_id="belly-rub-betrayal",
        )

    def test_publish_invokes_publish_inbox(self):
        with patch("sys.argv", ["main.py", "--publish"]):
            main()
        self.pipeline_instance.publish_inbox.assert_called_once()

    def test_clip_invokes_clip_footage(self, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        with patch("sys.argv", ["main.py", "--clip", str(video)]):
            main()
        self.pipeline_instance.clip_footage.assert_called_once()

    def test_clip_missing_file_exits(self):
        with patch("sys.argv", ["main.py", "--clip", "/nope/missing.mp4"]):
            with pytest.raises(SystemExit):
                main()

    def test_default_runs_daily_routine(self):
        with patch("sys.argv", ["main.py"]):
            main()
        self.pipeline_instance.run.assert_called_once_with()

    def test_prompt_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--prompt", "A sleepy cat"]):
            with pytest.raises(SystemExit):
                main()

    def test_category_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--category", "funny"]):
            with pytest.raises(SystemExit):
                main()

    def test_script_without_prepare_rejected(self):
        with patch("sys.argv", ["main.py", "--script", "some-id"]):
            with pytest.raises(SystemExit):
                main()
```

Also update the mock_pipeline fixture so `run`, `prepare`, `publish_inbox`, `clip_footage` all return sensible dicts:

```python
    @pytest.fixture(autouse=True)
    def mock_pipeline(self):
        pipe_instance = MagicMock()
        pipe_instance.run.return_value = {"published": [], "prepared": None, "status": "ok"}
        pipe_instance.prepare.return_value = {"script_id": "x", "status": "prepared"}
        pipe_instance.publish_inbox.return_value = []
        pipe_instance.clip_footage.return_value = {"project_id": "P1", "clips": [], "status": "clipped"}
        with patch("pipeline.runner.Pipeline", return_value=pipe_instance) as cls:
            self.pipeline_cls = cls
            self.pipeline_instance = pipe_instance
            yield
```

Keep/adapt the dry-run settings tests (they exercise `--dry-run` + default routine).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: FAIL — unknown `--prepare`/`--publish`/`--clip` arguments

- [ ] **Step 3: Update main.py**

Replace `--prompt`/`--category` argparse lines with:

```python
    parser.add_argument("--prepare",  action="store_true",      help="Stage the next script + photos for Agent Opus rendering")
    parser.add_argument("--publish",  action="store_true",      help="Publish rendered videos from handoff/inbox to TikTok")
    parser.add_argument("--clip",     type=str,  default=None,  help="Upload a local video and let OpusClip cut it into clips")
    parser.add_argument("--script",   type=str,  default=None,  help="Specific script id (with --prepare)")
    # Retired flags — old cron entries fail loudly with guidance:
    parser.add_argument("--prompt",   type=str,  default=None,  help=argparse.SUPPRESS)
    parser.add_argument("--category", type=str,  default=None,  help=argparse.SUPPRESS)
```

Replace the prompt/category handling and run-loop block in `main()` with:

```python
    if args.prompt or args.category:
        logger.error(
            "--prompt/--category were replaced by the script pipeline. "
            "Use --prepare [--script <id>], --publish, or --clip <video>."
        )
        sys.exit(1)

    if args.script and not args.prepare:
        logger.error("--script requires --prepare")
        sys.exit(1)

    from pipeline.runner import Pipeline

    if args.clip:
        from pathlib import Path
        video = Path(args.clip)
        if not video.is_file():
            logger.error("Video not found: {}", video)
            sys.exit(1)
        try:
            result = Pipeline().clip_footage(video)
            logger.info("Clipping done: {} clips (project {})",
                        len(result["clips"]), result["project_id"])
        except Exception as e:
            logger.error("Clipping failed: {}", e)
            sys.exit(1)
        return

    if args.publish:
        try:
            results = Pipeline().publish_inbox()
            logger.info("Published {} video(s)", len(results))
        except Exception as e:
            logger.error("Publish failed: {}", e)
            sys.exit(1)
        return

    if args.prepare:
        for i in range(args.count):
            try:
                result = Pipeline().prepare(script_id=args.script)
                logger.info("Prepared {}/{}: '{}' — {}",
                            i + 1, args.count,
                            result["script_id"], result["handoff_dir"])
            except Exception as e:
                logger.error("Prepare {}/{} failed: {}", i + 1, args.count, e)
                sys.exit(1)
        return

    # Default: daily routine (used by --schedule too)
    try:
        result = Pipeline().run()
        logger.info("Daily routine done: {} published, prepared={}",
                    len(result["published"]),
                    (result["prepared"] or {}).get("script_id"))
    except Exception as e:
        logger.error("Daily routine failed: {}", e)
        sys.exit(1)
```

Update the module docstring usage block to document the new flags.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: ALL PASS

- [ ] **Step 5: Full suite + coverage**

Run: `.venv/bin/python -m pytest -m "not smoke" --cov=clippers --cov=pipeline --cov=prompts --cov=characters --cov=utils --cov-report=term-missing`
Expected: ALL PASS; new modules ≥80%. (`.venv/bin/pip install pytest-cov` if missing.)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: two-lane CLI — --prepare/--publish/--clip replace --prompt/--category"
git push
```
