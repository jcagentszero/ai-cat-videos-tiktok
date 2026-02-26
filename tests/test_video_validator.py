import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from utils.video_validator import (
    validate_video,
    VideoValidationError,
    TIKTOK_MAX_FILE_SIZE,
    TIKTOK_MIN_DURATION,
    TIKTOK_MAX_DURATION,
    _check_mp4_header,
    _check_duration,
)

_PATCH_RUN = "utils.video_validator.subprocess.run"


def _make_mp4(path, size=1024):
    ftyp = b"\x00\x00\x00\x14" + b"ftyp" + b"isom" + b"\x00" * 8
    padding = b"\x00" * max(0, size - len(ftyp))
    path.write_bytes(ftyp + padding)
    return path


def _ffprobe_result(duration):
    output = json.dumps({"format": {"duration": str(duration)}})
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=output, stderr="",
    )


class TestValidateVideo:
    def test_valid_mp4_passes(self, tmp_path):
        video = _make_mp4(tmp_path / "test.mp4")
        with patch("utils.video_validator._check_duration"):
            validate_video(video)

    def test_file_not_found_raises(self, tmp_path):
        missing = tmp_path / "missing.mp4"
        with pytest.raises(VideoValidationError, match="not found"):
            validate_video(missing)

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        with pytest.raises(VideoValidationError, match="empty"):
            validate_video(empty)

    def test_invalid_header_raises(self, tmp_path):
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"\x00" * 100)
        with pytest.raises(VideoValidationError, match="ftyp"):
            validate_video(bad)

    def test_file_too_large_raises(self, tmp_path):
        video = _make_mp4(tmp_path / "big.mp4")
        with patch("utils.video_validator._check_duration"):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = MagicMock(
                    st_size=TIKTOK_MAX_FILE_SIZE + 1,
                )
                with pytest.raises(VideoValidationError, match="too large"):
                    validate_video(video)

    def test_accepts_path_as_string(self, tmp_path):
        video = _make_mp4(tmp_path / "test.mp4")
        with patch("utils.video_validator._check_duration"):
            validate_video(str(video))


class TestCheckMp4Header:
    def test_valid_ftyp_passes(self, tmp_path):
        video = _make_mp4(tmp_path / "valid.mp4")
        _check_mp4_header(video)

    def test_short_file_raises(self, tmp_path):
        short = tmp_path / "short.mp4"
        short.write_bytes(b"\x00\x00\x00")
        with pytest.raises(VideoValidationError, match="ftyp"):
            _check_mp4_header(short)

    def test_wrong_header_raises(self, tmp_path):
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"\x00\x00\x00\x08" + b"moov" + b"\x00" * 100)
        with pytest.raises(VideoValidationError, match="ftyp"):
            _check_mp4_header(bad)

    def test_unreadable_file_raises(self, tmp_path):
        video = tmp_path / "locked.mp4"
        with patch("builtins.open", side_effect=OSError("permission denied")):
            with pytest.raises(VideoValidationError, match="Cannot read"):
                _check_mp4_header(video)


class TestCheckDuration:
    def test_valid_duration_passes(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, return_value=_ffprobe_result(6.0)):
            _check_duration(video)

    def test_too_short_raises(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, return_value=_ffprobe_result(0.5)):
            with pytest.raises(VideoValidationError, match="too short"):
                _check_duration(video)

    def test_too_long_raises(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, return_value=_ffprobe_result(700.0)):
            with pytest.raises(VideoValidationError, match="too long"):
                _check_duration(video)

    def test_ffprobe_not_found_skips(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, side_effect=FileNotFoundError):
            _check_duration(video)  # should not raise

    def test_ffprobe_timeout_skips(self, tmp_path):
        video = tmp_path / "test.mp4"
        exc = subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)
        with patch(_PATCH_RUN, side_effect=exc):
            _check_duration(video)  # should not raise

    def test_ffprobe_nonzero_exit_skips(self, tmp_path):
        video = tmp_path / "test.mp4"
        bad = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error",
        )
        with patch(_PATCH_RUN, return_value=bad):
            _check_duration(video)  # should not raise

    def test_ffprobe_bad_json_skips(self, tmp_path):
        video = tmp_path / "test.mp4"
        bad = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not json", stderr="",
        )
        with patch(_PATCH_RUN, return_value=bad):
            _check_duration(video)  # should not raise

    def test_ffprobe_missing_duration_key_skips(self, tmp_path):
        video = tmp_path / "test.mp4"
        bad = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"format": {}}),
            stderr="",
        )
        with patch(_PATCH_RUN, return_value=bad):
            _check_duration(video)  # should not raise

    def test_min_boundary_passes(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, return_value=_ffprobe_result(TIKTOK_MIN_DURATION)):
            _check_duration(video)

    def test_max_boundary_passes(self, tmp_path):
        video = tmp_path / "test.mp4"
        with patch(_PATCH_RUN, return_value=_ffprobe_result(TIKTOK_MAX_DURATION)):
            _check_duration(video)
