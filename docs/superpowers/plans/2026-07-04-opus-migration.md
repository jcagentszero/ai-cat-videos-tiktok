# Agent Opus Migration + Nika Script System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap the video backend from Google Veo to the Agent Opus API (Veo kept as degraded fallback), driven by full multi-shot scripts starring "Nika" (Exotic Shorthair, Grumpy Cat 2.0 persona) with reference photos for character consistency.

**Architecture:** The pipeline's generator is duck-typed (`.generate(...) -> Path`), so we introduce a `VideoGenerator` Protocol + factory selected by `VIDEO_BACKEND`. One-line prompt pools are replaced by a pool of Markdown scripts with YAML frontmatter, consumed via atomic file moves. All Agent Opus API knowledge is confined to `generators/opus_client.py` — its endpoint path constants are the only code the Phase 0 spike adjusts.

**Tech Stack:** Python 3.14, requests, tenacity, pyyaml (new), pytest with unittest.mock.

## Global Constraints

- TDD mandatory: every task is RED → GREEN → commit. 80%+ coverage on new modules.
- Immutable patterns: frozen dataclasses, no in-place mutation of shared state.
- Files 200–400 lines typical; functions <50 lines; explicit error handling; validate at boundaries.
- No hardcoded secrets. All config via `config/settings.py` + `.env` (never `os.environ` elsewhere).
- Tests never hit real APIs — mock at the HTTP/client boundary (convention: `tests/test_tiktok.py`).
- Conventional commits (`feat:`, `fix:`, `test:`, `refactor:`). Push after every commit.
- `generators/veo.py` is NOT modified in any task.
- Run tests with: `.venv/bin/python -m pytest` (repo venv, Python 3.14).
- Endpoint paths in `generators/opus_client.py` marked "Provisional — Phase 0 spike" are expected to change once `specs/opus-api-notes.md` exists; tests reference the constants, not literal paths, so spike edits don't break them.

---

### Task 1: Settings — backend flag, Opus vars, reference photos dir

**Files:**
- Modify: `config/settings.py`
- Modify: `.env.example` (append new vars)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (foundation task)
- Produces: `settings.VIDEO_BACKEND: str` ("veo"|"opus", default "veo"), `settings.OPUS_API_KEY: str`, `settings.OPUS_API_BASE: str`, `settings.OPUS_POLL_TIMEOUT: int`, `settings.OPUS_POLL_INTERVAL: int`, `settings.OPUS_REFERENCE_ASSET_IDS: tuple[str, ...]`, `settings.REFERENCE_PHOTOS_DIR: Path`, `validate_config(*, dry_run=False)` branching by backend.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py` (note: `_patch_vars` already exists at the top of the file — extend its defaults with `VIDEO_BACKEND="veo"` and `OPUS_API_KEY=""` is NOT needed; patch per-test instead):

```python
class TestValidateConfigBackends:
    def test_opus_backend_requires_opus_key(self):
        with _patch_vars(VIDEO_BACKEND="opus", OPUS_API_KEY=""):
            with pytest.raises(ValueError, match="OPUS_API_KEY"):
                validate_config()

    def test_opus_backend_with_key_passes(self):
        with _patch_vars(VIDEO_BACKEND="opus", OPUS_API_KEY="ok_test"):
            validate_config()

    def test_opus_backend_skips_gcp_vars(self):
        with _patch_vars(
            VIDEO_BACKEND="opus", OPUS_API_KEY="ok_test",
            GCP_PROJECT_ID="", GCP_CREDENTIALS="",
        ):
            validate_config()

    def test_veo_backend_still_requires_gcp(self):
        with _patch_vars(VIDEO_BACKEND="veo", GCP_PROJECT_ID=""):
            with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT_ID"):
                validate_config()

    def test_invalid_backend_raises(self):
        with _patch_vars(VIDEO_BACKEND="banana"):
            with pytest.raises(ValueError, match="VIDEO_BACKEND"):
                validate_config()

    def test_opus_dry_run_skips_tiktok(self):
        with _patch_vars(
            VIDEO_BACKEND="opus", OPUS_API_KEY="ok_test",
            TIKTOK_CLIENT_KEY="", TIKTOK_CLIENT_SECRET="",
        ):
            validate_config(dry_run=True)


class TestNewSettings:
    def test_video_backend_defaults_to_veo(self):
        assert settings.VIDEO_BACKEND in ("veo", "opus")

    def test_reference_photos_dir_under_root(self):
        assert settings.ROOT_DIR in settings.REFERENCE_PHOTOS_DIR.parents

    def test_opus_reference_asset_ids_is_tuple(self):
        assert isinstance(settings.OPUS_REFERENCE_ASSET_IDS, tuple)
```

Also update the existing `_patch_vars` helper so the new attribute exists in defaults:

```python
def _patch_vars(**overrides):
    defaults = {
        "GCP_PROJECT_ID": "test-project",
        "GCP_CREDENTIALS": "/path/to/creds.json",
        "TIKTOK_CLIENT_KEY": "key123",
        "TIKTOK_CLIENT_SECRET": "secret456",
        "VIDEO_BACKEND": "veo",
        "OPUS_API_KEY": "",
    }
    defaults.update(overrides)
    return patch.multiple(settings, **defaults)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: ... does not have the attribute 'VIDEO_BACKEND'`

- [ ] **Step 3: Implement settings changes**

In `config/settings.py`, insert after the `# ── Google Cloud / Veo 3` block (line 25):

```python
# ── Video backend ────────────────────────────────────────────────────────────
VIDEO_BACKEND = os.getenv("VIDEO_BACKEND", "veo").lower()

# ── Agent Opus ────────────────────────────────────────────────────────────────
OPUS_API_KEY       = os.getenv("OPUS_API_KEY", "")
OPUS_API_BASE      = os.getenv("OPUS_API_BASE", "https://api.opus.pro/api")
OPUS_POLL_TIMEOUT  = int(os.getenv("OPUS_POLL_TIMEOUT", "1800"))
OPUS_POLL_INTERVAL = int(os.getenv("OPUS_POLL_INTERVAL", "15"))
# Escape hatch: pre-registered dashboard asset IDs, comma-separated.
# When set, reference photo upload is skipped entirely.
OPUS_REFERENCE_ASSET_IDS = tuple(
    x.strip() for x in os.getenv("OPUS_REFERENCE_ASSET_IDS", "").split(",") if x.strip()
)

# ── Reference photos (Nika) ──────────────────────────────────────────────────
REFERENCE_PHOTOS_DIR = ROOT_DIR / os.getenv("REFERENCE_PHOTOS_DIR", "reference/nika")
```

Replace the validation section (lines 69–96) with:

```python
_REQUIRED = {
    "GOOGLE_CLOUD_PROJECT_ID": "GCP_PROJECT_ID",
    "GOOGLE_APPLICATION_CREDENTIALS": "GCP_CREDENTIALS",
    "TIKTOK_CLIENT_KEY": "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET": "TIKTOK_CLIENT_SECRET",
    "OPUS_API_KEY": "OPUS_API_KEY",
}

_GCP_VARS = {"GOOGLE_CLOUD_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"}
_TIKTOK_VARS = {"TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"}
_OPUS_VARS = {"OPUS_API_KEY"}


def validate_config(*, dry_run=False):
    """Raise ValueError if any required setting is missing.

    Backend vars depend on VIDEO_BACKEND (opus → OPUS_API_KEY, veo → GCP vars).
    In dry-run mode, TikTok vars are skipped.
    """
    mod = sys.modules[__name__]

    if mod.VIDEO_BACKEND not in ("veo", "opus"):
        raise ValueError(
            f"Invalid VIDEO_BACKEND {mod.VIDEO_BACKEND!r}: must be 'veo' or 'opus'."
        )

    backend_vars = _OPUS_VARS if mod.VIDEO_BACKEND == "opus" else _GCP_VARS
    required = backend_vars if dry_run else backend_vars | _TIKTOK_VARS
    missing = [
        env_name for env_name in sorted(required)
        if not getattr(mod, _REQUIRED[env_name], "")
    ]

    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in your .env file or shell environment."
        )
```

Append to `.env.example`:

