import pytest
from unittest.mock import patch, MagicMock, call

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


class TestVeoPollJob:
    @patch("generators.veo.time")
    def test_returns_uri_on_immediate_completion(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        operation = MagicMock(done=True, error=None)
        operation.result.generated_videos = [MagicMock()]
        operation.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"

        result = gen._poll_job(operation)

        assert result == "gs://bucket/video.mp4"
        mock_time.sleep.assert_not_called()

    @patch("generators.veo.time")
    def test_polls_until_done(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 5.0, 15.0]
        _, client = mock_genai_client
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        pending = MagicMock(done=False)
        done_op = MagicMock(done=True, error=None)
        done_op.result.generated_videos = [MagicMock()]
        done_op.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"
        client.operations.get.return_value = done_op

        result = gen._poll_job(pending)

        assert result == "gs://bucket/video.mp4"
        client.operations.get.assert_called_once()
        mock_time.sleep.assert_called_once_with(10)

    @patch("generators.veo.time")
    def test_exponential_backoff(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 5.0, 15.0, 30.0]
        _, client = mock_genai_client
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        pending = MagicMock(done=False)
        still_pending = MagicMock(done=False)
        done_op = MagicMock(done=True, error=None)
        done_op.result.generated_videos = [MagicMock()]
        done_op.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"
        client.operations.get.side_effect = [still_pending, done_op]

        gen._poll_job(pending)

        assert mock_time.sleep.call_args_list == [call(10), call(15.0)]

    @patch("generators.veo.time")
    def test_raises_timeout_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 301.0]
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        pending = MagicMock(done=False)

        with pytest.raises(TimeoutError, match="timed out after 300s"):
            gen._poll_job(pending, timeout=300)

    @patch("generators.veo.time")
    def test_raises_on_operation_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        error = MagicMock()
        error.message = "content policy violation"
        operation = MagicMock(done=True, error=error)

        with pytest.raises(RuntimeError, match="content policy violation"):
            gen._poll_job(operation)

    @patch("generators.veo.time")
    def test_raises_on_empty_videos(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        operation = MagicMock(done=True, error=None)
        operation.result.generated_videos = []

        with pytest.raises(RuntimeError, match="no videos were generated"):
            gen._poll_job(operation)

    @patch("generators.veo.time")
    def test_raises_on_poll_api_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        mock_time.monotonic.side_effect = [0.0, 5.0]
        _, client = mock_genai_client
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        pending = MagicMock(done=False)
        client.operations.get.side_effect = ConnectionError("network error")

        with pytest.raises(ConnectionError, match="network error"):
            gen._poll_job(pending)
