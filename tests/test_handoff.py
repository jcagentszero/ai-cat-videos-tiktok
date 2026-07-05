from pathlib import Path

import pytest

from pipeline import handoff
from prompts.script import parse_script


@pytest.fixture
def handoff_root(tmp_path, monkeypatch):
    from config import settings
    root = tmp_path / "handoff"
    monkeypatch.setattr(settings, "HANDOFF_DIR", root)
    return root


@pytest.fixture
def script(script_file):
    return parse_script(script_file)


@pytest.fixture
def photos(tmp_path):
    p = tmp_path / "nika1.jpg"
    p.write_bytes(b"\xff\xd8")
    return (p,)


class TestPrepareHandoff:
    def test_creates_pending_package(self, handoff_root, script, photos):
        dest = handoff.prepare_handoff(script, photos)
        assert dest == handoff_root / "pending" / script.id
        assert (dest / "script.txt").exists()
        assert (dest / f"{script.id}.md").exists()
        assert (dest / "nika1.jpg").exists()
        assert (dest / "INSTRUCTIONS.md").exists()

    def test_script_txt_is_rendered_with_persona(self, handoff_root, script, photos):
        from characters.persona import NIKA
        dest = handoff.prepare_handoff(script, photos)
        text = (dest / "script.txt").read_text()
        assert "[CAT]" not in text
        assert NIKA.description in text

    def test_duplicate_pending_raises(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        with pytest.raises(handoff.HandoffError, match=script.id):
            handoff.prepare_handoff(script, photos)


class TestPendingAndInbox:
    def test_list_pending_empty(self, handoff_root):
        assert handoff.list_pending() == ()

    def test_list_pending_sorted(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        assert handoff.list_pending() == (script.id,)

    def test_find_inbox_video_none(self, handoff_root, script):
        assert handoff.find_inbox_video(script.id) is None

    def test_find_inbox_video_found(self, handoff_root, script):
        inbox = handoff_root / "inbox"
        inbox.mkdir(parents=True)
        video = inbox / f"{script.id}.mp4"
        video.write_bytes(b"\x00")
        assert handoff.find_inbox_video(script.id) == video

    def test_load_pending_script_roundtrip(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        loaded = handoff.load_pending_script(script.id)
        assert loaded.id == script.id
        assert loaded.caption == script.caption

    def test_load_pending_unknown_raises(self, handoff_root):
        with pytest.raises(handoff.HandoffError, match="nope"):
            handoff.load_pending_script("nope")


class TestArchive:
    def test_archive_moves_pending_and_video(self, handoff_root, script, photos):
        handoff.prepare_handoff(script, photos)
        inbox = handoff_root / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        video = inbox / f"{script.id}.mp4"
        video.write_bytes(b"\x00")

        done = handoff.archive_handoff(script.id, video)

        assert done == handoff_root / "done" / script.id
        assert (done / f"{script.id}.mp4").exists()
        assert not (handoff_root / "pending" / script.id).exists()
        assert not video.exists()
        assert handoff.list_pending() == ()