```bash
# ── Video backend: "veo" (default) or "opus" ─────────────
VIDEO_BACKEND=veo

# ── Agent Opus (required when VIDEO_BACKEND=opus) ────────
OPUS_API_KEY=
OPUS_API_BASE=https://api.opus.pro/api
OPUS_POLL_TIMEOUT=1800
OPUS_POLL_INTERVAL=15
# Optional: comma-separated pre-registered asset IDs (skips photo upload)
OPUS_REFERENCE_ASSET_IDS=

# ── Reference photos of Nika ─────────────────────────────
REFERENCE_PHOTOS_DIR=reference/nika
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: ALL PASS (including pre-existing tests — the veo default keeps old behavior)

- [ ] **Step 5: Commit**

```bash
git add config/settings.py .env.example tests/test_config.py
git commit -m "feat: add VIDEO_BACKEND flag, Agent Opus settings, reference photos dir"
git push
```

---

### Task 2: Character bible + persona module

**Files:**
- Create: `characters/__init__.py` (empty)
- Create: `characters/persona.py`
- Create: `characters/nika.md`
- Test: `tests/test_persona.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Persona` frozen dataclass (`name: str, breed: str, description: str, hashtags: tuple[str, ...], voice_rules: tuple[str, ...]`), singleton `NIKA: Persona`, `inject_persona(text: str, persona: Persona = NIKA) -> str` (replaces every `[CAT]`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_persona.py`:

```python
from pathlib import Path

from characters.persona import NIKA, Persona, inject_persona

NIKA_MD = Path(__file__).parent.parent / "characters" / "nika.md"


class TestPersona:
    def test_nika_is_frozen(self):
        import dataclasses
        assert dataclasses.is_dataclass(NIKA)
        assert NIKA.__dataclass_params__.frozen

    def test_nika_fields(self):
        assert NIKA.name == "Nika"
        assert NIKA.breed == "Exotic Shorthair"
        assert "[CAT]" not in NIKA.description
        assert len(NIKA.hashtags) >= 3
        assert len(NIKA.voice_rules) >= 1


class TestInjectPersona:
    def test_replaces_single_placeholder(self):
        assert inject_persona("[CAT] sits.") == f"{NIKA.description} sits."

    def test_replaces_every_placeholder(self):
        result = inject_persona("[CAT] and [CAT]")
        assert "[CAT]" not in result
        assert result.count(NIKA.description) == 2

    def test_no_placeholder_is_noop(self):
        assert inject_persona("a cat sits") == "a cat sits"

    def test_custom_persona(self):
        p = Persona(
            name="X", breed="Tabby", description="X the tabby",
            hashtags=("x",), voice_rules=("dry",),
        )
        assert inject_persona("[CAT]!", p) == "X the tabby!"


class TestCharacterBibleSync:
    def test_description_appears_verbatim_in_bible(self):
        assert NIKA.description in NIKA_MD.read_text()

    def test_every_hashtag_in_bible(self):
        text = NIKA_MD.read_text()
        for tag in NIKA.hashtags:
            assert tag in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_persona.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'characters'`

- [ ] **Step 3: Implement persona module and bible**

Create empty `characters/__init__.py`.

Create `characters/persona.py`:

```python
"""
characters/persona.py
─────────────────────
Nika's character definition, injected into every script at render time.
The prose description in characters/nika.md must contain NIKA.description
verbatim (enforced by tests/test_persona.py).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    breed: str
    description: str            # replaces the [CAT] placeholder in scripts
    hashtags: tuple[str, ...]   # brand hashtags appended to every post
    voice_rules: tuple[str, ...]


NIKA = Persona(
    name="Nika",
    breed="Exotic Shorthair",
    description=(
        "Nika, an Exotic Shorthair cat with a flat, permanently unimpressed "
        "face, huge round eyes, a plush dense coat, and a compact round body"
    ),
    hashtags=("nikathecat", "grumpybutsweet", "exoticshorthair", "grumpycat2"),
    voice_rules=(
        "Text overlays are deadpan and dry; no exclamation points",
        "Her face says done-with-everything; her actions are secretly sweet and social",
        "The joke is the gap between her grumpy face and her golden heart — never mock the cat",
    ),
)


def inject_persona(text: str, persona: Persona = NIKA) -> str:
    """Replace every [CAT] placeholder with the persona's description."""
    return text.replace("[CAT]", persona.description)
```

Create `characters/nika.md`:

```markdown
# Nika — Character Bible ("Grumpy Cat 2.0")

## Who she is

Nika is an Exotic Shorthair. Her face is permanently, magnificently unimpressed
— and there is not a mean bone in her body. She is extremely social, loves all
people, and is always hanging out exactly where the action is. The brand is the
gap: the grumpiest face on the internet attached to the sweetest cat in the room.

## Physical description (prompt injection string)

Every script references her as `[CAT]`. At render time that placeholder is
replaced with this exact sentence fragment (kept in sync with
`characters/persona.py` — do not edit one without the other):

Nika, an Exotic Shorthair cat with a flat, permanently unimpressed face, huge round eyes, a plush dense coat, and a compact round body

Refine with her actual coloring once reference photos land in `reference/nika/`
(update persona.py and this file together; the sync test will catch drift).

## Personality

- Looks: perpetual disapproval, mild disgust, silent judgment.
- Reality: sweetest, most social cat alive. Greets strangers. Supervises chores.
- Comedy engine: sincere setup → her unimpressed face → secretly kind payoff.

## Voice rules (overlays + captions)

- Deadpan and dry; no exclamation points.
- Her face says done-with-everything; her actions are secretly sweet and social.
- The joke is the gap between her grumpy face and her golden heart — never mock the cat.

## Brand hashtags

nikathecat, grumpybutsweet, exoticshorthair, grumpycat2

## Recurring bits

- "The Audit": Nika staring at ordinary household activities with visible disappointment.
- "Reluctant Cuddler": acts inconvenienced, moves closer anyway.
- "Front Desk": stationed wherever guests arrive, greeting them grumpily.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_persona.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add characters/ tests/test_persona.py
git commit -m "feat: add Nika persona module and character bible"
git push
```

---

### Task 3: Reference photos loader

**Files:**
- Create: `reference/nika/README.md`, `reference/nika/.gitkeep`
- Create: `utils/reference_photos.py`
- Modify: `.gitignore` (exclude actual photos, keep README)
- Test: `tests/test_reference_photos.py`

**Interfaces:**
- Consumes: `settings.REFERENCE_PHOTOS_DIR` (Task 1)
- Produces: `load_reference_photos(directory: Path | None = None) -> tuple[Path, ...]`, `ReferencePhotoError(Exception)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reference_photos.py`:

```python
import pytest

from utils.reference_photos import ReferencePhotoError, load_reference_photos


def _make_photo(directory, name, size=1024):
    p = directory / name
    p.write_bytes(b"\x89" * size)
    return p


class TestLoadReferencePhotos:
    def test_returns_sorted_tuple(self, tmp_path):
        _make_photo(tmp_path, "b.jpg")
        _make_photo(tmp_path, "a.png")
        photos = load_reference_photos(tmp_path)
        assert isinstance(photos, tuple)
        assert [p.name for p in photos] == ["a.png", "b.jpg"]

    def test_filters_non_image_files(self, tmp_path):
        _make_photo(tmp_path, "cat.jpeg")
        (tmp_path / "notes.txt").write_text("not a photo")
        (tmp_path / "README.md").write_text("readme")
        photos = load_reference_photos(tmp_path)
        assert [p.name for p in photos] == ["cat.jpeg"]

    def test_uppercase_extensions_accepted(self, tmp_path):
        _make_photo(tmp_path, "CAT.JPG")
        assert len(load_reference_photos(tmp_path)) == 1

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(ReferencePhotoError, match="not found"):
            load_reference_photos(tmp_path / "nope")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ReferencePhotoError, match="No reference photos"):
            load_reference_photos(tmp_path)

    def test_oversized_photo_raises(self, tmp_path):
        _make_photo(tmp_path, "huge.jpg", size=10 * 1024 * 1024 + 1)
        with pytest.raises(ReferencePhotoError, match="huge.jpg"):
            load_reference_photos(tmp_path)

    def test_defaults_to_settings_dir(self, tmp_path, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "REFERENCE_PHOTOS_DIR", tmp_path)
        _make_photo(tmp_path, "nika.jpg")
        assert len(load_reference_photos()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reference_photos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.reference_photos'`

- [ ] **Step 3: Implement**

Create `utils/reference_photos.py`:

