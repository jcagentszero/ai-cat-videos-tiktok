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

    def test_missing_gcp_project_raises(self):
        with _patch_vars(GCP_PROJECT_ID=""):
            with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT_ID"):
                validate_config()

    def test_missing_gcp_credentials_raises(self):
        with _patch_vars(GCP_CREDENTIALS=""):
            with pytest.raises(ValueError, match="GOOGLE_APPLICATION_CREDENTIALS"):
                validate_config()

    def test_missing_tiktok_key_raises(self):
        with _patch_vars(TIKTOK_CLIENT_KEY=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_KEY"):
                validate_config()

    def test_missing_tiktok_secret_raises(self):
        with _patch_vars(TIKTOK_CLIENT_SECRET=""):
            with pytest.raises(ValueError, match="TIKTOK_CLIENT_SECRET"):
                validate_config()

    def test_multiple_missing_lists_all(self):
        with _patch_vars(GCP_PROJECT_ID="", TIKTOK_CLIENT_KEY=""):
            with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT_ID.*TIKTOK_CLIENT_KEY"):
                validate_config()

    def test_missing_gcp_in_dry_run_still_raises(self):
        with _patch_vars(GCP_PROJECT_ID=""):
            with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT_ID"):
                validate_config(dry_run=True)

    def test_error_message_mentions_env_file(self):
        with _patch_vars(GCP_PROJECT_ID=""):
            with pytest.raises(ValueError, match=r"\.env"):
                validate_config()
