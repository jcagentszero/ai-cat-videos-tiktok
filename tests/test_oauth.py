import json
import threading
import urllib.request
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

import pytest

from config import settings
from publishers import oauth, token_store


def _patch_settings(**overrides):
    defaults = {
        "TIKTOK_CLIENT_KEY": "test_key",
        "TIKTOK_CLIENT_SECRET": "test_secret",
    }
    defaults.update(overrides)
    return patch.multiple(settings, **defaults)


class TestBuildAuthUrl:
    def test_url_starts_with_tiktok_auth(self):
        with _patch_settings():
            url = oauth.build_auth_url("abc123")
        assert url.startswith(oauth.AUTH_URL)

    def test_contains_client_key(self):
        with _patch_settings():
            url = oauth.build_auth_url("abc123")
        params = parse_qs(urlparse(url).query)
        assert params["client_key"] == ["test_key"]

    def test_contains_scopes(self):
        with _patch_settings():
            url = oauth.build_auth_url("abc123")
        params = parse_qs(urlparse(url).query)
        assert params["scope"] == [oauth.SCOPES]

    def test_contains_state(self):
        with _patch_settings():
            url = oauth.build_auth_url("my_state_value")
        params = parse_qs(urlparse(url).query)
        assert params["state"] == ["my_state_value"]

    def test_response_type_is_code(self):
        with _patch_settings():
            url = oauth.build_auth_url("abc123")
        params = parse_qs(urlparse(url).query)
        assert params["response_type"] == ["code"]

    def test_redirect_uri_is_localhost(self):
        with _patch_settings():
            url = oauth.build_auth_url("abc123")
        params = parse_qs(urlparse(url).query)
        redirect = params["redirect_uri"][0]
        assert redirect.startswith("http://localhost:")
        assert "/callback" in redirect


class TestExchangeCode:
    def test_sends_correct_payload(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "open_id": "oid_789",
            "expires_in": 86400,
        }
        mock_resp.raise_for_status = MagicMock()

        with _patch_settings(), \
             patch("publishers.oauth.requests.post", return_value=mock_resp) as mock_post:
            oauth.exchange_code("auth_code_abc")

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert payload["client_key"] == "test_key"
        assert payload["client_secret"] == "test_secret"
        assert payload["code"] == "auth_code_abc"
        assert payload["grant_type"] == "authorization_code"

    def test_returns_token_data(self):
        expected = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "open_id": "oid_789",
            "expires_in": 86400,
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = expected
        mock_resp.raise_for_status = MagicMock()

        with _patch_settings(), \
             patch("publishers.oauth.requests.post", return_value=mock_resp):
            result = oauth.exchange_code("auth_code_abc")

        assert result == expected

    def test_raises_on_api_error(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Code has expired",
        }
        mock_resp.raise_for_status = MagicMock()

        with _patch_settings(), \
             patch("publishers.oauth.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Code has expired"):
                oauth.exchange_code("expired_code")

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with _patch_settings(), \
             patch("publishers.oauth.requests.post", return_value=mock_resp):
            with pytest.raises(Exception, match="500 Server Error"):
                oauth.exchange_code("any_code")


class TestCallbackHandler:
    def _start_server(self):
        from http.server import HTTPServer
        server = HTTPServer(
            (oauth.REDIRECT_HOST, 0), oauth._CallbackHandler,
        )
        server.callback_params = {}
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, port, thread

    def test_captures_code_and_state(self):
        server, port, thread = self._start_server()
        try:
            url = f"http://localhost:{port}/callback?code=abc&state=xyz"
            urllib.request.urlopen(url, timeout=5)
            thread.join(timeout=5)
            assert server.callback_params["code"] == ["abc"]
            assert server.callback_params["state"] == ["xyz"]
        finally:
            server.shutdown()
            server.server_close()

    def test_captures_error(self):
        server, port, thread = self._start_server()
        try:
            url = (
                f"http://localhost:{port}/callback"
                f"?error=access_denied&error_description=User+cancelled"
            )
            urllib.request.urlopen(url, timeout=5)
            thread.join(timeout=5)
            assert server.callback_params["error"] == ["access_denied"]
        finally:
            server.shutdown()
            server.server_close()

    def test_404_for_wrong_path(self):
        server, port, thread = self._start_server()
        try:
            url = f"http://localhost:{port}/wrong"
            with pytest.raises(Exception):
                urllib.request.urlopen(url, timeout=5)
            assert server.callback_params == {}
        finally:
            server.shutdown()
            server.server_close()