```python
"""
utils/reference_photos.py
─────────────────────────
Loads Nika's reference photos for character-consistent video generation.
"""

from pathlib import Path

from config import settings

_ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per photo


class ReferencePhotoError(Exception):
    """Raised when the reference photo directory is missing, empty, or invalid."""


def load_reference_photos(directory: Path | None = None) -> tuple[Path, ...]:
    """Return a deterministic, validated tuple of reference photo paths.

    Raises:
        ReferencePhotoError: directory missing, no usable photos, or a photo >10MB.
    """
    directory = Path(directory) if directory is not None else settings.REFERENCE_PHOTOS_DIR

    if not directory.is_dir():
        raise ReferencePhotoError(f"Reference photo directory not found: {directory}")

    photos = tuple(sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _ALLOWED_SUFFIXES
    ))
    if not photos:
        raise ReferencePhotoError(
            f"No reference photos (.jpg/.jpeg/.png) found in {directory}"
        )

    oversized = [p.name for p in photos if p.stat().st_size > _MAX_BYTES]
    if oversized:
        raise ReferencePhotoError(
            f"Reference photos exceed 10MB limit: {', '.join(oversized)}"
        )
    return photos
```

Create `reference/nika/README.md`:

```markdown
# Nika reference photos

Drop 3–10 clear photos of Nika here (`.jpg`, `.jpeg`, or `.png`, max 10MB each).
They are uploaded to Agent Opus for character consistency in generated videos.

Good set: face close-up (front), full body sitting, full body standing,
her signature unimpressed stare, one in typical home lighting.

Actual photos are gitignored — only this README is committed.
```

Create empty `reference/nika/.gitkeep`. Append to `.gitignore`:

```
# Real cat photos stay out of the repo
reference/nika/*
!reference/nika/README.md
!reference/nika/.gitkeep
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reference_photos.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add utils/reference_photos.py reference/ .gitignore tests/test_reference_photos.py
git commit -m "feat: add reference photo loader and gitignored reference/nika folder"
git push
```

---

### Task 4: Script model + markdown parser

**Files:**
- Create: `prompts/script.py`
- Create: `tests/conftest.py` (shared script fixture)
- Modify: `requirements.txt` (add pyyaml)
- Test: `tests/test_script.py`

**Interfaces:**
- Consumes: `Persona`, `NIKA`, `inject_persona` (Task 2)
- Produces:
  - `Shot` frozen dataclass: `index: int, label: str, start_s: float, end_s: float, description: str, audio: str, text_overlay: str`
  - `Script` frozen dataclass: `id: str, title: str, logline: str, caption: str, hook: str, hashtags: tuple[str, ...], duration_seconds: int, shots: tuple[Shot, ...], body: str, path: Path`, method `render(persona: Persona = NIKA) -> str`
  - `parse_script(path: Path) -> Script` (raises `ValueError` naming the file on bad input)

- [ ] **Step 1: Install pyyaml and pin it**

Run: `.venv/bin/pip install pyyaml`
Append to `requirements.txt` under `# Utilities`:

```
pyyaml>=6.0        # script frontmatter parsing
```

- [ ] **Step 2: Write the shared fixture**

Create `tests/conftest.py`:

```python
import pytest

SAMPLE_SCRIPT_MD = """\
---
id: belly-rub-betrayal
title: The Belly Rub Betrayal
logline: A cat lures its owner into the oldest trap in feline history.
caption: The belly was never an offer. It was a test.
hook: She's offering her belly. This is a gift.
hashtags:
  - bellyrub
  - cattrap
duration_seconds: 30
created: 2026-07-04
---

## Shot 1 — The Invitation (0:00–0:06)

> [CAT] lying on its back on a sunlit living room rug, belly fully exposed,
> slow blinking at the camera, warm golden-hour light, static low-angle shot.

- **Audio:** Soft, dreamy piano. Gentle purring.
- **Text overlay:** "She's offering her belly. This is a gift."

## Shot 2 — The Trap Springs (0:06–0:12)

> Slow-motion shot of [CAT] snapping shut around a human hand like a bear trap,
> bunny-kicking with rear legs, 120fps slow motion.

- **Audio:** Horror-movie string stab.
- **Text overlay:** "THE MURDER REFLEX HAS BEEN ACTIVATED"

## Production notes

- Generate shots as separate clips and stitch.
"""


@pytest.fixture
def script_file(tmp_path):
    """A valid sample script written to a temp file."""
    path = tmp_path / "belly-rub-betrayal.md"
    path.write_text(SAMPLE_SCRIPT_MD)
    return path
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_script.py`:

```python
import pytest

from characters.persona import NIKA, Persona
from prompts.script import Script, Shot, parse_script
from tests.conftest import SAMPLE_SCRIPT_MD


class TestParseScript:
    def test_parses_frontmatter(self, script_file):
        s = parse_script(script_file)
        assert s.id == "belly-rub-betrayal"
        assert s.title == "The Belly Rub Betrayal"
        assert s.caption == "The belly was never an offer. It was a test."
        assert s.hook == "She's offering her belly. This is a gift."
        assert s.hashtags == ("bellyrub", "cattrap")
        assert s.duration_seconds == 30
        assert s.path == script_file

    def test_parses_shots(self, script_file):
        s = parse_script(script_file)
        assert len(s.shots) == 2
        first = s.shots[0]
        assert first.index == 1
        assert first.label == "The Invitation"
        assert first.start_s == 0.0
        assert first.end_s == 6.0
        assert first.description.startswith("[CAT] lying on its back")
        assert first.audio == "Soft, dreamy piano. Gentle purring."
        assert "gift" in first.text_overlay

    def test_second_shot_times(self, script_file):
        s = parse_script(script_file)
        assert s.shots[1].start_s == 6.0
        assert s.shots[1].end_s == 12.0

    def test_production_notes_not_a_shot(self, script_file):
        s = parse_script(script_file)
        assert all("Production" not in shot.label for shot in s.shots)

    def test_missing_frontmatter_key_raises_with_filename(self, tmp_path):
        bad = tmp_path / "bad.md"
        bad.write_text(SAMPLE_SCRIPT_MD.replace("caption: The belly was never an offer. It was a test.\n", ""))
        with pytest.raises(ValueError, match=r"bad\.md.*caption"):
            parse_script(bad)

    def test_no_frontmatter_raises(self, tmp_path):
        bad = tmp_path / "plain.md"
        bad.write_text("# just a heading\n\nsome text")
        with pytest.raises(ValueError, match=r"plain\.md"):
            parse_script(bad)

    def test_no_shots_raises(self, tmp_path):
        header_only = SAMPLE_SCRIPT_MD.split("## Shot 1")[0]
        bad = tmp_path / "noshots.md"
        bad.write_text(header_only)
        with pytest.raises(ValueError, match=r"noshots\.md.*[Ss]hot"):
            parse_script(bad)

    def test_script_is_frozen(self, script_file):
        s = parse_script(script_file)
        with pytest.raises(Exception):
            s.title = "changed"


class TestRender:
    def test_render_injects_persona(self, script_file):
        rendered = parse_script(script_file).render()
        assert "[CAT]" not in rendered
        assert NIKA.description in rendered

    def test_render_includes_title_logline_and_body(self, script_file):
        rendered = parse_script(script_file).render()
        assert "The Belly Rub Betrayal" in rendered
        assert "oldest trap in feline history" in rendered
        assert "Shot 2" in rendered

    def test_render_with_custom_persona(self, script_file):
        p = Persona(name="X", breed="T", description="X the test cat",
                    hashtags=("x",), voice_rules=())
        rendered = parse_script(script_file).render(p)
        assert "X the test cat" in rendered
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_script.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompts.script'`

- [ ] **Step 5: Implement the parser**

Create `prompts/script.py`:

