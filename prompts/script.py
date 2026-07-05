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
