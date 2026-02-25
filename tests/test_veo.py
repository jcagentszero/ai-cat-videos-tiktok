import pytest
from unittest.mock import patch, MagicMock

from generators.veo import VeoGenerator


@pytest.fixture
def mock_credentials():
    creds = MagicMock()
    with patch(
        "generators.veo.service_account.Credentials.from_service_account_file",
        return_value=creds,
    ) as mock_load:
        yield mock_load, creds


@pytest.fixture
def mock_genai_client():
    client = MagicMock()
    with patch("generators.veo.genai.Client", return_value=client) as mock_cls:
        yield mock_cls, client


class TestVeoGeneratorInit:
    def test_loads_credentials_from_settings(self, mock_credentials, mock_genai_client):
        mock_load, _ = mock_credentials
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            VeoGenerator()
        mock_load.assert_called_once_with("/path/to/sa.json")

    def test_creates_client_with_vertexai(self, mock_credentials, mock_genai_client):
        _, creds = mock_credentials
        mock_cls, _ = mock_genai_client
        with patch("config.settings.GCP_PROJECT_ID", "my-project"), \
             patch("config.settings.VEO_REGION", "us-central1"), \
             patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            VeoGenerator()
        mock_cls.assert_called_once_with(
            vertexai=True,
            project="my-project",
            location="us-central1",
            credentials=creds,
        )

    def test_stores_model_from_settings(self, mock_credentials, mock_genai_client):
        with patch("config.settings.VEO_MODEL", "veo-3.0-generate-001"), \
             patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()
        assert gen.model == "veo-3.0-generate-001"

    def test_stores_client_on_instance(self, mock_credentials, mock_genai_client):
        _, client = mock_genai_client
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()
        assert gen.client is client

    def test_raises_on_invalid_credentials_file(self):
        with patch(
            "generators.veo.service_account.Credentials.from_service_account_file",
            side_effect=FileNotFoundError("no such file"),
        ):
            with pytest.raises(FileNotFoundError):
                VeoGenerator()

    def test_raises_on_client_error(self, mock_credentials):
        with patch(
            "generators.veo.genai.Client",
            side_effect=RuntimeError("auth failed"),
        ), patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            with pytest.raises(RuntimeError, match="auth failed"):
                VeoGenerator()