```python
"""
prompts/script.py
─────────────────
Script domain model: a full multi-shot video script stored as Markdown
with YAML frontmatter. Scripts reference the cat as [CAT]; render()
injects the persona description.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from characters.persona import NIKA, Persona, inject_persona

_REQUIRED_KEYS = (
    "id", "title", "logline", "caption", "hook", "hashtags", "duration_seconds",
)

_SHOT_HEADER = re.compile(
    r"^## Shot (?P<index>\d+) — (?P<label>.+?) "
    r"\((?P<sm>\d+):(?P<ss>\d+)[–-](?P<em>\d+):(?P<es>\d+)\)\s*$",
    re.MULTILINE,
)
_ANY_HEADING = re.compile(r"^## ", re.MULTILINE)
_AUDIO = re.compile(r"^- \*\*Audio:\*\* (?P<text>.+)$", re.MULTILINE)
_OVERLAY = re.compile(r"^- \*\*Text overlay:\*\* (?P<text>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Shot:
    index: int
    label: str
    start_s: float
    end_s: float
    description: str
    audio: str
    text_overlay: str


@dataclass(frozen=True)
class Script:
    id: str
    title: str
    logline: str
    caption: str
    hook: str
    hashtags: tuple[str, ...]
    duration_seconds: int
    shots: tuple[Shot, ...]
    body: str
    path: Path

    def render(self, persona: Persona = NIKA) -> str:
        """Full script text for the video generator, [CAT] injected."""
        text = f"# {self.title}\n\n**Logline:** {self.logline}\n\n{self.body}"
        return inject_persona(text, persona)


def parse_script(path: Path) -> Script:
    """Parse a script markdown file. Strict on frontmatter, lenient on shots."""
    raw = path.read_text()
    if not raw.startswith("---"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")

    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path.name}: unterminated YAML frontmatter")

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"{path.name}: invalid frontmatter YAML: {e}") from e

    missing = [k for k in _REQUIRED_KEYS if k not in meta]
    if missing:
        raise ValueError(
            f"{path.name}: missing frontmatter keys: {', '.join(missing)}"
        )

    body = parts[2].strip()
    shots = _parse_shots(body)
    if not shots:
        raise ValueError(
            f"{path.name}: no parseable '## Shot N — Label (m:ss–m:ss)' sections"
        )

    return Script(
        id=str(meta["id"]),
        title=str(meta["title"]),
        logline=str(meta["logline"]),
        caption=str(meta["caption"]),
        hook=str(meta["hook"]),
        hashtags=tuple(str(h) for h in meta["hashtags"]),
        duration_seconds=int(meta["duration_seconds"]),
        shots=shots,
        body=body,
        path=path,
    )


def _parse_shots(body: str) -> tuple[Shot, ...]:
    shots = []
    for m in _SHOT_HEADER.finditer(body):
        next_heading = _ANY_HEADING.search(body, m.end())
        section = body[m.end(): next_heading.start() if next_heading else len(body)]

        description = " ".join(
            line[2:].strip()
            for line in section.splitlines()
            if line.startswith("> ")
        ).strip()
        audio = _AUDIO.search(section)
        overlay = _OVERLAY.search(section)

        shots.append(Shot(
            index=int(m["index"]),
            label=m["label"].strip(),
            start_s=float(int(m["sm"]) * 60 + int(m["ss"])),
            end_s=float(int(m["em"]) * 60 + int(m["es"])),
            description=description,
            audio=audio["text"].strip() if audio else "",
            text_overlay=overlay["text"].strip().strip('"') if overlay else "",
        ))
    return tuple(shots)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_script.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add prompts/script.py tests/test_script.py tests/conftest.py requirements.txt
git commit -m "feat: add Script domain model with markdown frontmatter parser"
git push
```

---

### Task 5: ScriptManager — consume-on-use script pool

**Files:**
- Create: `prompts/script_manager.py`
- Create: `prompts/scripts/available/.gitkeep`, `prompts/scripts/used/.gitkeep`
- Modify: `prompts/prompt_manager.py` (docstring deprecation note only)
- Test: `tests/test_script_manager.py`

**Interfaces:**
- Consumes: `parse_script`, `Script` (Task 4)
- Produces: `ScriptManager(available_dir=..., used_dir=..., used_log=...)` with `consume_script(script_id: str | None = None) -> Script`, `peek_script(script_id: str | None = None) -> Script`, `get_available_count() -> int`. Raises `RuntimeError` on empty pool / unknown id.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_script_manager.py`:

```python
import json

import pytest

from prompts.script_manager import ScriptManager
from tests.conftest import SAMPLE_SCRIPT_MD


@pytest.fixture
def pool(tmp_path):
    available = tmp_path / "available"
    used = tmp_path / "used"
    available.mkdir()
    used.mkdir()
    for slug in ("script-a", "script-b"):
        content = SAMPLE_SCRIPT_MD.replace("id: belly-rub-betrayal", f"id: {slug}")
        (available / f"{slug}.md").write_text(content)
    log = tmp_path / "used_log.json"
    return ScriptManager(available_dir=available, used_dir=used, used_log=log)


class TestConsume:
    def test_consume_returns_script_and_moves_file(self, pool, tmp_path):
        script = pool.consume_script()
        assert script.id in ("script-a", "script-b")
        assert not (tmp_path / "available" / f"{script.id}.md").exists()
        assert (tmp_path / "used" / f"{script.id}.md").exists()
        assert script.path == tmp_path / "used" / f"{script.id}.md"

    def test_consume_logs_timestamp(self, pool, tmp_path):
        script = pool.consume_script()
        entries = json.loads((tmp_path / "used_log.json").read_text())
        assert entries[0]["id"] == script.id
        assert "consumed_at" in entries[0]

    def test_consume_by_id(self, pool):
        assert pool.consume_script("script-b").id == "script-b"

    def test_consume_unknown_id_raises(self, pool):
        with pytest.raises(RuntimeError, match="script-zzz"):
            pool.consume_script("script-zzz")

    def test_empty_pool_raises(self, pool):
        pool.consume_script()
        pool.consume_script()
        with pytest.raises(RuntimeError, match="empty"):
            pool.consume_script()


class TestPeek:
    def test_peek_does_not_move(self, pool):
        pool.peek_script()
        assert pool.get_available_count() == 2

    def test_peek_by_id(self, pool):
        assert pool.peek_script("script-a").id == "script-a"


class TestCount:
    def test_count_decrements_on_consume(self, pool):
        assert pool.get_available_count() == 2
        pool.consume_script()
        assert pool.get_available_count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_script_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompts.script_manager'`

- [ ] **Step 3: Implement**

Create `prompts/script_manager.py`:

```python
"""
prompts/script_manager.py
─────────────────────────
Thread-safe script pool with consume-on-use semantics.

Scripts are markdown files in prompts/scripts/available/. Consuming a
script atomically moves its file to prompts/scripts/used/ and appends a
timestamped entry to used_log.json — a script is never posted twice.
"""

import json
import random
import shutil
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from prompts.script import Script, parse_script
from utils.logger import logger

_SCRIPTS_DIR = Path(__file__).parent / "scripts"
_AVAILABLE_DIR = _SCRIPTS_DIR / "available"
_USED_DIR = _SCRIPTS_DIR / "used"
_USED_LOG = _SCRIPTS_DIR / "used_log.json"


class ScriptManager:
    """Manages the pool of full video scripts (replaces PromptManager)."""

    def __init__(
        self,
        available_dir: Path | str = _AVAILABLE_DIR,
        used_dir: Path | str = _USED_DIR,
        used_log: Path | str = _USED_LOG,
    ):
        self._available_dir = Path(available_dir)
        self._used_dir = Path(used_dir)
        self._used_log = Path(used_log)
        self._lock = threading.Lock()

    def consume_script(self, script_id: str | None = None) -> Script:
        """Pick a script, move it to used/, log it. Raises RuntimeError if empty."""
        with self._lock:
            path = self._pick(script_id)
            script = parse_script(path)

            self._used_dir.mkdir(parents=True, exist_ok=True)
            dest = self._used_dir / path.name
            shutil.move(str(path), str(dest))
            self._log_consumption(script.id)

            logger.info(
                "Consumed script '{}' ({} remaining)",
                script.id, len(self._list_available()),
            )
            return replace(script, path=dest)

    def peek_script(self, script_id: str | None = None) -> Script:
        """Pick a script without consuming it (dry runs)."""
        with self._lock:
            return parse_script(self._pick(script_id))

    def get_available_count(self) -> int:
        with self._lock:
            return len(self._list_available())

    def _list_available(self) -> list[Path]:
        return sorted(self._available_dir.glob("*.md"))

    def _pick(self, script_id: str | None) -> Path:
        available = self._list_available()
        if script_id is not None:
            path = self._available_dir / f"{script_id}.md"
            if path not in available:
                raise RuntimeError(
                    f"Script '{script_id}' not found in available pool"
                )
            return path
        if not available:
            raise RuntimeError("Script pool is empty")
        return random.choice(available)

    def _log_consumption(self, script_id: str) -> None:
        entries = []
        if self._used_log.exists():
            entries = json.loads(self._used_log.read_text())
        entries = [*entries, {
            "id": script_id,
            "consumed_at": datetime.now().isoformat(),
        }]
        self._used_log.write_text(json.dumps(entries, indent=2))
```

Create empty `prompts/scripts/available/.gitkeep` and `prompts/scripts/used/.gitkeep`.

In `prompts/prompt_manager.py`, add to the end of the module docstring (line 10, before the closing `"""`):

