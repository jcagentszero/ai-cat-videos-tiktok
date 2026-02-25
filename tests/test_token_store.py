import json
import os
from unittest.mock import patch

import pytest

from config import settings
from publishers import token_store


class TestLoadTokens:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            assert token_store.load_tokens() == {}

    def test_loads_valid_token_file(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        expected = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "expires_at": "2025-01-01T00:00:00+00:00",
        }
        token_file.write_text(json.dumps(expected))
        with patch.object(settings, "TOKEN_FILE", token_file):
            assert token_store.load_tokens() == expected

    def test_loads_tokens_with_open_id(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        expected = {
            "access_token": "at_123",
            "refresh_token": "rt_456",
            "expires_at": "2025-01-01T00:00:00+00:00",
            "open_id": "oid_789",
        }
        token_file.write_text(json.dumps(expected))
        with patch.object(settings, "TOKEN_FILE", token_file):
            data = token_store.load_tokens()
        assert data["open_id"] == "oid_789"

    def test_returns_empty_dict_on_corrupt_json(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text("{bad json!!!")
        with patch.object(settings, "TOKEN_FILE", token_file):
            assert token_store.load_tokens() == {}

    def test_returns_empty_dict_on_read_error(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text("{}")
        os.chmod(token_file, 0o000)
        try:
            with patch.object(settings, "TOKEN_FILE", token_file):
                assert token_store.load_tokens() == {}
        finally:
            os.chmod(token_file, 0o644)


class TestSaveTokens:
    def test_creates_parent_directories(self, tmp_path):
        token_file = tmp_path / "nested" / "dir" / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at",
                refresh_token="rt",
                expires_at="2025-01-01T00:00:00",
            )
        assert token_file.exists()

    def test_writes_valid_json(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at_abc",
                refresh_token="rt_def",
                expires_at="2025-06-15T12:00:00+00:00",
            )
        data = json.loads(token_file.read_text())
        assert data["access_token"] == "at_abc"
        assert data["refresh_token"] == "rt_def"
        assert data["expires_at"] == "2025-06-15T12:00:00+00:00"

    def test_includes_open_id_when_provided(self, tmp_path):
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

    def test_omits_open_id_when_not_provided(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at",
                refresh_token="rt",
                expires_at="2025-01-01T00:00:00",
            )
        data = json.loads(token_file.read_text())
        assert "open_id" not in data

    def test_overwrites_existing_tokens(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({
            "access_token": "old_at",
            "refresh_token": "old_rt",
            "expires_at": "2024-01-01T00:00:00",
        }))
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="new_at",
                refresh_token="new_rt",
                expires_at="2025-01-01T00:00:00",
            )
        data = json.loads(token_file.read_text())
        assert data["access_token"] == "new_at"
        assert data["refresh_token"] == "new_rt"

    def test_raises_on_write_error(self, tmp_path):
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        token_file = read_only_dir / "tokens.json"
        os.chmod(read_only_dir, 0o444)
        try:
            with patch.object(settings, "TOKEN_FILE", token_file):
                with pytest.raises(OSError):
                    token_store.save_tokens(
                        access_token="at",
                        refresh_token="rt",
                        expires_at="2025-01-01T00:00:00",
                    )
        finally:
            os.chmod(read_only_dir, 0o755)


class TestRoundTrip:
    def test_save_then_load(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        with patch.object(settings, "TOKEN_FILE", token_file):
            token_store.save_tokens(
                access_token="at_round",
                refresh_token="rt_round",
                expires_at="2025-12-31T23:59:59+00:00",
                open_id="oid_round",
            )
            data = token_store.load_tokens()
        assert data["access_token"] == "at_round"
        assert data["refresh_token"] == "rt_round"
        assert data["expires_at"] == "2025-12-31T23:59:59+00:00"
        assert data["open_id"] == "oid_round"
