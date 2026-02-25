import pytest
from unittest.mock import patch, MagicMock

from scheduler.cron import _parse_cron, _run_pipeline, run_scheduler


class TestParseCron:
    def test_default_schedule(self):
        result = _parse_cron("0 18 * * *")
        assert result == {
            "minute": "0",
            "hour": "18",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_complex_expression(self):
        result = _parse_cron("30 9,18 */2 1-6 MON-FRI")
        assert result == {
            "minute": "30",
            "hour": "9,18",
            "day": "*/2",
            "month": "1-6",
            "day_of_week": "MON-FRI",
        }

    def test_strips_whitespace(self):
        result = _parse_cron("  5 12 * * 0  ")
        assert result["minute"] == "5"
        assert result["hour"] == "12"

    def test_too_few_fields_raises(self):
        with pytest.raises(ValueError, match="Expected 5-field"):
            _parse_cron("0 18 *")

    def test_too_many_fields_raises(self):
        with pytest.raises(ValueError, match="Expected 5-field"):
            _parse_cron("0 18 * * * 2026")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Expected 5-field"):
            _parse_cron("")


class TestRunPipeline:
    def test_creates_and_runs_pipeline(self):
        mock_instance = MagicMock()
        mock_instance.run.return_value = {"status": "published"}
        with patch("pipeline.runner.Pipeline", return_value=mock_instance) as cls:
            _run_pipeline()
        cls.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_logs_success(self):
        mock_instance = MagicMock()
        mock_instance.run.return_value = {"status": "published"}
        with patch("pipeline.runner.Pipeline", return_value=mock_instance):
            with patch("scheduler.cron.logger") as mock_logger:
                _run_pipeline()
        info_calls = [c for c in mock_logger.info.call_args_list
                      if "Scheduled run complete" in str(c)]
        assert len(info_calls) == 1

    def test_catches_pipeline_error(self):
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("veo down")
        with patch("pipeline.runner.Pipeline", return_value=mock_instance):
            _run_pipeline()  # should not raise

    def test_logs_pipeline_error(self):
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("veo down")
        with patch("pipeline.runner.Pipeline", return_value=mock_instance):
            with patch("scheduler.cron.logger") as mock_logger:
                _run_pipeline()
        mock_logger.error.assert_called_once()
        assert "Scheduled run failed" in mock_logger.error.call_args[0][0]


class TestRunScheduler:
    def test_adds_job_and_starts(self):
        mock_scheduler = MagicMock()
        with patch("scheduler.cron.BlockingScheduler",
                   return_value=mock_scheduler) as cls:
            with patch("scheduler.cron.settings") as mock_settings:
                mock_settings.POST_SCHEDULE_CRON = "0 18 * * *"
                mock_settings.POST_TIMEZONE = "America/Los_Angeles"
                run_scheduler()
        cls.assert_called_once_with(timezone="America/Los_Angeles")
        mock_scheduler.add_job.assert_called_once()
        job_args = mock_scheduler.add_job.call_args
        assert job_args[0][0] is _run_pipeline
        assert job_args[1]["id"] == "pipeline_run"
        mock_scheduler.start.assert_called_once()

    def test_uses_cron_trigger(self):
        mock_scheduler = MagicMock()
        with patch("scheduler.cron.BlockingScheduler",
                   return_value=mock_scheduler):
            with patch("scheduler.cron.CronTrigger") as mock_trigger_cls:
                with patch("scheduler.cron.settings") as mock_settings:
                    mock_settings.POST_SCHEDULE_CRON = "30 9 * * 1"
                    mock_settings.POST_TIMEZONE = "UTC"
                    run_scheduler()
        mock_trigger_cls.assert_called_once_with(
            timezone="UTC",
            minute="30",
            hour="9",
            day="*",
            month="*",
            day_of_week="1",
        )

    def test_handles_keyboard_interrupt(self):
        mock_scheduler = MagicMock()
        mock_scheduler.start.side_effect = KeyboardInterrupt
        with patch("scheduler.cron.BlockingScheduler",
                   return_value=mock_scheduler):
            with patch("scheduler.cron.settings") as mock_settings:
                mock_settings.POST_SCHEDULE_CRON = "0 18 * * *"
                mock_settings.POST_TIMEZONE = "America/Los_Angeles"
                run_scheduler()  # should not raise

    def test_logs_scheduler_start(self):
        mock_scheduler = MagicMock()
        mock_scheduler.start.side_effect = KeyboardInterrupt
        with patch("scheduler.cron.BlockingScheduler",
                   return_value=mock_scheduler):
            with patch("scheduler.cron.settings") as mock_settings:
                mock_settings.POST_SCHEDULE_CRON = "0 18 * * *"
                mock_settings.POST_TIMEZONE = "America/Los_Angeles"
                with patch("scheduler.cron.logger") as mock_logger:
                    run_scheduler()
        info_calls = [c for c in mock_logger.info.call_args_list
                      if "Scheduler started" in str(c)]
        assert len(info_calls) == 1

    def test_invalid_cron_raises(self):
        with patch("scheduler.cron.settings") as mock_settings:
            mock_settings.POST_SCHEDULE_CRON = "bad"
            mock_settings.POST_TIMEZONE = "UTC"
            with pytest.raises(ValueError, match="Expected 5-field"):
                run_scheduler()
