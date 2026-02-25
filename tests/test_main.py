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


class TestMainCategory:
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

    def test_category_selects_prompt(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--category", "funny"]):
            with patch("prompts.cat_prompts.get_prompt_by_category",
                       return_value="A funny cat prompt") as mock_get:
                main()
        mock_get.assert_called_once_with("funny")
        self.pipeline_instance.run.assert_called_once_with(
            prompt="A funny cat prompt",
        )

    def test_invalid_category_exits(self):
        with patch("sys.argv", ["main.py", "--dry-run", "--category", "bogus"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_prompt_and_category_mutually_exclusive(self):
        with patch("sys.argv", ["main.py", "--prompt", "x", "--category", "cozy"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_no_prompt_no_category_uses_none(self):
        with patch("sys.argv", ["main.py", "--dry-run"]):
            main()
        self.pipeline_instance.run.assert_called_once_with(prompt=None)


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
