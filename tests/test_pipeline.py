import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from pipeline.runner import Pipeline
from prompts.cat_prompts import ALL_PROMPTS, COZY, DRAMATIC, FUNNY, PLAYFUL


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


class TestSelectPrompt:
    @pytest.fixture
    def pipe(self, mock_veo, mock_tiktok, mock_storage):
        return Pipeline(dry_run=True)

    def test_returns_prompt_from_scheduled_category(self, pipe):
        pipe.storage.get_recent_prompts.return_value = []
        # Wednesday = weekday 2 = "dramatic"
        wed = datetime(2026, 2, 25, 12, 0)  # a Wednesday
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            prompt = pipe._select_prompt()
        assert prompt in DRAMATIC

    def test_excludes_recently_used_prompts(self, pipe):
        # Use all but one dramatic prompt as recent
        pipe.storage.get_recent_prompts.return_value = DRAMATIC[:2]
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            prompt = pipe._select_prompt()
        assert prompt == DRAMATIC[2]

    def test_falls_back_to_all_prompts_when_category_exhausted(self, pipe):
        # All dramatic prompts used recently
        pipe.storage.get_recent_prompts.return_value = list(DRAMATIC)
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            prompt = pipe._select_prompt()
        assert prompt in ALL_PROMPTS
        assert prompt not in DRAMATIC

    def test_reuses_from_category_when_all_prompts_exhausted(self, pipe):
        pipe.storage.get_recent_prompts.return_value = list(ALL_PROMPTS)
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            prompt = pipe._select_prompt()
        assert prompt in DRAMATIC

    def test_uses_correct_category_for_monday(self, pipe):
        pipe.storage.get_recent_prompts.return_value = []
        mon = datetime(2026, 2, 23, 12, 0)  # a Monday
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = mon
            prompt = pipe._select_prompt()
        assert prompt in COZY

    def test_uses_correct_category_for_tuesday(self, pipe):
        pipe.storage.get_recent_prompts.return_value = []
        tue = datetime(2026, 2, 24, 12, 0)  # a Tuesday
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = tue
            prompt = pipe._select_prompt()
        assert prompt in PLAYFUL

    def test_calls_get_recent_prompts(self, pipe):
        pipe.storage.get_recent_prompts.return_value = []
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            pipe._select_prompt()
        pipe.storage.get_recent_prompts.assert_called_once()

    def test_always_returns_a_string(self, pipe):
        pipe.storage.get_recent_prompts.return_value = []
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            result = pipe._select_prompt()
        assert isinstance(result, str)
        assert len(result) > 0


class TestBuildCaption:
    @pytest.fixture
    def pipe(self, mock_veo, mock_tiktok, mock_storage):
        return Pipeline(dry_run=True)

    def test_caption_is_first_clause_of_prompt(self, pipe):
        prompt = COZY[0]
        caption, _ = pipe._build_caption(prompt)
        expected = prompt.split(",")[0].strip()
        assert caption == expected

    def test_returns_hashtag_list(self, pipe):
        caption, hashtags = pipe._build_caption(COZY[0])
        assert isinstance(hashtags, list)
        assert len(hashtags) > 0
        assert all(isinstance(h, str) for h in hashtags)

    def test_base_hashtags_always_present(self, pipe):
        _, hashtags = pipe._build_caption(COZY[0])
        for tag in Pipeline.BASE_HASHTAGS:
            assert tag in hashtags

    def test_cozy_prompt_gets_cozy_hashtags(self, pipe):
        _, hashtags = pipe._build_caption(COZY[0])
        for tag in Pipeline.CATEGORY_HASHTAGS["cozy"]:
            assert tag in hashtags

    def test_funny_prompt_gets_funny_hashtags(self, pipe):
        _, hashtags = pipe._build_caption(FUNNY[0])
        for tag in Pipeline.CATEGORY_HASHTAGS["funny"]:
            assert tag in hashtags

    def test_unknown_prompt_gets_only_base_hashtags(self, pipe):
        _, hashtags = pipe._build_caption("A totally custom prompt, not in any list")
        assert hashtags == list(Pipeline.BASE_HASHTAGS)

    def test_hashtags_do_not_contain_hash_symbol(self, pipe):
        _, hashtags = pipe._build_caption(COZY[0])
        for tag in hashtags:
            assert not tag.startswith("#")

    def test_returns_tuple(self, pipe):
        result = pipe._build_caption(DRAMATIC[0])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_caption_is_nonempty_string(self, pipe):
        caption, _ = pipe._build_caption(PLAYFUL[0])
        assert isinstance(caption, str)
        assert len(caption) > 0
