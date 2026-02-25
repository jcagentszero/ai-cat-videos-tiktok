import pytest
from datetime import datetime
from pathlib import Path
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


class TestPipelineRun:
    @pytest.fixture
    def pipe(self, mock_veo, mock_tiktok, mock_storage):
        _, gen = mock_veo
        gen.generate.return_value = Path("/fake/output/video_20260224_001.mp4")
        _, pub = mock_tiktok
        pub.publish.return_value = {
            "publish_id": "pub123",
            "status": "PUBLISH_COMPLETE",
            "video_path": "/fake/output/video_20260224_001.mp4",
        }
        pipe = Pipeline(dry_run=False)
        pipe.storage.get_recent_prompts.return_value = []
        return pipe

    @pytest.fixture
    def dry_pipe(self, mock_veo, mock_tiktok, mock_storage):
        _, gen = mock_veo
        gen.generate.return_value = Path("/fake/output/video_20260224_001.mp4")
        pipe = Pipeline(dry_run=True)
        pipe.storage.get_recent_prompts.return_value = []
        return pipe

    def test_returns_dict(self, dry_pipe):
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            result = dry_pipe.run()
        assert isinstance(result, dict)

    def test_result_contains_required_keys(self, dry_pipe):
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            result = dry_pipe.run()
        for key in ("prompt", "video_path", "caption", "hashtags",
                    "publish_result", "status"):
            assert key in result

    def test_uses_provided_prompt(self, dry_pipe):
        result = dry_pipe.run(prompt="A custom cat prompt")
        assert result["prompt"] == "A custom cat prompt"

    def test_selects_prompt_when_none_given(self, dry_pipe):
        wed = datetime(2026, 2, 25, 12, 0)
        with patch("pipeline.runner.datetime") as mock_dt:
            mock_dt.now.return_value = wed
            result = dry_pipe.run()
        assert result["prompt"] in DRAMATIC

    def test_calls_generator(self, dry_pipe):
        dry_pipe.run(prompt="A cat on a couch")
        dry_pipe.generator.generate.assert_called_once_with("A cat on a couch")

    def test_video_path_in_result(self, dry_pipe):
        result = dry_pipe.run(prompt="A cat on a couch")
        assert result["video_path"] == "/fake/output/video_20260224_001.mp4"

    def test_dry_run_skips_publish(self, dry_pipe):
        result = dry_pipe.run(prompt="A cat on a couch")
        assert result["status"] == "dry_run"
        assert result["publish_result"] is None

    def test_dry_run_logs_what_would_have_been_posted(self, dry_pipe):
        with patch("pipeline.runner.logger") as mock_logger:
            dry_pipe.run(prompt="A fluffy cat, sitting on a ledge")
        info_calls = [c for c in mock_logger.info.call_args_list
                      if "DRY_RUN" in str(c)]
        assert len(info_calls) == 1
        call_args = info_calls[0][0]
        assert "would have posted" in call_args[0]
        assert str(dry_pipe.generator.generate.return_value) in str(call_args[1])
        assert "A fluffy cat" in call_args[2]
        assert isinstance(call_args[3], list)

    def test_publishes_when_not_dry_run(self, pipe):
        result = pipe.run(prompt="A cat on a couch")
        assert result["status"] == "published"
        pipe.publisher.publish.assert_called_once()

    def test_publish_receives_caption_and_hashtags(self, pipe):
        pipe.run(prompt="A cat on a couch")
        args = pipe.publisher.publish.call_args
        assert args[0][0] == Path("/fake/output/video_20260224_001.mp4")
        assert isinstance(args[0][1], str)   # caption
        assert isinstance(args[0][2], list)  # hashtags

    def test_publish_result_in_output(self, pipe):
        result = pipe.run(prompt="A cat on a couch")
        assert result["publish_result"]["publish_id"] == "pub123"

    def test_saves_run_record(self, dry_pipe):
        dry_pipe.run(prompt="A cat on a couch")
        dry_pipe.storage.save_run.assert_called_once()
        args = dry_pipe.storage.save_run.call_args[0]
        assert args[0] == "A cat on a couch"
        assert args[1] == Path("/fake/output/video_20260224_001.mp4")
        assert isinstance(args[2], dict)

    def test_generate_error_calls_handle_error_and_raises(self, dry_pipe):
        dry_pipe.generator.generate.side_effect = RuntimeError("veo down")
        with patch.object(dry_pipe, "_handle_error") as mock_handle:
            with pytest.raises(RuntimeError, match="veo down"):
                dry_pipe.run(prompt="A cat on a couch")
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][0] == "generate"

    def test_publish_error_calls_handle_error_and_raises(self, pipe):
        pipe.publisher.publish.side_effect = RuntimeError("upload failed")
        with patch.object(pipe, "_handle_error") as mock_handle:
            with pytest.raises(RuntimeError, match="upload failed"):
                pipe.run(prompt="A cat on a couch")
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][0] == "publish"

    def test_save_run_error_calls_handle_error_and_raises(self, dry_pipe):
        dry_pipe.storage.save_run.side_effect = OSError("disk full")
        with patch.object(dry_pipe, "_handle_error") as mock_handle:
            with pytest.raises(OSError, match="disk full"):
                dry_pipe.run(prompt="A cat on a couch")
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][0] == "save_run"

    def test_caption_in_result(self, dry_pipe):
        result = dry_pipe.run(prompt="A fluffy cat, sitting on a ledge")
        assert result["caption"] == "A fluffy cat"

    def test_hashtags_in_result(self, dry_pipe):
        result = dry_pipe.run(prompt="A cat on a couch")
        assert isinstance(result["hashtags"], list)
        assert len(result["hashtags"]) > 0


