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
    """Manages the pool of full, multi-shot video scripts awaiting handoff."""

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