```
DEPRECATED: one-line prompts are replaced by full scripts (prompts/script_manager.py).
This module remains only for the legacy veo prompt path and is removed in Phase 6.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_script_manager.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add prompts/script_manager.py prompts/scripts/ prompts/prompt_manager.py tests/test_script_manager.py
git commit -m "feat: add ScriptManager with consume-on-use file-move semantics"
git push
```

---

### Task 6: OpusClient — thin HTTP client (spike-shaped file)

**Files:**
- Create: `generators/opus_client.py`
- Test: `tests/test_opus_client.py`

**Interfaces:**
- Consumes: `settings.OPUS_API_KEY`, `settings.OPUS_API_BASE` (Task 1)
- Produces:
  - `OpusJob` frozen dataclass: `id: str, state: str, video_url: str | None, error: str | None` (states: `PENDING|PROCESSING|COMPLETED|FAILED`)
  - `OpusClient(api_key=None, base_url=None)` with `upload_reference(photo: Path) -> str`, `submit_generation(script_text: str, reference_ids, *, duration_seconds: int, aspect_ratio: str = "9:16") -> str`, `get_job(job_id: str) -> OpusJob`, `download(url: str, dest: Path) -> Path`
  - `OpusApiError(Exception)` (attrs: `status_code`, `body`), `OpusTransientError(OpusApiError)`
  - Module constants `UPLOAD_PATH`, `GENERATE_PATH`, `JOB_PATH` — **the only spike-adjustment point**

- [ ] **Step 1: Write the failing tests**

Create `tests/test_opus_client.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generators.opus_client import (
    GENERATE_PATH,
    JOB_PATH,
    UPLOAD_PATH,
    OpusApiError,
    OpusClient,
    OpusJob,
    OpusTransientError,
)


def _make_client():
    return OpusClient(api_key="ok_test", base_url="https://api.test/api")


def _mock_response(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    return resp


class TestInit:
    def test_missing_key_raises(self):
        with patch("config.settings.OPUS_API_KEY", ""):
            with pytest.raises(ValueError, match="OPUS_API_KEY"):
                OpusClient(api_key="")

    def test_bearer_header_set(self):
        client = _make_client()
        assert client._session.headers["Authorization"] == "Bearer ok_test"

    def test_base_url_trailing_slash_stripped(self):
        client = OpusClient(api_key="k", base_url="https://api.test/api/")
        assert client.base_url == "https://api.test/api"


class TestSubmitGeneration:
    def test_posts_script_and_references(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, {"id": "job_1"})) as req:
            job_id = client.submit_generation(
                "full script text", ["asset_1"], duration_seconds=30,
            )
        assert job_id == "job_1"
        method, url = req.call_args[0]
        assert method == "POST"
        assert url == f"https://api.test/api{GENERATE_PATH}"
        payload = req.call_args[1]["json"]
        assert payload["script"] == "full script text"
        assert payload["referenceAssetIds"] == ["asset_1"]
        assert payload["durationSeconds"] == 30
        assert payload["aspectRatio"] == "9:16"

    def test_missing_job_id_raises(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, {"nope": True})):
            with pytest.raises(OpusApiError, match="job id"):
                client.submit_generation("s", [], duration_seconds=30)


class TestGetJob:
    def test_returns_opus_job(self):
        client = _make_client()
        data = {"id": "job_1", "state": "COMPLETED",
                "videoUrl": "https://cdn.test/v.mp4"}
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, data)) as req:
            job = client.get_job("job_1")
        assert job == OpusJob(id="job_1", state="COMPLETED",
                              video_url="https://cdn.test/v.mp4", error=None)
        _, url = req.call_args[0]
        assert url == f"https://api.test/api{JOB_PATH.format(job_id='job_1')}"


class TestUploadReference:
    def test_uploads_file_returns_asset_id(self, tmp_path):
        photo = tmp_path / "nika.jpg"
        photo.write_bytes(b"\xff\xd8fakejpg")
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, {"id": "asset_9"})) as req:
            asset_id = client.upload_reference(photo)
        assert asset_id == "asset_9"
        _, url = req.call_args[0]
        assert url == f"https://api.test/api{UPLOAD_PATH}"
        assert "files" in req.call_args[1]


class TestErrors:
    def test_4xx_raises_api_error(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(403, {"error": "nope"})):
            with pytest.raises(OpusApiError) as exc:
                client.get_job("j")
            assert exc.value.status_code == 403
            assert not isinstance(exc.value, OpusTransientError)

    def test_429_retries_then_succeeds(self):
        client = _make_client()
        responses = [
            _mock_response(429, {}),
            _mock_response(200, {"id": "j", "state": "PENDING"}),
        ]
        with patch.object(client._session, "request", side_effect=responses), \
             patch("time.sleep"):
            job = client.get_job("j")
        assert job.state == "PENDING"

    def test_500_exhausts_retries_and_raises(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(500, {})), \
             patch("time.sleep"):
            with pytest.raises(OpusTransientError):
                client.get_job("j")


class TestDownload:
    def test_streams_to_dest(self, tmp_path):
        client = _make_client()
        resp = _mock_response(200)
        resp.iter_content.return_value = [b"chunk1", b"chunk2"]
        dest = tmp_path / "out" / "v.mp4"
        with patch.object(client._session, "request", return_value=resp):
            result = client.download("https://cdn.test/v.mp4", dest)
        assert result == dest
        assert dest.read_bytes() == b"chunk1chunk2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_opus_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generators.opus_client'`

- [ ] **Step 3: Implement**

Create `generators/opus_client.py`:

```python
"""
generators/opus_client.py
─────────────────────────
Thin HTTP client for the Agent Opus video generation API.

ALL Agent Opus API knowledge lives here. The path constants and payload
field names below are provisional pending the Phase 0 spike — update them
per specs/opus-api-notes.md; nothing outside this file should need to change.
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

# Provisional — confirm in Phase 0 spike (specs/opus-api-notes.md)
UPLOAD_PATH = "/media/assets"
GENERATE_PATH = "/agent/videos"
JOB_PATH = "/agent/videos/{job_id}"

_REQUEST_TIMEOUT = 60  # seconds per HTTP call


class OpusApiError(Exception):
    """Non-transient Agent Opus API failure."""

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OpusTransientError(OpusApiError):
    """Retryable failure: 429 rate limit or 5xx server error."""


def _log_retry(retry_state):
    logger.warning(
        "Retrying Opus API call (attempt {}): {}",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    )


_api_retry = retry(
    retry=retry_if_exception_type((OpusTransientError, requests.ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
    sleep=lambda s: time.sleep(s),
)


@dataclass(frozen=True)
class OpusJob:
    id: str
    state: str                # PENDING | PROCESSING | COMPLETED | FAILED
    video_url: str | None
    error: str | None


class OpusClient:
    """Authenticated HTTP wrapper around the Agent Opus API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.OPUS_API_KEY
        if not self.api_key:
            raise ValueError("OPUS_API_KEY is not set")
        self.base_url = (base_url or settings.OPUS_API_BASE).rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    @_api_retry
    def _request(self, method: str, path_or_url: str, **kwargs) -> requests.Response:
        url = path_or_url if path_or_url.startswith("http") \
            else f"{self.base_url}{path_or_url}"
        resp = self._session.request(method, url, timeout=_REQUEST_TIMEOUT, **kwargs)

        if resp.status_code == 429 or resp.status_code >= 500:
            raise OpusTransientError(
                f"Opus API {resp.status_code} on {method} {url}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        if resp.status_code >= 400:
            raise OpusApiError(
                f"Opus API {resp.status_code} on {method} {url}: {resp.text[:200]}",
                status_code=resp.status_code, body=resp.text[:500],
            )
        return resp

    def upload_reference(self, photo: Path) -> str:
        """Upload a reference photo; returns its asset id."""
        with open(photo, "rb") as f:
            resp = self._request(
                "POST", UPLOAD_PATH, files={"file": (photo.name, f)},
            )
        data = resp.json()
        asset_id = data.get("id") or data.get("assetId")
        if not asset_id:
            raise OpusApiError(
                f"Upload response missing asset id for {photo.name}",
                body=str(data)[:500],
            )
        logger.info("Uploaded reference photo {} → asset {}", photo.name, asset_id)
        return str(asset_id)

    def submit_generation(
        self,
        script_text: str,
        reference_ids,
        *,
        duration_seconds: int,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Submit a script for video generation; returns the job id."""
        payload = {
            "script": script_text,
            "referenceAssetIds": list(reference_ids),
            "durationSeconds": duration_seconds,
            "aspectRatio": aspect_ratio,
        }
        resp = self._request("POST", GENERATE_PATH, json=payload)
        data = resp.json()
        job_id = data.get("id") or data.get("jobId") or data.get("projectId")
        if not job_id:
            raise OpusApiError(
                "Generation response missing job id", body=str(data)[:500],
            )
        logger.info("Opus generation submitted (job={})", job_id)
        return str(job_id)

    def get_job(self, job_id: str) -> OpusJob:
        resp = self._request("GET", JOB_PATH.format(job_id=job_id))
        data = resp.json()
        return OpusJob(
            id=str(data.get("id", job_id)),
            state=str(data.get("state", data.get("status", "PENDING"))).upper(),
            video_url=data.get("videoUrl") or data.get("video_url"),
            error=data.get("error"),
        )

    def download(self, url: str, dest: Path) -> Path:
        """Stream the finished video to dest."""
        resp = self._request("GET", url, stream=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        logger.info("Downloaded video to {} ({} bytes)", dest, dest.stat().st_size)
        return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_opus_client.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add generators/opus_client.py tests/test_opus_client.py
git commit -m "feat: add OpusClient HTTP wrapper with retry and typed errors"
git push
```

