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
