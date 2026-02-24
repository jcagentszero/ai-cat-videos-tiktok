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