class TestHandleError:
    @pytest.fixture
    def pipe(self, mock_veo, mock_tiktok, mock_storage):
        return Pipeline(dry_run=True)

    def test_does_not_raise(self, pipe):
        pipe._handle_error("generate", ValueError("bad prompt"))

    def test_logs_error_with_step_and_type(self, pipe):
        err = RuntimeError("connection lost")
        with patch("pipeline.runner.logger") as mock_logger:
            pipe._handle_error("publish", err)
        mock_logger.error.assert_called_once()
        args = mock_logger.error.call_args
        assert "publish" in args[0][1]
        assert "RuntimeError" in args[0][2]

    def test_logs_debug_traceback(self, pipe):
        try:
            raise ValueError("test error")
        except ValueError as err:
            with patch("pipeline.runner.logger") as mock_logger:
                pipe._handle_error("generate", err)
        mock_logger.debug.assert_called_once()
        tb_str = mock_logger.debug.call_args[0][2]
        assert "ValueError" in tb_str
        assert "test error" in tb_str

    def test_skips_email_when_not_configured(self, pipe):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", ""):
            with patch("pipeline.runner.smtplib") as mock_smtp:
                pipe._handle_error("generate", ValueError("x"))
        mock_smtp.SMTP.assert_not_called()

    def test_sends_email_when_configured(self, pipe):
        mock_smtp_instance = MagicMock()
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.runner.smtplib.SMTP") as mock_smtp_cls:
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                pipe._handle_error("publish", RuntimeError("upload failed"))
        mock_smtp_instance.send_message.assert_called_once()
        msg = mock_smtp_instance.send_message.call_args[0][0]
        assert msg["To"] == "user@example.com"
        assert "publish" in msg["Subject"]

    def test_email_contains_error_details(self, pipe):
        mock_smtp_instance = MagicMock()
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.runner.smtplib.SMTP") as mock_smtp_cls:
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                pipe._handle_error("generate", ValueError("bad input"))
        msg = mock_smtp_instance.send_message.call_args[0][0]
        body = msg.get_content()
        assert "generate" in body
        assert "ValueError" in body
        assert "bad input" in body

    def test_email_failure_does_not_raise(self, pipe):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.runner.smtplib.SMTP", side_effect=ConnectionRefusedError("no smtp")):
                pipe._handle_error("publish", RuntimeError("fail"))

    def test_email_failure_logs_warning(self, pipe):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "user@example.com"):
            with patch("pipeline.runner.smtplib.SMTP", side_effect=ConnectionRefusedError("no smtp")):
                with patch("pipeline.runner.logger") as mock_logger:
                    pipe._handle_error("publish", RuntimeError("fail"))
        mock_logger.warning.assert_called_once()
        assert "notification" in mock_logger.warning.call_args[0][0].lower()


class TestSaveFailure:
    @pytest.fixture
    def pipe(self, mock_veo, mock_tiktok, mock_storage):
        return Pipeline(dry_run=True)

    def test_saves_failure_record(self, pipe):
        pipe._save_failure("test prompt", Path("/fake/video.mp4"), RuntimeError("boom"))
        pipe.storage.save_run.assert_called_once()
        args = pipe.storage.save_run.call_args[0]
        assert args[0] == "test prompt"
        assert args[1] == Path("/fake/video.mp4")
        assert args[2]["status"] == "failed"
        assert "RuntimeError: boom" in args[2]["error"]

    def test_uses_unknown_prompt_when_none(self, pipe):
        pipe._save_failure(None, None, ValueError("no prompt"))
        args = pipe.storage.save_run.call_args[0]
        assert args[0] == "unknown"

    def test_handles_none_video_path(self, pipe):
        pipe._save_failure("a prompt", None, RuntimeError("fail"))
        args = pipe.storage.save_run.call_args[0]
        assert args[2]["video_path"] is None

    def test_save_error_does_not_raise(self, pipe):
        pipe.storage.save_run.side_effect = OSError("disk full")
        pipe._save_failure("p", None, RuntimeError("fail"))  # should not raise

    def test_generate_failure_saves_record(self, mock_veo, mock_tiktok, mock_storage):
        _, gen = mock_veo
        gen.generate.side_effect = RuntimeError("veo down")
        pipe = Pipeline(dry_run=True)
        pipe.storage.get_recent_prompts.return_value = []
        with pytest.raises(RuntimeError, match="veo down"):
            pipe.run(prompt="A cat on a couch")
        save_calls = [
            c for c in pipe.storage.save_run.call_args_list
            if c[0][2].get("status") == "failed"
        ]
        assert len(save_calls) == 1
        assert "RuntimeError" in save_calls[0][0][2]["error"]

    def test_publish_failure_saves_record(self, mock_veo, mock_tiktok, mock_storage):
        _, gen = mock_veo
        gen.generate.return_value = Path("/fake/video.mp4")
        _, pub = mock_tiktok
        pub.publish.side_effect = RuntimeError("upload failed")
        pipe = Pipeline(dry_run=False)
        with pytest.raises(RuntimeError, match="upload failed"):
            pipe.run(prompt="A cat on a couch")
        save_calls = [
            c for c in pipe.storage.save_run.call_args_list
            if c[0][2].get("status") == "failed"
        ]
        assert len(save_calls) == 1
        assert save_calls[0][0][2]["video_path"] == "/fake/video.mp4"
