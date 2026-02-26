import json
import threading

import pytest

from prompts.prompt_manager import PromptManager, VALID_CATEGORIES, DAY_SCHEDULE


SAMPLE_PROMPTS = {
    "funny": ["funny prompt 1", "funny prompt 2", "funny prompt 3"],
    "playful": ["playful prompt 1", "playful prompt 2"],
    "cute": ["cute prompt 1"],
}

EMPTY_USED = {"funny": [], "playful": [], "cute": []}


@pytest.fixture
def prompt_files(tmp_path):
    avail = tmp_path / "available.json"
    used = tmp_path / "used.json"
    avail.write_text(json.dumps(SAMPLE_PROMPTS))
    used.write_text(json.dumps(EMPTY_USED))
    return avail, used


@pytest.fixture
def pm(prompt_files):
    avail, used = prompt_files
    return PromptManager(available_path=avail, used_path=used)


class TestConsume:
    def test_returns_tuple(self, pm):
        result = pm.consume_prompt("funny")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_prompt_from_requested_category(self, pm):
        prompt, category = pm.consume_prompt("funny")
        assert category == "funny"
        assert prompt in SAMPLE_PROMPTS["funny"]

    def test_removes_prompt_from_available(self, pm):
        prompt, _ = pm.consume_prompt("funny")
        counts = pm.get_available_count()
        assert counts["funny"] == 2

    def test_adds_prompt_to_used(self, pm):
        prompt, _ = pm.consume_prompt("funny")
        used_prompts = [e["prompt"] for e in pm._used["funny"]]
        assert prompt in used_prompts

    def test_used_entry_has_timestamp(self, pm):
        pm.consume_prompt("funny")
        entry = pm._used["funny"][0]
        assert "consumed_at" in entry

    def test_persists_to_disk(self, pm, prompt_files):
        avail_path, used_path = prompt_files
        prompt, _ = pm.consume_prompt("cute")

        avail_on_disk = json.loads(avail_path.read_text())
        used_on_disk = json.loads(used_path.read_text())

        assert prompt not in avail_on_disk["cute"]
        used_prompts = [e["prompt"] for e in used_on_disk["cute"]]
        assert prompt in used_prompts

    def test_uses_day_schedule_when_no_category(self, pm):
        from unittest.mock import patch
        from datetime import datetime
        # Monday = 0 = "funny"
        mon = datetime(2026, 2, 23, 12, 0)
        with patch("prompts.prompt_manager.datetime") as mock_dt:
            mock_dt.now.return_value = mon
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            _, category = pm.consume_prompt()
        assert category == DAY_SCHEDULE[0]


class TestDepletion:
    def test_falls_back_when_category_exhausted(self, pm):
        # Exhaust cute (only 1 prompt)
        pm.consume_prompt("cute")
        # Should fall back to another category
        prompt, category = pm.consume_prompt("cute")
        assert category != "cute"
        assert isinstance(prompt, str)

    def test_raises_when_all_empty(self, pm):
        # Exhaust everything: 3 funny + 2 playful + 1 cute = 6
        for _ in range(6):
            pm.consume_prompt()
        with pytest.raises(RuntimeError, match="All prompt pools are empty"):
            pm.consume_prompt()


class TestFindCategory:
    def test_finds_available_prompt(self, pm):
        assert pm.find_category("funny prompt 1") == "funny"
        assert pm.find_category("playful prompt 1") == "playful"
        assert pm.find_category("cute prompt 1") == "cute"

    def test_finds_used_prompt(self, pm):
        prompt, _ = pm.consume_prompt("funny")
        assert pm.find_category(prompt) == "funny"

    def test_returns_none_for_unknown(self, pm):
        assert pm.find_category("totally unknown prompt") is None


class TestGetAvailableCount:
    def test_returns_dict(self, pm):
        counts = pm.get_available_count()
        assert isinstance(counts, dict)

    def test_correct_initial_counts(self, pm):
        counts = pm.get_available_count()
        assert counts["funny"] == 3
        assert counts["playful"] == 2
        assert counts["cute"] == 1

    def test_decrements_after_consume(self, pm):
        pm.consume_prompt("funny")
        counts = pm.get_available_count()
        assert counts["funny"] == 2


class TestPersistence:
    def test_reload_preserves_state(self, prompt_files):
        avail, used = prompt_files
        pm1 = PromptManager(available_path=avail, used_path=used)
        prompt, _ = pm1.consume_prompt("funny")

        pm2 = PromptManager(available_path=avail, used_path=used)
        assert pm2.get_available_count()["funny"] == 2
        used_prompts = [e["prompt"] for e in pm2._used["funny"]]
        assert prompt in used_prompts

    def test_handles_missing_files(self, tmp_path):
        avail = tmp_path / "nonexistent_avail.json"
        used = tmp_path / "nonexistent_used.json"
        pm = PromptManager(available_path=avail, used_path=used)
        counts = pm.get_available_count()
        assert all(c == 0 for c in counts.values())


class TestThreadSafety:
    def test_concurrent_consumes_no_duplicates(self, tmp_path):
        prompts = {
            "funny": [f"funny prompt {i}" for i in range(50)],
            "playful": [f"playful prompt {i}" for i in range(50)],
            "cute": [f"cute prompt {i}" for i in range(50)],
        }
        avail = tmp_path / "available.json"
        used = tmp_path / "used.json"
        avail.write_text(json.dumps(prompts))
        used.write_text(json.dumps(EMPTY_USED))

        pm = PromptManager(available_path=avail, used_path=used)
        results = []
        errors = []

        def consume():
            try:
                result = pm.consume_prompt()
                results.append(result)
            except RuntimeError:
                errors.append(True)

        threads = [threading.Thread(target=consume) for _ in range(150)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        consumed_prompts = [r[0] for r in results]
        assert len(consumed_prompts) == len(set(consumed_prompts))  # no duplicates
        assert len(consumed_prompts) == 150

        counts = pm.get_available_count()
        total_remaining = sum(counts.values())
        assert total_remaining == 0