class TestRunOauthFlow:
    def test_missing_client_key_raises(self):
        with _patch_settings(TIKTOK_CLIENT_KEY=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_KEY"):
                oauth.run_oauth_flow()

    def test_missing_client_secret_raises(self):
        with _patch_settings(TIKTOK_CLIENT_SECRET=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_SECRET"):
                oauth.run_oauth_flow()

    def test_full_flow_success(self, tmp_path):
        token_file = tmp_path / "tokens.json"

        token_response = {
            "access_token": "at_live",
            "refresh_token": "rt_live",
            "open_id": "oid_live",
            "expires_in": 86400,
        }

        def fake_server_init(self, addr, handler):
            self._addr = addr
            self.callback_params = {}

        def fake_serve_forever(self):
            pass

        def fake_server_close(self):
            pass

        def fake_shutdown(self):
            pass

        captured_state = {}

        original_build = oauth.build_auth_url

        def capture_state_build(state):
            captured_state["state"] = state
            return original_build(state)

        def fake_join(self, timeout=None):
            self.server = MagicMock()
            pass

        def fake_thread_is_alive(self):
            return False

        with _patch_settings(), \
             patch.object(settings, "TOKEN_FILE", token_file), \
             patch("publishers.oauth.build_auth_url", side_effect=capture_state_build), \
             patch("publishers.oauth.webbrowser.open"), \
             patch("publishers.oauth.exchange_code", return_value=token_response), \
             patch("publishers.oauth.HTTPServer") as mock_server_cls, \
             patch("publishers.oauth.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server.callback_params = {}
            mock_server_cls.return_value = mock_server

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_thread_cls.return_value = mock_thread

            def set_params_on_join(timeout=None):
                state = captured_state.get("state", "")
                mock_server.callback_params = {
                    "code": ["auth_code_123"],
                    "state": [state],
                }

            mock_thread.join.side_effect = set_params_on_join

            result = oauth.run_oauth_flow()

        assert result["access_token"] == "at_live"
        assert result["refresh_token"] == "rt_live"
        assert result["open_id"] == "oid_live"
        assert result["expires_in"] == 86400

        saved = json.loads(token_file.read_text())
        assert saved["access_token"] == "at_live"
        assert saved["refresh_token"] == "rt_live"
        assert saved["open_id"] == "oid_live"
        assert "expires_at" in saved

    def test_state_mismatch_raises(self):
        with _patch_settings(), \
             patch("publishers.oauth.webbrowser.open"), \
             patch("publishers.oauth.HTTPServer") as mock_server_cls, \
             patch("publishers.oauth.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server.callback_params = {}
            mock_server_cls.return_value = mock_server

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_thread_cls.return_value = mock_thread

            def set_wrong_state(timeout=None):
                mock_server.callback_params = {
                    "code": ["auth_code_123"],
                    "state": ["wrong_state"],
                }

            mock_thread.join.side_effect = set_wrong_state

            with pytest.raises(RuntimeError, match="state mismatch"):
                oauth.run_oauth_flow()

    def test_authorization_denied_raises(self):
        with _patch_settings(), \
             patch("publishers.oauth.webbrowser.open"), \
             patch("publishers.oauth.HTTPServer") as mock_server_cls, \
             patch("publishers.oauth.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server.callback_params = {}
            mock_server_cls.return_value = mock_server

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_thread_cls.return_value = mock_thread

            def set_error(timeout=None):
                mock_server.callback_params = {
                    "error": ["access_denied"],
                    "error_description": ["User cancelled"],
                }

            mock_thread.join.side_effect = set_error

            with pytest.raises(RuntimeError, match="Authorization denied"):
                oauth.run_oauth_flow()

    def test_timeout_raises(self):
        with _patch_settings(), \
             patch("publishers.oauth.webbrowser.open"), \
             patch("publishers.oauth.HTTPServer") as mock_server_cls, \
             patch("publishers.oauth.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server.callback_params = {}
            mock_server_cls.return_value = mock_server

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            mock_thread_cls.return_value = mock_thread

            with pytest.raises(TimeoutError, match="not received within"):
                oauth.run_oauth_flow()

    def test_no_code_in_callback_raises(self):
        with _patch_settings(), \
             patch("publishers.oauth.webbrowser.open"), \
             patch("publishers.oauth.HTTPServer") as mock_server_cls, \
             patch("publishers.oauth.threading.Thread") as mock_thread_cls:

            mock_server = MagicMock()
            mock_server.callback_params = {}
            mock_server_cls.return_value = mock_server

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_thread_cls.return_value = mock_thread

            mock_thread.join.side_effect = lambda timeout=None: None

            with pytest.raises(RuntimeError, match="No authorization code"):
                oauth.run_oauth_flow()


class TestTokenStoreOpenId:
    def test_save_with_open_id(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at",
                refresh_token="rt",
                expires_at="2025-01-01T00:00:00",
                open_id="oid_123",
            )
        data = json.loads(token_file.read_text())
        assert data["open_id"] == "oid_123"

    def test_save_without_open_id(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at",
                refresh_token="rt",
                expires_at="2025-01-01T00:00:00",
            )
        data = json.loads(token_file.read_text())
        assert "open_id" not in data

    def test_load_includes_open_id(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "at",
            "refresh_token": "rt",
            "expires_at": "2025-01-01T00:00:00",
            "open_id": "oid_loaded",
        }))
        with patch.object(settings, "TOKEN_FILE", token_file):
            data = token_store.load_tokens()
        assert data["open_id"] == "oid_loaded"
