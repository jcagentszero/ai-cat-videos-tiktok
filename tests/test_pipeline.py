from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.runner import Pipeline
from prompts.script import parse_script


@pytest.fixture
def sample_script(script_file):
    return parse_script(script_file)


@pytest.fixture
def mock_scripts(sample_script):
    mgr = MagicMock()
    mgr.consume_script.return_value = sample_script
    mgr.peek_script.return_value = sample_script
    with patch("pipeline.runner.ScriptManager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_handoff(sample_script):
    with patch("pipeline.runner.prepare_handoff",
               return_value=Path("/tmp/handoff/pending/x")) as prep, \
         patch("pipeline.runner.list_pending",
               return_value=(sample_script.id,)) as pending, \
         patch("pipeline.runner.find_inbox_video",
               return_value=Path("/tmp/handoff/inbox/x.mp4")) as find, \
         patch("pipeline.runner.load_pending_script",
               return_value=sample_script) as load, \
         patch("pipeline.runner.archive_handoff") as archive:
        yield {"prepare": prep, "pending": pending, "find": find,
               "load": load, "archive": archive}


@pytest.fixture
def mock_photos():
    with patch("pipeline.runner.load_reference_photos",
               return_value=(Path("/tmp/nika.jpg"),)):
        yield


@pytest.fixture
def mock_tiktok():
    pub = MagicMock()
    pub.publish.return_value = {"publish_id": "pub_1"}
    with patch("pipeline.runner.TikTokPublisher", return_value=pub):
        yield pub


@pytest.fixture
def mock_storage():
    mgr = MagicMock()
    with patch("pipeline.runner.StorageManager", return_value=mgr):
        yield mgr


@pytest.fixture
def mock_validate():
    with patch("pipeline.runner.validate_video") as v:
        yield v


@pytest.fixture
def mock_clipper():
    client = MagicMock()
    client.upload_video.return_value = "up_1"
    client.create_clip_project.return_value = "P123"
    from clippers.opusclip import Clip
    client.get_clips.return_value = (
        Clip(id="c1", video_url="https://cdn/c1.mp4", title="Funny 1", raw={}),
    )
    client.download.side_effect = lambda url, dest: dest
    with patch("pipeline.runner.OpusClipClient", return_value=client):
        yield client


@pytest.fixture
def overlapping_script(script_file, tmp_path):
    """Script whose hashtags collide with BASE_HASHTAGS and NIKA.hashtags.

    'catvideos' is already in Pipeline.BASE_HASHTAGS and 'nikathecat' is
    already in NIKA.hashtags — only 'bellyrubtrapz' is unique to the script.
    """
    text = script_file.read_text().replace(
        "  - bellyrub\n  - cattrap",
        "  - catvideos\n  - nikathecat\n  - bellyrubtrapz",
    )
    path = tmp_path / "overlap.md"
    path.write_text(text)
    return parse_script(path)


ALL = ("mock_scripts", "mock_handoff", "mock_photos",
       "mock_tiktok", "mock_storage", "mock_validate", "mock_clipper")


@pytest.mark.usefixtures(*ALL)
class TestPrepare:
    def test_consumes_and_stages(self, mock_scripts, mock_handoff, mock_storage):
        result = Pipeline(dry_run=False).prepare()
        mock_scripts.consume_script.assert_called_once_with(None)
        mock_handoff["prepare"].assert_called_once()
        assert result["status"] == "prepared"
        assert result["script_id"] == "belly-rub-betrayal"
        mock_storage.save_run.assert_called_once()

    def test_dry_run_peeks(self, mock_scripts):
        Pipeline(dry_run=True).prepare()
        mock_scripts.peek_script.assert_called_once_with(None)
        mock_scripts.consume_script.assert_not_called()

    def test_script_id_forwarded(self, mock_scripts):
        Pipeline(dry_run=False).prepare(script_id="belly-rub-betrayal")
        mock_scripts.consume_script.assert_called_once_with("belly-rub-betrayal")


@pytest.mark.usefixtures(*ALL)
class TestPublishInbox:
    def test_publishes_ready_video(self, mock_handoff, mock_tiktok, mock_storage,
                                   sample_script):
        results = Pipeline(dry_run=False).publish_inbox()
        assert len(results) == 1
        r = results[0]
        assert r["status"] == "published"
        assert r["script_id"] == sample_script.id
        assert r["prompt"] == sample_script.title
        mock_tiktok.publish.assert_called_once()
        mock_handoff["archive"].assert_called_once()
        mock_storage.save_run.assert_called_once()

    def test_caption_from_script(self, mock_tiktok):
        Pipeline(dry_run=False).publish_inbox()
        _, caption, hashtags = mock_tiktok.publish.call_args[0]
        assert caption == "The belly was never an offer. It was a test."
        assert len(hashtags) == len(set(hashtags))

    def test_skips_when_no_inbox_video(self, mock_handoff, mock_tiktok):
        mock_handoff["find"].return_value = None
        results = Pipeline(dry_run=False).publish_inbox()
        assert results == []
        mock_tiktok.publish.assert_not_called()

    def test_dry_run_does_not_publish_or_archive(self, mock_handoff, mock_tiktok):
        results = Pipeline(dry_run=True).publish_inbox()
        assert results[0]["status"] == "dry_run"
        mock_tiktok.publish.assert_not_called()
        mock_handoff["archive"].assert_not_called()

    def test_validation_failure_recorded(self, mock_validate, mock_storage):
        mock_validate.side_effect = RuntimeError("bad video")
        with pytest.raises(RuntimeError):
            Pipeline(dry_run=False).publish_inbox()
        fail = mock_storage.save_run.call_args[0][2]
        assert fail["status"] == "failed"

    def test_hashtags_deduped_base_first(self, mock_handoff, mock_tiktok,
                                         overlapping_script):
        # Adversarial dedup: the script re-declares 'catvideos' (BASE) and
        # 'nikathecat' (NIKA) — naive concat would duplicate them, and an
        # unordered dedup (set) would scramble the base-first ordering.
        mock_handoff["load"].return_value = overlapping_script
        Pipeline(dry_run=False).publish_inbox()
        _, _, hashtags = mock_tiktok.publish.call_args[0]

        assert len(hashtags) == len(set(hashtags)), "duplicates survived dedup"
        # dict.fromkeys keeps the FIRST occurrence: duplicates re-declared by
        # the script stay at their base/persona position, and only the tag
        # unique to the script lands at the end.
        assert hashtags == [
            # BASE_HASHTAGS, in declaration order
            "catvideos", "catsoftiktok", "aiart", "aigenerated",
            # NIKA.hashtags, in declaration order
            "nikathecat", "grumpybutsweet", "exoticshorthair", "grumpycat2",
            # only the script-unique tag remains from the script's list
            "bellyrubtrapz",
        ]
        assert (hashtags.index("catvideos")
                < hashtags.index("nikathecat")
                < hashtags.index("bellyrubtrapz"))


@pytest.mark.usefixtures(*ALL)
class TestClipFootage:
    def test_full_clip_flow(self, mock_clipper, mock_storage, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        with patch("pipeline.runner.time.sleep"):
            result = Pipeline(dry_run=False).clip_footage(video)
        mock_clipper.upload_video.assert_called_once_with(video)
        mock_clipper.create_clip_project.assert_called_once()
        assert result["project_id"] == "P123"
        assert result["status"] == "clipped"
        assert len(result["clips"]) == 1

    def test_polls_until_clips_appear(self, mock_clipper, tmp_path):
        from clippers.opusclip import Clip
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        mock_clipper.get_clips.side_effect = [
            (), (),
            (Clip(id="c1", video_url="https://cdn/c1.mp4", title="t", raw={}),),
        ]
        with patch("pipeline.runner.time.sleep"):
            Pipeline(dry_run=False).clip_footage(video)
        assert mock_clipper.get_clips.call_count == 3

    def test_timeout_raises(self, mock_clipper, tmp_path):
        video = tmp_path / "raw.mp4"
        video.write_bytes(b"\x00")
        mock_clipper.get_clips.return_value = ()
        fake_clock = iter(range(0, 100000, 600))
        with patch("pipeline.runner.time.sleep"), \
             patch("pipeline.runner.time.monotonic",
                   side_effect=lambda: next(fake_clock)):
            with pytest.raises(TimeoutError):
                Pipeline(dry_run=False).clip_footage(video)


@pytest.mark.usefixtures(*ALL)
class TestRunDaily:
    def test_publishes_then_prepares_when_empty(self, mock_handoff, mock_scripts):
        # after publishing, nothing pending → prepare next
        mock_handoff["pending"].side_effect = [(mock_scripts.consume_script.return_value.id,), ()]
        result = Pipeline(dry_run=False).run()
        assert result["status"] == "ok"
        assert result["prepared"] is not None

    def test_no_prepare_while_pending(self, mock_handoff, mock_scripts):
        mock_handoff["find"].return_value = None      # video not dropped yet
        result = Pipeline(dry_run=False).run()
        assert result["prepared"] is None
        mock_scripts.consume_script.assert_not_called()


@pytest.mark.usefixtures(*ALL)
class TestSaveFailure:
    def test_failure_record_has_script_id_and_error(self, mock_validate,
                                                    mock_storage, sample_script):
        mock_validate.side_effect = RuntimeError("bad video")
        with pytest.raises(RuntimeError):
            Pipeline(dry_run=False).publish_inbox()
        fail = mock_storage.save_run.call_args[0][2]
        assert fail["status"] == "failed"
        assert fail["script_id"] == sample_script.id
        assert fail["error"] == "RuntimeError: bad video"

    def test_storage_error_swallowed_original_raised(self, mock_validate,
                                                     mock_storage):
        # If save_run itself blows up while recording the failure, the
        # ORIGINAL error must still be the one that propagates.
        mock_validate.side_effect = RuntimeError("bad video")
        mock_storage.save_run.side_effect = OSError("disk full")
        with pytest.raises(RuntimeError, match="bad video"):
            Pipeline(dry_run=False).publish_inbox()


@pytest.mark.usefixtures(*ALL)
class TestHandleError:
    def test_no_email_when_notify_unset(self):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", ""), \
             patch("pipeline.runner.smtplib.SMTP") as smtp_cls:
            Pipeline(dry_run=True)._handle_error("prepare", RuntimeError("boom"))
        smtp_cls.assert_not_called()

    def test_email_sent_when_notify_set(self):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "ops@example.com"), \
             patch("pipeline.runner.smtplib.SMTP") as smtp_cls:
            Pipeline(dry_run=True)._handle_error(
                "publish_inbox", RuntimeError("boom"),
            )
        smtp_cls.assert_called_once_with("localhost")
        sent = smtp_cls.return_value.__enter__.return_value \
            .send_message.call_args[0][0]
        assert "publish_inbox" in sent["Subject"]
        assert sent["To"] == "ops@example.com"

    def test_smtp_failure_swallowed(self):
        with patch("pipeline.runner.settings.NOTIFY_EMAIL", "ops@example.com"), \
             patch("pipeline.runner.smtplib.SMTP",
                   side_effect=OSError("smtp down")):
            # must not raise despite the notification failure
            Pipeline(dry_run=True)._handle_error("prepare", RuntimeError("boom"))
