import pytest
from unittest.mock import patch, MagicMock

from main import main


class TestMainTwoLane:
    @pytest.fixture(autouse=True)
    def mock_validate(self):
        with patch("main.validate_config"):
            yield

    @pytest.fixture(autouse=True)
    def mock_pipeline(self):
        pipe_instance = MagicMock()
        pipe_instance.run.return_value = {"published": [], "prepared": None, "status": "ok"}
        pipe_instance.prepare.return_value = {"script_id": "x", "status": "prepared"}
        pipe_instance.publish_inbox.return_value = []
        pipe_instance.clip_footage.return_value = {"project_id": "P1", "clips": [], "status": "clipped"}
        with patch("pipeline.runner.Pipeline", return_value=pipe_instance) as cls:
            self.pipeline_cls = cls
            self.pipeline_instance = pipe_instance
            yield

    def test_prepare_invokes_prepare(self):
        with patch("sys.argv", ["main.py", "--prepare"]):
            main()
        self.pipeline_instance.prepare.assert_called_once_with(script_id=None)

    def test_prepare_with_script_id(self):
        with patch("sys.argv", ["main.py", "--prepare", "--script", "belly-rub-betrayal"]):
            main()
        self.pipeline_instance.prepare.assert_called_once_with(
            script_id="belly-rub-betrayal",
        )

    def test_publish_invokes_publish_inbox(self):
        with patch("sys.argv", ["main.py", "--publish"]):
            main()
        self.pipeline_instance.publish_inbox.assert_called_once()

    def test_clip_invokes_clip_footage(self, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        with patch("sys.argv", ["main.py", "--clip", str(video)]):
            main()
        self.pipeline_instance.clip_footage.assert_called_once()

    def test_clip_missing_file_exits(self):
        with patch("sys.argv", ["main.py", "--clip", "/nope/missing.mp4"]):
            with pytest.raises(SystemExit):
                main()

    def test_default_runs_daily_routine(self):
        with patch("sys.argv", ["main.py"]):
            main()
        self.pipeline_instance.run.assert_called_once_with()

    def test_prompt_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--prompt", "A sleepy cat"]):
            with pytest.raises(SystemExit):
                main()

    def test_category_flag_rejected(self):
        with patch("sys.argv", ["main.py", "--category", "funny"]):
            with pytest.raises(SystemExit):
                main()

    def test_script_without_prepare_rejected(self):
        with patch("sys.argv", ["main.py", "--script", "some-id"]):
            with pytest.raises(SystemExit):
                main()


class TestMainDryRun:
    @pytest.fixture(autouse=True)
    def mock_validate(self):
        with patch("main.validate_config"):
            yield

    @pytest.fixture(autouse=True)
    def mock_pipeline(self):
        pipe_instance = MagicMock()
        pipe_instance.run.return_value = {"status": "dry_run"}
        with patch("pipeline.runner.Pipeline", return_value=pipe_instance) as cls:
            self.pipeline_cls = cls
            self.pipeline_instance = pipe_instance
            yield

    def test_dry_run_flag_sets_settings(self):
        import config.settings as s
        original = s.DRY_RUN
        try:
            with patch("sys.argv", ["main.py", "--dry-run"]):
                s.DRY_RUN = False
                main()
                assert s.DRY_RUN is True
        finally:
            s.DRY_RUN = original

    def test_no_dry_run_flag_preserves_settings(self):
        import config.settings as s
        original = s.DRY_RUN
        try:
            s.DRY_RUN = False
            with patch("sys.argv", ["main.py"]):
                main()
            assert s.DRY_RUN is False
        finally:
            s.DRY_RUN = original

    def test_pipeline_invoked(self):
        with patch("sys.argv", ["main.py", "--dry-run"]):
            main()
        self.pipeline_cls.assert_called_once()
        self.pipeline_instance.run.assert_called_once_with()

    def test_count_runs_multiple(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--count", "3"]):
            main()
        assert self.pipeline_cls.call_count == 3
        assert self.pipeline_instance.run.call_count == 3


class TestMainAnalytics:
    def test_analytics_calls_collect(self):
        with patch("sys.argv", ["main.py", "--analytics"]):
            with patch("pipeline.analytics_collector.collect_analytics",
                       return_value={"collected": 2, "failed": 0}) as mock_collect:
                main()
        mock_collect.assert_called_once()

    def test_analytics_does_not_run_pipeline(self):
        with patch("sys.argv", ["main.py", "--analytics"]):
            with patch("pipeline.analytics_collector.collect_analytics",
                       return_value={"collected": 0, "failed": 0}):
                with patch("pipeline.runner.Pipeline") as mock_pipeline:
                    main()
        mock_pipeline.assert_not_called()

    def test_analytics_exits_on_error(self):
        with patch("sys.argv", ["main.py", "--analytics"]):
            with patch("pipeline.analytics_collector.collect_analytics",
                       side_effect=RuntimeError("api down")):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 1


class TestMainDigest:
    def test_digest_calls_generate_daily_digest(self):
        with patch("sys.argv", ["main.py", "--digest"]):
            with patch("pipeline.digest.generate_daily_digest") as mock_digest:
                main()
        mock_digest.assert_called_once()

    def test_digest_does_not_run_pipeline(self):
        with patch("sys.argv", ["main.py", "--digest"]):
            with patch("pipeline.digest.generate_daily_digest"):
                with patch("pipeline.runner.Pipeline") as mock_pipeline:
                    main()
        mock_pipeline.assert_not_called()
