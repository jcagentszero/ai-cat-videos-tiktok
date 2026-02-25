import pytest
from pathlib import Path
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


class TestVeoDownloadVideo:
    @patch("generators.veo.gcs")
    def test_downloads_to_dest_path(
        self, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        _, creds = mock_credentials
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.GCP_PROJECT_ID", "my-project"):
            gen = VeoGenerator()

            dest = tmp_path / "output" / "video.mp4"
            mock_client = MagicMock()
            mock_gcs.Client.return_value = mock_client
            mock_blob = MagicMock()
            mock_client.bucket.return_value.blob.return_value = mock_blob

            def fake_download(path):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b"fake video data")
            mock_blob.download_to_filename.side_effect = fake_download

            result = gen._download_video("gs://my-bucket/path/to/video.mp4", dest)

            assert result == dest
            mock_gcs.Client.assert_called_once_with(
                credentials=creds,
                project="my-project",
            )
            mock_client.bucket.assert_called_once_with("my-bucket")
            mock_client.bucket.return_value.blob.assert_called_once_with("path/to/video.mp4")
            mock_blob.download_to_filename.assert_called_once_with(str(dest))

    @patch("generators.veo.gcs")
    def test_creates_parent_directories(
        self, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        dest = tmp_path / "deeply" / "nested" / "video.mp4"
        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob

        def fake_download(path):
            Path(path).write_bytes(b"data")
        mock_blob.download_to_filename.side_effect = fake_download

        gen._download_video("gs://bucket/obj/video.mp4", dest)

        assert dest.parent.exists()

    def test_raises_on_invalid_uri_no_gs_prefix(
        self, mock_credentials, mock_genai_client
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        with pytest.raises(ValueError, match="Invalid GCS URI"):
            gen._download_video(
                "https://storage.googleapis.com/bucket/vid.mp4",
                Path("/tmp/video.mp4"),
            )

    def test_raises_on_invalid_uri_bucket_only(
        self, mock_credentials, mock_genai_client
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        with pytest.raises(ValueError, match="Invalid GCS URI"):
            gen._download_video("gs://bucket-only", Path("/tmp/video.mp4"))

    def test_raises_on_empty_uri(
        self, mock_credentials, mock_genai_client
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        with pytest.raises(ValueError, match="Invalid GCS URI"):
            gen._download_video("gs://", Path("/tmp/video.mp4"))

    @patch("generators.veo.gcs")
    def test_raises_on_download_error(
        self, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob
        mock_blob.download_to_filename.side_effect = Exception("permission denied")

        dest = tmp_path / "video.mp4"
        with pytest.raises(Exception, match="permission denied"):
            gen._download_video("gs://bucket/path/video.mp4", dest)

    @patch("generators.veo.gcs")
    def test_returns_dest_path(
        self, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        dest = tmp_path / "video.mp4"
        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob

        def fake_download(path):
            Path(path).write_bytes(b"video bytes")
        mock_blob.download_to_filename.side_effect = fake_download

        result = gen._download_video("gs://bucket/output/vid.mp4", dest)

        assert result == dest
        assert result.exists()


class TestVeoGenerate:
    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_end_to_end_generate(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        _, client = mock_genai_client

        operation = MagicMock(done=True, error=None)
        operation.result.generated_videos = [MagicMock()]
        operation.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"
        client.models.generate_videos.return_value = operation

        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob

        def fake_download(path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"fake video")
        mock_blob.download_to_filename.side_effect = fake_download

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            result = gen.generate("a fluffy cat playing piano")

        assert result.exists()
        assert result.parent == tmp_path
        assert result.suffix == ".mp4"

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_submits_correct_config(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        _, client = mock_genai_client

        operation = MagicMock(done=True, error=None)
        operation.result.generated_videos = [MagicMock()]
        operation.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"
        client.models.generate_videos.return_value = operation

        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob
        mock_blob.download_to_filename.side_effect = lambda p: Path(p).write_bytes(b"v")

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path), \
             patch("config.settings.VEO_MODEL", "veo-3.0-generate-001"):
            gen = VeoGenerator()
            gen.generate("cat prompt", duration_seconds=6)

        call_kwargs = client.models.generate_videos.call_args
        assert call_kwargs.kwargs["model"] == "veo-3.0-generate-001"
        assert call_kwargs.kwargs["prompt"] == "cat prompt"
        config = call_kwargs.kwargs["config"]
        assert config.number_of_videos == 1
        assert config.duration_seconds == 6
        assert config.aspect_ratio == "9:16"
        assert config.generate_audio is True

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_raises_on_submit_error(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        _, client = mock_genai_client
        client.models.generate_videos.side_effect = RuntimeError("quota exceeded")

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            with pytest.raises(RuntimeError, match="quota exceeded"):
                gen.generate("cat prompt")

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_polls_and_downloads(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        mock_time.monotonic.side_effect = [0.0, 5.0, 15.0]
        _, client = mock_genai_client

        pending = MagicMock(done=False)
        done_op = MagicMock(done=True, error=None)
        done_op.result.generated_videos = [MagicMock()]
        done_op.result.generated_videos[0].video.uri = "gs://bucket/out/vid.mp4"
        client.models.generate_videos.return_value = pending
        client.operations.get.return_value = done_op

        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob
        mock_blob.download_to_filename.side_effect = lambda p: Path(p).write_bytes(b"v")

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            result = gen.generate("cat on skateboard")

        client.operations.get.assert_called_once()
        assert result.exists()

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_returns_path_in_output_dir(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        mock_time.monotonic.side_effect = [0.0, 1.0]
        _, client = mock_genai_client

        operation = MagicMock(done=True, error=None)
        operation.result.generated_videos = [MagicMock()]
        operation.result.generated_videos[0].video.uri = "gs://bucket/video.mp4"
        client.models.generate_videos.return_value = operation

        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob
        mock_blob.download_to_filename.side_effect = lambda p: Path(p).write_bytes(b"v")

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            result = gen.generate("prompt")

        assert str(result).startswith(str(tmp_path))
        assert "video_" in result.name

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_propagates_poll_timeout(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        mock_time.monotonic.side_effect = [0.0, 301.0]
        _, client = mock_genai_client

        pending = MagicMock(done=False)
        client.models.generate_videos.return_value = pending

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"), \
             patch("config.settings.OUTPUT_DIR", tmp_path):
            gen = VeoGenerator()
            with pytest.raises(TimeoutError):
                gen.generate("cat prompt")


class TestVeoRetry:
    @patch("generators.veo.time")
    def test_submit_retries_on_transient_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        _, client = mock_genai_client
        operation = MagicMock()
        client.models.generate_videos.side_effect = [
            ConnectionError("transient"),
            operation,
        ]

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        result = gen._submit_job("cat prompt", 8)
        assert result is operation
        assert client.models.generate_videos.call_count == 2

    @patch("generators.veo.time")
    def test_poll_once_retries_on_transient_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        _, client = mock_genai_client
        done_op = MagicMock()
        client.operations.get.side_effect = [
            ConnectionError("transient"),
            done_op,
        ]

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        result = gen._poll_once(MagicMock())
        assert result is done_op
        assert client.operations.get.call_count == 2

    @patch("generators.veo.gcs")
    @patch("generators.veo.time")
    def test_download_retries_on_transient_error(
        self, mock_time, mock_gcs, mock_credentials, mock_genai_client, tmp_path
    ):
        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        dest = tmp_path / "video.mp4"
        mock_blob = MagicMock()
        mock_gcs.Client.return_value.bucket.return_value.blob.return_value = mock_blob

        call_count = 0

        def flaky_download(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("transient network error")
            Path(path).write_bytes(b"video data")

        mock_blob.download_to_filename.side_effect = flaky_download

        result = gen._download_video("gs://bucket/path/video.mp4", dest)
        assert result == dest
        assert call_count == 2

    @patch("generators.veo.time")
    def test_no_retry_on_non_transient_error(
        self, mock_time, mock_credentials, mock_genai_client
    ):
        _, client = mock_genai_client
        client.models.generate_videos.side_effect = RuntimeError("quota exceeded")

        with patch("config.settings.GCP_CREDENTIALS", "/path/to/sa.json"):
            gen = VeoGenerator()

        with pytest.raises(RuntimeError, match="quota exceeded"):
            gen._submit_job("cat prompt", 8)
        assert client.models.generate_videos.call_count == 1
