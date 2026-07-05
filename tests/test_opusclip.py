from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clippers.opusclip import (
    CLIP_PROJECTS_PATH,
    EXPORTABLE_CLIPS_PATH,
    UPLOAD_LINKS_PATH,
    Clip,
    OpusClipClient,
    OpusClipError,
    OpusClipTransientError,
)


def _make_client(org_id="org_test"):
    return OpusClipClient(api_key="ok_test", base_url="https://api.test/api",
                          org_id=org_id)


def _mock_response(status=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    resp.headers = headers or {}
    resp.text = str(json_data)
    return resp


class TestInit:
    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="AGENT_OPUS_API_KEY"):
            OpusClipClient(api_key="")

    def test_org_header_set_when_provided(self):
        client = _make_client(org_id="org_9")
        assert client._session.headers["x-opus-org-id"] == "org_9"

    def test_org_header_absent_when_empty(self):
        client = _make_client(org_id="")
        assert "x-opus-org-id" not in client._session.headers


class TestUploadVideo:
    def test_three_step_upload(self, tmp_path):
        video = tmp_path / "nika.mp4"
        video.write_bytes(b"\x00" * 128)
        client = _make_client()
        link_resp = _mock_response(200, {"url": "https://gcs.test/up", "uploadId": "up_1"})
        init_resp = _mock_response(201, headers={"location": "https://gcs.test/resume"})
        put_resp = _mock_response(200)
        with patch.object(client._session, "request", return_value=link_resp) as api, \
             patch("clippers.opusclip.requests.post", return_value=init_resp) as init, \
             patch("clippers.opusclip.requests.put", return_value=put_resp) as put:
            upload_id = client.upload_video(video)

        assert upload_id == "up_1"
        method, url = api.call_args[0]
        assert (method, url) == ("POST", f"https://api.test/api{UPLOAD_LINKS_PATH}")
        assert api.call_args[1]["json"] == {"video": {"usecase": "LocalUpload"}}
        assert init.call_args[0][0] == "https://gcs.test/up"
        assert init.call_args[1]["headers"]["x-goog-resumable"] == "start"
        assert put.call_args[0][0] == "https://gcs.test/resume"

    def test_missing_location_header_raises(self, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")
        client = _make_client()
        link_resp = _mock_response(200, {"url": "https://gcs.test/up", "uploadId": "up_1"})
        init_resp = _mock_response(201, headers={})
        with patch.object(client._session, "request", return_value=link_resp), \
             patch("clippers.opusclip.requests.post", return_value=init_resp):
            with pytest.raises(OpusClipError, match="location"):
                client.upload_video(video)

    def test_missing_upload_id_raises(self, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, {"url": "x"})):
            with pytest.raises(OpusClipError, match="uploadId"):
                client.upload_video(video)


class TestCreateClipProject:
    def test_posts_payload_returns_project_id(self):
        client = _make_client()
        resp = _mock_response(201, {"projectId": "P123"})
        with patch.object(client._session, "request", return_value=resp) as req:
            pid = client.create_clip_project(
                "up_1", topic_keywords=("cat",), clip_durations=((0, 60),),
            )
        assert pid == "P123"
        payload = req.call_args[1]["json"]
        assert payload["videoUrl"] == "up_1"
        assert payload["curationPref"]["topicKeywords"] == ["cat"]
        assert payload["curationPref"]["clipDurations"] == [[0, 60]]
        assert payload["importPref"] == {"sourceLang": "auto"}

    def test_missing_project_id_raises(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(201, {})):
            with pytest.raises(OpusClipError, match="project"):
                client.create_clip_project("up_1")


class TestGetClips:
    def test_maps_clip_fields_defensively(self):
        client = _make_client()
        items = [
            {"id": "c1", "videoUrl": "https://cdn/c1.mp4", "title": "Funny 1"},
            {"clipId": "c2", "downloadUrl": "https://cdn/c2.mp4", "caption": "Funny 2"},
        ]
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, items)) as req:
            clips = client.get_clips("P123")
        assert clips[0] == Clip(id="c1", video_url="https://cdn/c1.mp4",
                                title="Funny 1", raw=items[0])
        assert clips[1].id == "c2"
        assert clips[1].video_url == "https://cdn/c2.mp4"
        assert clips[1].title == "Funny 2"
        _, url = req.call_args[0]
        assert url == (f"https://api.test/api{EXPORTABLE_CLIPS_PATH}"
                       "?q=findByProjectId&projectId=P123")

    def test_empty_list(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(200, [])):
            assert client.get_clips("P123") == ()


class TestErrors:
    def test_429_is_transient_and_retried(self):
        client = _make_client()
        responses = [_mock_response(429, {}), _mock_response(200, [])]
        with patch.object(client._session, "request", side_effect=responses), \
             patch("time.sleep"):
            assert client.get_clips("P1") == ()

    def test_4xx_raises_non_transient(self):
        client = _make_client()
        with patch.object(client._session, "request",
                          return_value=_mock_response(403, {})):
            with pytest.raises(OpusClipError) as exc:
                client.get_clips("P1")
            assert not isinstance(exc.value, OpusClipTransientError)


class TestDownload:
    def test_streams_to_dest(self, tmp_path):
        client = _make_client()
        resp = _mock_response(200)
        resp.iter_content.return_value = [b"a", b"b"]
        dest = tmp_path / "out" / "c.mp4"
        with patch.object(client._session, "request", return_value=resp):
            assert client.download("https://cdn/c.mp4", dest) == dest
        assert dest.read_bytes() == b"ab"
