import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
import requests as requests_lib

from config import settings
from publishers.tiktok import TikTokPublisher, REFRESH_BUFFER_SECONDS, TOKEN_URL


def _make_publisher():
    return object.__new__(TikTokPublisher)


def _future_expiry(seconds=3600):
    return (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).isoformat()


def _past_expiry():
    return (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    ).isoformat()


def _near_expiry():
    return (
        datetime.now(timezone.utc)
        + timedelta(seconds=REFRESH_BUFFER_SECONDS - 10)
    ).isoformat()


def _mock_refresh_response(**overrides):
    defaults = {
        "access_token": "at_new",
        "refresh_token": "rt_new",
        "expires_in": 86400,
    }
    defaults.update(overrides)
    resp = MagicMock()
    resp.json.return_value = defaults
    resp.raise_for_status = MagicMock()
    return resp


def _patch_settings():
    return patch.multiple(
        settings,
        TIKTOK_CLIENT_KEY="test_ck",
        TIKTOK_CLIENT_SECRET="test_cs",
    )


class TestRefreshTokenSkip:
    def test_skips_refresh_when_token_still_valid(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_valid",
            "refresh_token": "rt_valid",
            "expires_at": _future_expiry(3600),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file):
            result = pub.refresh_token()

        assert result == "at_valid"

    def test_skips_refresh_at_exact_buffer_boundary(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        expires = (
            datetime.now(timezone.utc)
            + timedelta(seconds=REFRESH_BUFFER_SECONDS + 60)
        ).isoformat()
        token_file.write_text(json.dumps({
            "access_token": "at_boundary",
            "refresh_token": "rt_boundary",
            "expires_at": expires,
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file):
            result = pub.refresh_token()

        assert result == "at_boundary"


class TestRefreshTokenExecutes:
    def test_refreshes_when_token_expired(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response()):
            result = pub.refresh_token()

        assert result == "at_new"

    def test_refreshes_when_near_expiry(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_expiring",
            "refresh_token": "rt_expiring",
            "expires_at": _near_expiry(),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response(
                       access_token="at_refreshed",
                   )):
            result = pub.refresh_token()

        assert result == "at_refreshed"

    def test_refreshes_when_expires_at_missing(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_no_expiry",
            "refresh_token": "rt_no_expiry",
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response(
                       access_token="at_fresh",
                   )):
            result = pub.refresh_token()

        assert result == "at_fresh"

    def test_refreshes_when_expires_at_unparseable(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_bad_ts",
            "refresh_token": "rt_bad_ts",
            "expires_at": "not-a-date",
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response(
                       access_token="at_forced",
                   )):
            result = pub.refresh_token()

        assert result == "at_forced"


class TestRefreshTokenPersistence:
    def test_persists_new_tokens(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response(
                       access_token="at_persisted",
                       refresh_token="rt_persisted",
                       open_id="oid_persisted",
                   )):
            pub.refresh_token()

        saved = json.loads(token_file.read_text())
        assert saved["access_token"] == "at_persisted"
        assert saved["refresh_token"] == "rt_persisted"
        assert saved["open_id"] == "oid_persisted"
        assert "expires_at" in saved

    def test_preserves_stored_open_id_when_not_in_response(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
            "open_id": "oid_stored",
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response()):
            pub.refresh_token()

        saved = json.loads(token_file.read_text())
        assert saved["open_id"] == "oid_stored"


class TestRefreshTokenPayload:
    def test_sends_correct_payload(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_payload_test",
            "expires_at": _past_expiry(),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=_mock_refresh_response()) as mock_post:
            pub.refresh_token()

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == TOKEN_URL
        payload = call_args.kwargs.get("data") or call_args[1].get("data")
        assert payload["client_key"] == "test_ck"
        assert payload["client_secret"] == "test_cs"
        assert payload["grant_type"] == "refresh_token"
        assert payload["refresh_token"] == "rt_payload_test"


class TestRefreshTokenErrors:
    def test_raises_when_no_refresh_token_in_store(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({"access_token": "at_only"}))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file):
            with pytest.raises(RuntimeError, match="No refresh token"):
                pub.refresh_token()

    def test_raises_when_token_store_empty(self, tmp_path):
        token_file = tmp_path / "tokens.json"

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file):
            with pytest.raises(RuntimeError, match="No refresh token"):
                pub.refresh_token()

    def test_raises_on_http_error(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
        }))

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests_lib.HTTPError(
            "500 Server Error"
        )

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=mock_resp):
            with pytest.raises(RuntimeError, match="request failed"):
                pub.refresh_token()

    def test_raises_on_connection_error(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
        }))

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   side_effect=requests_lib.ConnectionError(
                       "Connection refused"
                   )):
            with pytest.raises(RuntimeError, match="request failed"):
                pub.refresh_token()

    def test_raises_on_api_error_response(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at_old",
            "refresh_token": "rt_old",
            "expires_at": _past_expiry(),
        }))

        resp = MagicMock()
        resp.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token expired",
        }
        resp.raise_for_status = MagicMock()

        pub = _make_publisher()
        with patch.object(settings, "TOKEN_FILE", token_file), \
             _patch_settings(), \
             patch("publishers.tiktok.requests.post",
                   return_value=resp):
            with pytest.raises(RuntimeError, match="Refresh token expired"):
                pub.refresh_token()
