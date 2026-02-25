import pytest
from unittest.mock import patch, MagicMock

from main import main


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
        self.pipeline_instance.run.assert_called_once()

    def test_prompt_forwarded(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--prompt", "A sleepy cat"]):
            main()
        self.pipeline_instance.run.assert_called_once_with(prompt="A sleepy cat")

    def test_count_runs_multiple(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--count", "3"]):
            main()
        assert self.pipeline_cls.call_count == 3
        assert self.pipeline_instance.run.call_count == 3
