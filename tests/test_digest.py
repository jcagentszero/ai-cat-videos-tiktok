import pytest
from unittest.mock import patch, MagicMock

from pipeline.digest import generate_daily_digest


@pytest.fixture
def mock_storage():
    mgr = MagicMock()
    mgr.get_runs_for_date.return_value = []
    with patch("pipeline.digest.StorageManager", return_value=mgr):
        yield mgr


def _make_run(timestamp, prompt, status, caption=None, error=None):
    result = {"status": status}
    if caption:
        result["caption"] = caption
    if error:
        result["error"] = error
    return {
        "timestamp": timestamp,
        "prompt": prompt,
        "video_path": f"/fake/{prompt.replace(' ', '_')}.mp4",
        "result": result,
    }


class TestGenerateDailyDigest:
    def test_returns_expected_keys(self, mock_storage):
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert set(result.keys()) == {"date", "total", "successful", "failed", "report"}

    def test_empty_runs(self, mock_storage):
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert result["total"] == 0
        assert result["successful"] == 0
        assert result["failed"] == 0
        assert "No pipeline runs recorded" in result["report"]

    def test_counts_successful_runs(self, mock_storage):
        mock_storage.get_runs_for_date.return_value = [
            _make_run("2026-02-24T10:00:00", "cat a", "published", caption="Cat A"),
            _make_run("2026-02-24T14:00:00", "cat b", "dry_run", caption="Cat B"),
        ]
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert result["total"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0

    def test_counts_failed_runs(self, mock_storage):
        mock_storage.get_runs_for_date.return_value = [
            _make_run("2026-02-24T10:00:00", "cat a", "published", caption="Cat A"),
            _make_run("2026-02-24T12:00:00", "cat b", "failed", error="RuntimeError: veo down"),
        ]
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert result["total"] == 2
        assert result["successful"] == 1
        assert result["failed"] == 1

    def test_report_contains_date(self, mock_storage):
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert "2026-02-24" in result["report"]

    def test_report_lists_posted_videos(self, mock_storage):
        mock_storage.get_runs_for_date.return_value = [
            _make_run("2026-02-24T10:00:00", "cat sleeping", "published", caption="Cat sleeping"),
        ]
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert "Cat sleeping" in result["report"]
        assert "Posted Videos" in result["report"]

    def test_report_lists_failures(self, mock_storage):
        mock_storage.get_runs_for_date.return_value = [
            _make_run("2026-02-24T10:00:00", "cat x", "failed", error="RuntimeError: veo down"),
        ]
        result = generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        assert "RuntimeError: veo down" in result["report"]
        assert "Failures" in result["report"]

    def test_date_passed_to_storage(self, mock_storage):
        generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        mock_storage.get_runs_for_date.assert_called_once_with("2026-02-24")

    def test_defaults_to_today(self, mock_storage):
        with patch("pipeline.digest.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2026-02-24"
            result = generate_daily_digest(storage=mock_storage)
        assert result["date"] == "2026-02-24"

    def test_creates_storage_when_none(self, mock_storage):
        with patch("pipeline.digest.StorageManager", return_value=mock_storage) as cls:
            generate_daily_digest(date_str="2026-02-24")
        cls.assert_called_once()

    def test_sends_email_when_configured(self, mock_storage):
        mock_smtp_instance = MagicMock()
        with patch("pipeline.digest.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.digest.smtplib.SMTP") as mock_smtp_cls:
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        mock_smtp_instance.send_message.assert_called_once()
        msg = mock_smtp_instance.send_message.call_args[0][0]
        assert msg["To"] == "user@example.com"
        assert "2026-02-24" in msg["Subject"]

    def test_skips_email_when_not_configured(self, mock_storage):
        with patch("pipeline.digest.settings.NOTIFY_EMAIL", ""):
            with patch("pipeline.digest.smtplib") as mock_smtp:
                generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
        mock_smtp.SMTP.assert_not_called()

    def test_email_failure_does_not_raise(self, mock_storage):
        with patch("pipeline.digest.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.digest.smtplib.SMTP", side_effect=ConnectionRefusedError("no smtp")):
                generate_daily_digest(date_str="2026-02-24", storage=mock_storage)
