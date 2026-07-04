import pytest
from unittest.mock import patch

from config import settings
from config.settings import validate_config


def _patch_vars(**overrides):
    defaults = {
        "GCP_PROJECT_ID": "test-project",
        "GCP_CREDENTIALS": "/path/to/creds.json",
        "TIKTOK_CLIENT_KEY": "key123",
        "TIKTOK_CLIENT_SECRET": "secret456",
        "OPUS_API_KEY": "ok_test",
    }
    defaults.update(overrides)
    return patch.multiple(settings, **defaults)


class TestValidateConfig:
    def test_all_vars_set_passes(self):
        with _patch_vars():
            validate_config()

    def test_dry_run_skips_tiktok_vars(self):
        with _patch_vars(TIKTOK_CLIENT_KEY="", TIKTOK_CLIENT_SECRET=""):
            validate_config(dry_run=True)

    def test_missing_tiktok_key_raises(self):
        with _patch_vars(TIKTOK_CLIENT_KEY=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_KEY"):
                validate_config()

    def test_missing_tiktok_secret_raises(self):
        with _patch_vars(TIKTOK_CLIENT_SECRET=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_SECRET"):
                validate_config()

    def test_multiple_missing_lists_all(self):
        with _patch_vars(OPUS_API_KEY="", TIKTOK_CLIENT_KEY=""):
            with pytest.raises(ValueError, match="OPUS_API_KEY.*TIKTOK_CLIENT_KEY"):
                validate_config()

    def test_error_message_mentions_env_file(self):
        with _patch_vars(OPUS_API_KEY=""):
            with pytest.raises(ValueError, match=r"\.env"):
                validate_config()


class TestValidateConfigOpus:
    def test_missing_opus_key_raises(self):
        with _patch_vars(OPUS_API_KEY=""):
            with pytest.raises(ValueError, match="OPUS_API_KEY"):
                validate_config()

    def test_gcp_vars_no_longer_required(self):
        with _patch_vars(GCP_PROJECT_ID="", GCP_CREDENTIALS=""):
            validate_config()

    def test_dry_run_still_requires_opus_key(self):
        with _patch_vars(OPUS_API_KEY=""):
            with pytest.raises(ValueError, match="OPUS_API_KEY"):
                validate_config(dry_run=True)


class TestNewSettings:
    def test_reference_photos_dir_under_root(self):
        assert settings.ROOT_DIR in settings.REFERENCE_PHOTOS_DIR.parents

    def test_opus_reference_asset_ids_is_tuple(self):
        assert isinstance(settings.OPUS_REFERENCE_ASSET_IDS, tuple)

    def test_opus_api_base_default(self):
        assert settings.OPUS_API_BASE.startswith("https://")