---

### Task 7: OpusGenerator — submit → poll → download

**Files:**
- Create: `generators/opus.py`
- Test: `tests/test_opus.py`

**Interfaces:**
- Consumes: `OpusClient`, `OpusJob`, `OpusApiError` (Task 6); `Script` (Task 4); `settings.OUTPUT_DIR`, `settings.OPUS_POLL_TIMEOUT`, `settings.OPUS_POLL_INTERVAL`, `settings.OPUS_REFERENCE_ASSET_IDS` (Task 1)
- Produces: `OpusGenerator(client: OpusClient | None = None)` with `generate(script: Script, reference_photos) -> Path`. Raises `TimeoutError` on poll timeout, `RuntimeError` on FAILED job.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_opus.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generators.opus import OpusGenerator
from generators.opus_client import OpusJob
from prompts.script import parse_script


def _job(state, video_url=None, error=None):
    return OpusJob(id="job_1", state=state, video_url=video_url, error=error)


@pytest.fixture
def script(script_file):
    return parse_script(script_file)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.upload_reference.side_effect = ["asset_1", "asset_2"]
    client.submit_generation.return_value = "job_1"
    client.get_job.return_value = _job("COMPLETED", video_url="https://cdn/v.mp4")
    client.download.side_effect = lambda url, dest: dest
    return client


@pytest.fixture
def photos(tmp_path):
    paths = []
    for name in ("a.jpg", "b.jpg"):
        p = tmp_path / name
        p.write_bytes(b"\xff\xd8")
        paths.append(p)
    return tuple(paths)


class TestGenerate:
    def test_happy_path(self, script, mock_client, photos):
        gen = OpusGenerator(client=mock_client)
        with patch("generators.opus.time.sleep"):
            result = gen.generate(script, photos)
        assert isinstance(result, Path)
        assert result.suffix == ".mp4"
        assert mock_client.upload_reference.call_count == 2
        submit_kwargs = mock_client.submit_generation.call_args
        assert "[CAT]" not in submit_kwargs[0][0]        # persona injected
        assert submit_kwargs[1]["duration_seconds"] == 30
        mock_client.download.assert_called_once()

    def test_reference_ids_cached_across_calls(self, script, mock_client, photos):
        gen = OpusGenerator(client=mock_client)
        with patch("generators.opus.time.sleep"):
            gen.generate(script, photos)
            gen.generate(script, photos)
        assert mock_client.upload_reference.call_count == 2  # not 4

    def test_env_asset_ids_skip_upload(self, script, mock_client, photos):
        with patch("config.settings.OPUS_REFERENCE_ASSET_IDS", ("pre_1",)):
            gen = OpusGenerator(client=mock_client)
            with patch("generators.opus.time.sleep"):
                gen.generate(script, photos)
        mock_client.upload_reference.assert_not_called()
        assert mock_client.submit_generation.call_args[0][1] == ("pre_1",)

    def test_polls_until_complete(self, script, mock_client, photos):
        mock_client.get_job.side_effect = [
            _job("PENDING"), _job("PROCESSING"),
            _job("COMPLETED", video_url="https://cdn/v.mp4"),
        ]
        gen = OpusGenerator(client=mock_client)
        with patch("generators.opus.time.sleep"):
            gen.generate(script, photos)
        assert mock_client.get_job.call_count == 3

    def test_failed_job_raises(self, script, mock_client, photos):
        mock_client.get_job.return_value = _job("FAILED", error="content policy")
        gen = OpusGenerator(client=mock_client)
        with patch("generators.opus.time.sleep"):
            with pytest.raises(RuntimeError, match="content policy"):
                gen.generate(script, photos)

    def test_timeout_raises(self, script, mock_client, photos):
        mock_client.get_job.return_value = _job("PROCESSING")
        gen = OpusGenerator(client=mock_client)
        fake_clock = iter(range(0, 100000, 600))
        with patch("generators.opus.time.sleep"), \
             patch("generators.opus.time.monotonic",
                   side_effect=lambda: next(fake_clock)):
            with pytest.raises(TimeoutError, match="timed out"):
                gen.generate(script, photos)

    def test_completed_without_url_raises(self, script, mock_client, photos):
        mock_client.get_job.return_value = _job("COMPLETED", video_url=None)
        gen = OpusGenerator(client=mock_client)
        with patch("generators.opus.time.sleep"):
            with pytest.raises(RuntimeError, match="video URL"):
                gen.generate(script, photos)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_opus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generators.opus'`

- [ ] **Step 3: Implement**

Create `generators/opus.py`:

```python
"""
generators/opus.py
──────────────────
Agent Opus video generation: submit full script + reference photos,
poll until complete, download the mp4. Mirrors generators/veo.py's
submit → poll → download structure.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Sequence

from config import settings
from generators.opus_client import OpusClient, OpusJob
from prompts.script import Script
from utils.logger import logger

_TERMINAL_STATES = ("COMPLETED", "FAILED")


class OpusGenerator:
    """Generates videos from full scripts via the Agent Opus API."""

    def __init__(self, client: OpusClient | None = None):
        self.client = client or OpusClient()
        self._reference_ids: tuple[str, ...] | None = None
        logger.info("OpusGenerator initialized (base={})", self.client.base_url)

    def generate(self, script: Script, reference_photos: Sequence[Path]) -> Path:
        """Generate a video for the script. Returns local mp4 path."""
        logger.info(
            "Starting Opus generation for script '{}' ({}s, {} shots)",
            script.id, script.duration_seconds, len(script.shots),
        )

        reference_ids = self._ensure_references(reference_photos)
        job_id = self.client.submit_generation(
            script.render(),
            reference_ids,
            duration_seconds=script.duration_seconds,
        )

        job = self._poll_job(job_id)

        if not job.video_url:
            raise RuntimeError(
                f"Opus job {job_id} completed without a video URL"
            )

        dest = settings.OUTPUT_DIR / "video_{}.mp4".format(
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        return self.client.download(job.video_url, dest)

    def _ensure_references(self, photos: Sequence[Path]) -> tuple[str, ...]:
        """Resolve reference asset ids: env override, else upload once and cache."""
        if settings.OPUS_REFERENCE_ASSET_IDS:
            return tuple(settings.OPUS_REFERENCE_ASSET_IDS)
        if self._reference_ids is None:
            self._reference_ids = tuple(
                self.client.upload_reference(p) for p in photos
            )
        return self._reference_ids

    def _poll_job(self, job_id: str) -> OpusJob:
        """Poll until terminal state. Raises TimeoutError / RuntimeError."""
        timeout = settings.OPUS_POLL_TIMEOUT
        interval = float(settings.OPUS_POLL_INTERVAL)
        max_interval = 60.0
        start = time.monotonic()

        while True:
            job = self.client.get_job(job_id)
            if job.state in _TERMINAL_STATES:
                break

            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Opus generation timed out after {timeout}s (job={job_id})"
                )
            logger.debug(
                "Polling Opus job {} (state={}, elapsed={:.0f}s)",
                job_id, job.state, elapsed,
            )
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)

        if job.state == "FAILED":
            raise RuntimeError(
                f"Opus generation failed (job={job_id}): {job.error or 'unknown error'}"
            )

        logger.info(
            "Opus job {} completed in {:.1f}s", job_id, time.monotonic() - start,
        )
        return job
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_opus.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add generators/opus.py tests/test_opus.py
git commit -m "feat: add OpusGenerator with submit-poll-download flow"
git push
```

