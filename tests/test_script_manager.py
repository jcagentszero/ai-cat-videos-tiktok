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
