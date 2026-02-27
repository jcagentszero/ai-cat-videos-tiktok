"""
prompts/prompt_manager.py
─────────────────────────
Manages prompt lifecycle with JSON persistence and consume-on-use semantics.

Prompts live in JSON files so they can be consumed at runtime:
  - available_prompts.json: pool of unused prompts per category
  - used_prompts.json: archive of consumed prompts with timestamps

Once a prompt is consumed it moves from available → used and is never reused.
"""

import json
import random
import threading
from datetime import datetime
from pathlib import Path

from utils.logger import logger

_PROMPTS_DIR = Path(__file__).parent
_AVAILABLE_PATH = _PROMPTS_DIR / "available_prompts.json"
_USED_PATH = _PROMPTS_DIR / "used_prompts.json"

VALID_CATEGORIES = ("funny", "playful", "cute")

DAY_SCHEDULE = {
    0: "funny",     # Monday
    1: "playful",   # Tuesday
    2: "cute",      # Wednesday
    3: "funny",     # Thursday
    4: "playful",   # Friday
    5: "funny",     # Saturday
    6: "cute",      # Sunday
}


class PromptManager:
    """Thread-safe prompt manager with consume-on-use persistence."""

    def __init__(
        self,
        available_path: Path | str = _AVAILABLE_PATH,
        used_path: Path | str = _USED_PATH,
    ):
        self._available_path = Path(available_path)
        self._used_path = Path(used_path)
        self._lock = threading.Lock()
        self._available = self._load(self._available_path)
        self._used = self._load(self._used_path)

    def _load(self, path: Path) -> dict:
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {cat: [] for cat in VALID_CATEGORIES}

    def _persist(self) -> None:
        with open(self._available_path, "w") as f:
            json.dump(self._available, f, indent=2)
        with open(self._used_path, "w") as f:
            json.dump(self._used, f, indent=2)

    def consume_prompt(self, category: str | None = None) -> tuple[str, str]:
        """Pick a random prompt, remove from available, archive to used.

        Args:
            category: Target category. Falls back to any non-empty category
                      if the requested one is exhausted. If None, uses the
                      day-of-week schedule.

        Returns:
            (prompt, category) tuple.

        Raises:
            RuntimeError: If all prompt pools are empty.
        """
        with self._lock:
            if category is None:
                day = datetime.now().weekday()
                category = DAY_SCHEDULE[day]

            # Try requested category first
            if self._available.get(category):
                return self._consume_from(category)

            # Fall back to any non-empty category
            for fallback in VALID_CATEGORIES:
                if self._available.get(fallback):
                    logger.warning(
                        "Category '{}' exhausted, falling back to '{}'",
                        category, fallback,
                    )
                    return self._consume_from(fallback)

            raise RuntimeError("All prompt pools are empty")

    def _consume_from(self, category: str) -> tuple[str, str]:
        """Remove a random prompt from category and persist. Caller holds lock."""
        pool = self._available[category]
        prompt = random.choice(pool)
        pool.remove(prompt)

        self._used.setdefault(category, []).append({
            "prompt": prompt,
            "consumed_at": datetime.now().isoformat(),
        })

        self._persist()

        remaining = len(pool)
        logger.info(
            "Consumed prompt from '{}' ({} remaining)", category, remaining,
        )
        return prompt, category

    def peek_prompt(self, category: str | None = None) -> tuple[str, str]:
        """Pick a random prompt without consuming it (for dry runs).

        Same selection logic as consume_prompt but does not modify pools.
        """
        with self._lock:
            if category is None:
                day = datetime.now().weekday()
                category = DAY_SCHEDULE[day]

            if self._available.get(category):
                prompt = random.choice(self._available[category])
                return prompt, category

            for fallback in VALID_CATEGORIES:
                if self._available.get(fallback):
                    prompt = random.choice(self._available[fallback])
                    return prompt, fallback

            raise RuntimeError("All prompt pools are empty")

    def find_category(self, prompt: str) -> str | None:
        """Reverse-lookup category for a prompt across both pools."""
        for cat in VALID_CATEGORIES:
            if prompt in self._available.get(cat, []):
                return cat
            for entry in self._used.get(cat, []):
                used_prompt = entry if isinstance(entry, str) else entry.get("prompt")
                if used_prompt == prompt:
                    return cat
        return None

    def get_available_count(self) -> dict[str, int]:
        """Return count of available prompts per category."""
        return {cat: len(self._available.get(cat, [])) for cat in VALID_CATEGORIES}