---

### Task 8: Backend factory + VeoAdapter

**Files:**
- Create: `generators/factory.py`
- Test: `tests/test_factory.py`

**Interfaces:**
- Consumes: `OpusGenerator` (Task 7), `VeoGenerator` (existing, unmodified), `Script` (Task 4), `inject_persona` (Task 2), `settings.VIDEO_BACKEND` (Task 1)
- Produces: `VideoGenerator` Protocol (`generate(script: Script, reference_photos: Sequence[Path]) -> Path`), `create_generator(backend: str | None = None) -> VideoGenerator`, `VeoAdapter` (degraded fallback).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_factory.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from generators.factory import VeoAdapter, create_generator
from prompts.script import parse_script


class TestCreateGenerator:
    def test_opus_backend(self):
        with patch("generators.opus.OpusClient"):
            gen = create_generator("opus")
        from generators.opus import OpusGenerator
        assert isinstance(gen, OpusGenerator)

    def test_veo_backend(self):
        with patch("generators.veo.VeoGenerator") as veo_cls:
            gen = create_generator("veo")
        assert isinstance(gen, VeoAdapter)
        veo_cls.assert_called_once()

    def test_default_uses_settings(self):
        with patch("config.settings.VIDEO_BACKEND", "opus"), \
             patch("generators.opus.OpusClient"):
            from generators.opus import OpusGenerator
            assert isinstance(create_generator(), OpusGenerator)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="banana"):
            create_generator("banana")


class TestVeoAdapter:
    def test_degraded_mode_uses_shot_one(self, script_file):
        script = parse_script(script_file)
        with patch("generators.veo.VeoGenerator") as veo_cls:
            veo = MagicMock()
            veo_cls.return_value = veo
            adapter = create_generator("veo")
            adapter.generate(script, ())
        prompt = veo.generate.call_args[0][0]
        assert "lying on its back" in prompt        # shot 1 description
        assert "[CAT]" not in prompt                # persona injected
        assert veo.generate.call_args[1]["duration_seconds"] == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generators.factory'`

- [ ] **Step 3: Implement**

Create `generators/factory.py`:

```python
"""
generators/factory.py
─────────────────────
Video backend selection. The pipeline depends only on the VideoGenerator
Protocol; concrete backends are chosen by settings.VIDEO_BACKEND.
"""

from pathlib import Path
from typing import Protocol, Sequence

from config import settings
from characters.persona import inject_persona
from prompts.script import Script
from utils.logger import logger


class VideoGenerator(Protocol):
    def generate(self, script: Script, reference_photos: Sequence[Path]) -> Path: ...


def create_generator(backend: str | None = None) -> VideoGenerator:
    """Instantiate the configured video backend. Raises ValueError on unknown."""
    backend = (backend or settings.VIDEO_BACKEND).lower()
    if backend == "opus":
        from generators.opus import OpusGenerator
        return OpusGenerator()
    if backend == "veo":
        return VeoAdapter()
    raise ValueError(
        f"Unknown VIDEO_BACKEND {backend!r}: must be 'opus' or 'veo'"
    )


class VeoAdapter:
    """Degraded-mode fallback: renders only shot 1 as a single 8s Veo clip.

    Veo cannot consume multi-shot scripts or reference photos. This adapter
    exists for pipeline continuity if Agent Opus is unavailable — not for
    quality parity.
    """

    def __init__(self):
        from generators.veo import VeoGenerator
        self._veo = VeoGenerator()

    def generate(self, script: Script, reference_photos: Sequence[Path]) -> Path:
        logger.warning(
            "VeoAdapter degraded mode: rendering only shot 1 of '{}' as an "
            "8s clip; reference photos ignored", script.id,
        )
        prompt = inject_persona(script.shots[0].description)
        return self._veo.generate(prompt, duration_seconds=8)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_factory.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add generators/factory.py tests/test_factory.py
git commit -m "feat: add video backend factory with VeoAdapter degraded fallback"
git push
```

---

### Task 9: Pipeline integration

**Files:**
- Modify: `pipeline/runner.py` (imports, `__init__`, `run`, `_select_prompt` → `_select_script`, `_build_caption`, `_save_failure`)
- Test: `tests/test_pipeline.py` (full rewrite)

**Interfaces:**
- Consumes: `create_generator` (Task 8), `ScriptManager` (Task 5), `load_reference_photos` (Task 3), `NIKA` (Task 2), existing `validate_video`, `TikTokPublisher`, `StorageManager`
- Produces: `Pipeline(dry_run=None)` with `run(script_id: str | None = None) -> dict`. Result dict keys: `prompt` (= script.title, backward compat for storage/digest), `script_id`, `title`, `video_path`, `caption`, `hashtags`, `publish_result`, `status`.

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
def mock_generator():
    gen = MagicMock()
    gen.generate.return_value = Path("/tmp/video.mp4")
    with patch("pipeline.runner.create_generator", return_value=gen) as factory:
        yield factory, gen


