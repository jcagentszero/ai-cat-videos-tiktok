import pytest
from unittest.mock import patch, MagicMock

from pipeline.runner import Pipeline


@pytest.fixture
def mock_veo():
    gen = MagicMock()
    with patch("pipeline.runner.VeoGenerator", return_value=gen) as cls:
        yield cls, gen


@pytest.fixture
def mock_tiktok():
    pub = MagicMock()
    with patch("pipeline.runner.TikTokPublisher", return_value=pub) as cls:
        yield cls, pub


@pytest.fixture
def mock_storage(tmp_path):
    mgr = MagicMock()
    with patch("pipeline.runner.StorageManager", return_value=mgr) as cls:
        yield cls, mgr


class TestPipelineInit:
    def test_creates_storage(self, mock_veo, mock_tiktok, mock_storage):
        cls, mgr = mock_storage
        pipe = Pipeline(dry_run=False)
        cls.assert_called_once()
        assert pipe.storage is mgr

    def test_creates_generator(self, mock_veo, mock_tiktok, mock_storage):
        cls, gen = mock_veo
        Pipeline(dry_run=False)
        cls.assert_called_once()

    def test_stores_generator(self, mock_veo, mock_tiktok, mock_storage):
        _, gen = mock_veo
        pipe = Pipeline(dry_run=False)
        assert pipe.generator is gen

    def test_creates_publisher_when_not_dry_run(self, mock_veo, mock_tiktok, mock_storage):
        cls, pub = mock_tiktok
        pipe = Pipeline(dry_run=False)
        cls.assert_called_once()
        assert pipe.publisher is pub

    def test_skips_publisher_when_dry_run(self, mock_veo, mock_tiktok, mock_storage):
        cls, _ = mock_tiktok
        pipe = Pipeline(dry_run=True)
        cls.assert_not_called()
        assert pipe.publisher is None

    def test_dry_run_defaults_to_settings(self, mock_veo, mock_tiktok, mock_storage):
        with patch("pipeline.runner.settings.DRY_RUN", True):
            pipe = Pipeline()
        assert pipe.dry_run is True

    def test_dry_run_false_default(self, mock_veo, mock_tiktok, mock_storage):
        with patch("pipeline.runner.settings.DRY_RUN", False):
            pipe = Pipeline()
        assert pipe.dry_run is False

    def test_dry_run_explicit_overrides_settings(self, mock_veo, mock_tiktok, mock_storage):
        with patch("pipeline.runner.settings.DRY_RUN", False):
            pipe = Pipeline(dry_run=True)
        assert pipe.dry_run is True

    def test_raises_on_generator_failure(self, mock_tiktok, mock_storage):
        with patch("pipeline.runner.VeoGenerator", side_effect=RuntimeError("bad creds")):
            with pytest.raises(RuntimeError, match="bad creds"):
                Pipeline(dry_run=False)

    def test_raises_on_publisher_failure(self, mock_veo, mock_storage):
        with patch("pipeline.runner.TikTokPublisher", side_effect=RuntimeError("no token")):
            with pytest.raises(RuntimeError, match="no token"):
                Pipeline(dry_run=False)

    def test_publisher_failure_skipped_in_dry_run(self, mock_veo, mock_storage):
        with patch("pipeline.runner.TikTokPublisher", side_effect=RuntimeError("no token")):
            pipe = Pipeline(dry_run=True)
        assert pipe.publisher is None
