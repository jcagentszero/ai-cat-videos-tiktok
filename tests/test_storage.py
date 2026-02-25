import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from storage.manager import StorageManager


@pytest.fixture
def storage(tmp_path):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    with patch("config.settings.OUTPUT_DIR", output_dir), \
         patch("config.settings.LOGS_DIR", logs_dir):
        mgr = StorageManager()
        yield mgr


@pytest.fixture
def run_log(tmp_path):
    return tmp_path / "logs" / "run_history.json"


class TestNextVideoPath:
    def test_first_video_of_day(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        today = datetime.now().strftime("%Y%m%d")
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert path == output_dir / f"video_{today}_001.mp4"

    def test_increments_sequence(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        today = datetime.now().strftime("%Y%m%d")
        (output_dir / f"video_{today}_001.mp4").touch()
        (output_dir / f"video_{today}_002.mp4").touch()
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert path == output_dir / f"video_{today}_003.mp4"

    def test_ignores_other_dates(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        today = datetime.now().strftime("%Y%m%d")
        (output_dir / "video_20200101_005.mp4").touch()
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert path == output_dir / f"video_{today}_001.mp4"

    def test_handles_gap_in_sequence(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        today = datetime.now().strftime("%Y%m%d")
        (output_dir / f"video_{today}_001.mp4").touch()
        (output_dir / f"video_{today}_005.mp4").touch()
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert path == output_dir / f"video_{today}_006.mp4"

    def test_returns_path_object(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert isinstance(path, Path)

    def test_pads_sequence_to_three_digits(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        with patch("config.settings.OUTPUT_DIR", output_dir):
            path = storage.next_video_path()
        assert path.stem.endswith("_001")


class TestSaveRun:
    def test_creates_file_when_missing(self, storage, run_log):
        video = Path("/tmp/output/video_20260224_001.mp4")
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("a cat sleeping", video, {"status": "ok"})
        assert run_log.exists()
        records = json.loads(run_log.read_text())
        assert len(records) == 1
        assert records[0]["prompt"] == "a cat sleeping"

    def test_appends_to_existing(self, storage, run_log):
        video = Path("/tmp/output/video_20260224_001.mp4")
        run_log.write_text(json.dumps([{"prompt": "old"}]))
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("new prompt", video, {"status": "ok"})
        records = json.loads(run_log.read_text())
        assert len(records) == 2
        assert records[0]["prompt"] == "old"
        assert records[1]["prompt"] == "new prompt"

    def test_record_has_expected_fields(self, storage, run_log):
        video = Path("/tmp/output/video_20260224_001.mp4")
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("cat on keyboard", video, {"published": True})
        record = json.loads(run_log.read_text())[0]
        assert "timestamp" in record
        assert record["video_path"] == str(video)
        assert record["result"] == {"published": True}

    def test_handles_corrupt_json(self, storage, run_log):
        run_log.write_text("not valid json{{{")
        video = Path("/tmp/output/video_20260224_001.mp4")
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("a cat jumping", video, {})
        records = json.loads(run_log.read_text())
        assert len(records) == 1
        assert records[0]["prompt"] == "a cat jumping"

    def test_stores_video_path_as_string(self, storage, run_log):
        video = Path("/tmp/output/video_20260224_002.mp4")
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("cat stretching", video, {})
        record = json.loads(run_log.read_text())[0]
        assert isinstance(record["video_path"], str)

    def test_timestamp_is_iso_format(self, storage, run_log):
        video = Path("/tmp/output/video_20260224_001.mp4")
        with patch("storage.manager.RUN_LOG", run_log):
            storage.save_run("cat yawning", video, {})
        record = json.loads(run_log.read_text())[0]
        datetime.fromisoformat(record["timestamp"])


class TestGetRecentPrompts:
    def test_returns_empty_when_no_file(self, storage, run_log):
        with patch("storage.manager.RUN_LOG", run_log):
            assert storage.get_recent_prompts() == []

    def test_returns_all_prompts_when_fewer_than_n(self, storage, run_log):
        history = [
            {"prompt": "cat sleeping", "timestamp": "2026-01-01T00:00:00"},
            {"prompt": "cat jumping", "timestamp": "2026-01-02T00:00:00"},
        ]
        run_log.write_text(json.dumps(history))
        with patch("storage.manager.RUN_LOG", run_log):
            result = storage.get_recent_prompts(n=10)
        assert result == ["cat sleeping", "cat jumping"]

    def test_returns_last_n_prompts(self, storage, run_log):
        history = [{"prompt": f"prompt {i}"} for i in range(5)]
        run_log.write_text(json.dumps(history))
        with patch("storage.manager.RUN_LOG", run_log):
            result = storage.get_recent_prompts(n=3)
        assert result == ["prompt 2", "prompt 3", "prompt 4"]

    def test_handles_corrupt_json(self, storage, run_log):
        run_log.write_text("not valid json{{{")
        with patch("storage.manager.RUN_LOG", run_log):
            assert storage.get_recent_prompts() == []

    def test_skips_records_without_prompt_key(self, storage, run_log):
        history = [
            {"prompt": "cat sleeping"},
            {"no_prompt_here": True},
            {"prompt": "cat jumping"},
        ]
        run_log.write_text(json.dumps(history))
        with patch("storage.manager.RUN_LOG", run_log):
            result = storage.get_recent_prompts()
        assert result == ["cat sleeping", "cat jumping"]

    def test_default_n_is_ten(self, storage, run_log):
        history = [{"prompt": f"prompt {i}"} for i in range(15)]
        run_log.write_text(json.dumps(history))
        with patch("storage.manager.RUN_LOG", run_log):
            result = storage.get_recent_prompts()
        assert len(result) == 10
        assert result[0] == "prompt 5"


def _create_videos(output_dir, count, base_time=1000000):
    """Helper to create mp4 files with distinct modification times."""
    import os
    paths = []
    for i in range(count):
        p = output_dir / f"video_{i:03d}.mp4"
        p.write_bytes(b"\x00" * 100)
        os.utime(p, (base_time + i, base_time + i))
        paths.append(p)
    return paths


class TestCleanupOldVideos:
    def test_deletes_oldest_videos(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        videos = _create_videos(output_dir, 5)
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=2)
        remaining = list(output_dir.glob("*.mp4"))
        assert len(remaining) == 2
        assert videos[3] in remaining
        assert videos[4] in remaining

    def test_no_op_when_fewer_than_keep_last(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        _create_videos(output_dir, 3)
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=5)
        assert len(list(output_dir.glob("*.mp4"))) == 3

    def test_no_op_when_exactly_keep_last(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        _create_videos(output_dir, 3)
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=3)
        assert len(list(output_dir.glob("*.mp4"))) == 3

    def test_no_op_when_empty_directory(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=5)
        assert len(list(output_dir.glob("*.mp4"))) == 0

    def test_ignores_non_mp4_files(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        _create_videos(output_dir, 3)
        (output_dir / "readme.txt").write_text("keep me")
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=1)
        assert (output_dir / "readme.txt").exists()

    def test_keeps_newest_by_mtime(self, storage, tmp_path):
        import os
        output_dir = tmp_path / "output"
        old = output_dir / "old_video.mp4"
        new = output_dir / "new_video.mp4"
        old.write_bytes(b"\x00")
        new.write_bytes(b"\x00")
        os.utime(old, (1000, 1000))
        os.utime(new, (9999, 9999))
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos(keep_last=1)
        assert not old.exists()
        assert new.exists()

    def test_handles_delete_failure(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        videos = _create_videos(output_dir, 3)
        with patch("config.settings.OUTPUT_DIR", output_dir), \
             patch.object(type(videos[0]), "unlink", side_effect=OSError("permission denied")):
            storage.cleanup_old_videos(keep_last=1)

    def test_default_keep_last_is_30(self, storage, tmp_path):
        output_dir = tmp_path / "output"
        _create_videos(output_dir, 35)
        with patch("config.settings.OUTPUT_DIR", output_dir):
            storage.cleanup_old_videos()
        assert len(list(output_dir.glob("*.mp4"))) == 30