@pytest.fixture
def mock_scripts(sample_script):
    mgr = MagicMock()
    mgr.consume_script.return_value = sample_script
    mgr.peek_script.return_value = sample_script
    with patch("pipeline.runner.ScriptManager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_photos():
    with patch("pipeline.runner.load_reference_photos",
               return_value=(Path("/tmp/nika.jpg"),)) as loader:
        yield loader


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


ALL = ("mock_generator", "mock_scripts", "mock_photos",
       "mock_tiktok", "mock_storage", "mock_validate")


@pytest.mark.usefixtures(*ALL)
class TestPipelineInit:
    def test_uses_factory(self, mock_generator):
        factory, gen = mock_generator
        pipe = Pipeline(dry_run=False)
        factory.assert_called_once()
        assert pipe.generator is gen

    def test_dry_run_skips_publisher(self):
        assert Pipeline(dry_run=True).publisher is None


@pytest.mark.usefixtures(*ALL)
class TestRun:
    def test_publish_flow(self, mock_generator, mock_scripts, mock_tiktok,
                          mock_storage, sample_script):
        _, gen = mock_generator
        result = Pipeline(dry_run=False).run()

        mock_scripts.consume_script.assert_called_once_with(None)
        script_arg, photos_arg = gen.generate.call_args[0]
        assert script_arg is sample_script
        assert photos_arg == (Path("/tmp/nika.jpg"),)
        mock_tiktok.publish.assert_called_once()
        mock_storage.save_run.assert_called_once()
        assert result["status"] == "published"
        assert result["script_id"] == "belly-rub-betrayal"
        assert result["prompt"] == sample_script.title   # storage compat

    def test_dry_run_peeks_and_skips_publish(self, mock_scripts, mock_tiktok):
        result = Pipeline(dry_run=True).run()
        mock_scripts.peek_script.assert_called_once_with(None)
        mock_scripts.consume_script.assert_not_called()
        assert result["status"] == "dry_run"

    def test_script_id_forwarded(self, mock_scripts):
        Pipeline(dry_run=False).run(script_id="belly-rub-betrayal")
        mock_scripts.consume_script.assert_called_once_with("belly-rub-betrayal")

    def test_generate_failure_saves_failure(self, mock_generator, mock_storage):
        _, gen = mock_generator
        gen.generate.side_effect = RuntimeError("opus down")
        with pytest.raises(RuntimeError):
            Pipeline(dry_run=False).run()
        fail_record = mock_storage.save_run.call_args[0][2]
        assert fail_record["status"] == "failed"
        assert "opus down" in fail_record["error"]


@pytest.mark.usefixtures(*ALL)
class TestBuildCaption:
    def test_caption_from_script(self, sample_script):
        caption, hashtags = Pipeline(dry_run=True)._build_caption(sample_script)
        assert caption == "The belly was never an offer. It was a test."

    def test_hashtags_merge_base_persona_script(self, sample_script):
        from characters.persona import NIKA
        _, hashtags = Pipeline(dry_run=True)._build_caption(sample_script)
        for tag in Pipeline.BASE_HASHTAGS:
            assert tag in hashtags
        for tag in NIKA.hashtags:
            assert tag in hashtags
        assert "bellyrub" in hashtags

    def test_hashtags_deduped_preserving_order(self, sample_script):
        _, hashtags = Pipeline(dry_run=True)._build_caption(sample_script)
        assert len(hashtags) == len(set(hashtags))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_generator' from 'pipeline.runner'` (or AttributeError on patch targets)

- [ ] **Step 3: Rewrite pipeline/runner.py**

Replace the imports block (lines 18–24) with:

```python
from config import settings
from characters.persona import NIKA
from generators.factory import create_generator
from prompts.script import Script
from prompts.script_manager import ScriptManager
from publishers.tiktok import TikTokPublisher
from storage.manager import StorageManager
from utils.reference_photos import load_reference_photos
from utils.video_validator import validate_video
from utils.logger import logger
```

Replace `__init__` body's manager lines (lines 46–49) with:

```python
            self.storage = StorageManager()
            self.generator = create_generator()
            self.script_manager = ScriptManager()
            self.publisher = None if self.dry_run else TikTokPublisher()
```

Replace `run` (lines 57–142) with:

```python
    def run(self, script_id: str | None = None) -> dict:
        """
        Execute the full pipeline for one video.

        Args:
            script_id: Optional specific script id (filename stem). If None,
                       a random available script is selected.

        Returns:
            Result dict: {prompt, script_id, title, video_path, caption,
                          hashtags, publish_result, status}
        """
        script = None
        video_path = None

        try:
            # 1. Select script
            try:
                script = self._select_script(script_id)
                logger.info("Pipeline run started with script: '{}'", script.id)
            except Exception as e:
                self._handle_error("select_script", e)
                raise

            # 2. Generate video
            try:
                video_path = self.generator.generate(
                    script, load_reference_photos(),
                )
                logger.info("Video generated: {}", video_path)
            except Exception as e:
                self._handle_error("generate", e)
                raise

            # 3. Validate video
            try:
                validate_video(video_path)
            except Exception as e:
                self._handle_error("validate_video", e)
                raise

            # 4. Build caption and hashtags
            try:
                caption, hashtags = self._build_caption(script)
            except Exception as e:
                self._handle_error("build_caption", e)
                raise

            # 5. Publish (skip if dry_run)
            publish_result = None
            if self.dry_run:
                logger.info(
                    "DRY_RUN: skipping publish — would have posted: "
                    "video={}, caption={!r}, hashtags={}",
                    video_path, caption, hashtags,
                )
                status = "dry_run"
            else:
                try:
                    publish_result = self.publisher.publish(
                        video_path, caption, hashtags,
                    )
                    status = "published"
                except Exception as e:
                    self._handle_error("publish", e)
                    raise
        except Exception as e:
            self._save_failure(script, video_path, e)
            raise

        # 6. Save run record (only reached on success)
        result = {
            "prompt": script.title,          # backward compat: storage/digest read this
            "script_id": script.id,
            "title": script.title,
            "video_path": str(video_path),
            "caption": caption,
            "hashtags": hashtags,
            "publish_result": publish_result,
            "status": status,
        }
        try:
            self.storage.save_run(script.title, video_path, result)
        except Exception as e:
            self._handle_error("save_run", e)
            raise

        logger.info("Pipeline run complete (status={})", status)
        return result
```

Replace `_save_failure` and `_select_prompt` (lines 144–163) with:

```python
    def _save_failure(self, script, video_path, error):
        fail_result = {
            "prompt": script.title if script else "unknown",
            "script_id": script.id if script else None,
            "video_path": str(video_path) if video_path else None,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
        }
        try:
            self.storage.save_run(
                script.title if script else "unknown",
                video_path or Path("."),
                fail_result,
            )
        except Exception as save_err:
            logger.debug("Could not save failure record: {}", save_err)

    def _select_script(self, script_id: str | None = None) -> Script:
        if self.dry_run:
            return self.script_manager.peek_script(script_id)
        return self.script_manager.consume_script(script_id)
```

Replace `BASE_HASHTAGS`/`CATEGORY_HASHTAGS`/`_build_caption` (lines 165–182) with:

```python
    BASE_HASHTAGS = ["catvideos", "catsoftiktok", "aiart", "aigenerated"]

    def _build_caption(self, script: Script) -> tuple[str, list[str]]:
        caption = script.caption or script.hook or script.title

        # Base + persona brand + per-script tags, deduped preserving order
        hashtags = list(dict.fromkeys(
            [*self.BASE_HASHTAGS, *NIKA.hashtags, *script.hashtags]
        ))

        logger.info(
            "Built caption ({} chars, {} hashtags) for script '{}'",
            len(caption), len(hashtags), script.id,
        )
        return caption, hashtags
```

Also update the module docstring (line 5) from `prompts → Veo generator → storage → TikTok publisher` to `scripts → video generator (Opus/Veo) → storage → TikTok publisher`, and the class docstring list to say "Select script" / "Generate video via configured backend".

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run the full suite (except smoke)**

Run: `.venv/bin/python -m pytest -m "not smoke"`
Expected: everything passes EXCEPT `tests/test_main.py::test_prompt_forwarded` (fixed in Task 10). If other failures appear, fix before committing.

- [ ] **Step 6: Commit**

```bash
git add pipeline/runner.py tests/test_pipeline.py
git commit -m "feat: pipeline consumes scripts via backend factory with reference photos"
git push
```

---

### Task 10: CLI — --script flag, retire --category/--prompt

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `Pipeline.run(script_id=...)` (Task 9)
- Produces: CLI `--script <id>`; `--prompt` and `--category` removed with a clear migration error if used.

- [ ] **Step 1: Update tests (failing)**

In `tests/test_main.py`, replace `test_prompt_forwarded` with:

```python
    def test_script_forwarded(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--script", "belly-rub-betrayal"]):
            main()
        self.pipeline_instance.run.assert_called_once_with(
            script_id="belly-rub-betrayal",
        )

    def test_no_script_passes_none(self):
        with patch("sys.argv", ["main.py", "--dry-run"]):
            main()
        self.pipeline_instance.run.assert_called_once_with(script_id=None)

    def test_prompt_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--prompt", "A sleepy cat"]):
            with pytest.raises(SystemExit):
                main()

    def test_category_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--category", "funny"]):
            with pytest.raises(SystemExit):
                main()
```

If other tests in the file call `run(prompt=...)` expectations, update them to `run(script_id=None)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: FAIL — `run` called with `prompt=None`, not `script_id=None`

- [ ] **Step 3: Update main.py**

In `parse_args()`, replace the `--prompt` and `--category` lines with:

```python
    parser.add_argument("--script",   type=str,  default=None, help="Specific script id (filename stem in prompts/scripts/available/)")
    # Retired flags — kept so old cron entries fail loudly with guidance:
    parser.add_argument("--prompt",   type=str,  default=None, help=argparse.SUPPRESS)
    parser.add_argument("--category", type=str,  default=None, help=argparse.SUPPRESS)
```

In `main()`, replace the `--prompt`/`--category` handling block (lines 82–108) with:

```python
    if args.prompt or args.category:
        logger.error(
            "--prompt/--category were replaced by full scripts. "
            "Use --script <id> or let the pipeline pick from "
            "prompts/scripts/available/."
        )
        sys.exit(1)
```

Replace the run loop (lines 110–118) with:

```python
    from pipeline.runner import Pipeline
    for i in range(args.count):
        try:
            result = Pipeline().run(script_id=args.script)
            logger.info("Run {}/{} complete (status={})",
                        i + 1, args.count, result["status"])
        except Exception as e:
            logger.error("Run {}/{} failed: {}", i + 1, args.count, e)
            sys.exit(1)
```

Update the module docstring usage examples: replace `--prompt`/`--category` lines with `python main.py --script belly-rub-betrayal  # run a specific script`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: ALL PASS

- [ ] **Step 5: Full suite + coverage gate**

Run: `.venv/bin/python -m pytest -m "not smoke" --cov=generators --cov=prompts --cov=pipeline --cov=characters --cov=utils --cov-report=term-missing`
Expected: ALL PASS, new modules ≥80% coverage. (If pytest-cov isn't installed: `.venv/bin/pip install pytest-cov`.)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: replace --prompt/--category CLI flags with --script"
git push
```

---

## Post-plan work (separate sessions, not in this plan)

- **Phase 0 spike** (user-gated): probe Agent Opus API with real key → write `specs/opus-api-notes.md` → adjust `UPLOAD_PATH`/`GENERATE_PATH`/`JOB_PATH` constants and payload field names in `generators/opus_client.py` → run `tests/test_opus_smoke.py`.
- **Phase 5**: convert 4 existing `scripts/*.md` to frontmatter format; build `tools/generate_seed_scripts.py`; human review gate.
- **Phase 6**: specs rewrite, README, flip `VIDEO_BACKEND` default to `opus`, delete deprecated `prompt_manager.py` + JSON pools.
```
