import pytest
from unittest.mock import patch, MagicMock

from pipeline.analytics_collector import collect_analytics


@pytest.fixture
def mock_storage():
    mgr = MagicMock()
    mgr.get_runs_needing_analytics.return_value = []
    with patch("pipeline.analytics_collector.StorageManager", return_value=mgr):
        yield mgr


def _make_run(publish_id, video_id, timestamp="2026-02-23T10:00:00"):
    return {
        "timestamp": timestamp,
        "prompt": "cat sleeping",
        "video_path": "/fake/video.mp4",
        "result": {
            "status": "published",
            "publish_result": {
                "publish_id": publish_id,
                "video_id": video_id,
            },
        },
    }


class TestCollectAnalyticsNoRuns:
    def test_returns_zero_when_no_runs(self, mock_storage):
        with patch("pipeline.analytics_collector.TikTokPublisher"):
            result = collect_analytics(storage=mock_storage)
        assert result == {"collected": 0, "failed": 0}

    def test_does_not_create_publisher_when_no_runs(self, mock_storage):
        with patch("pipeline.analytics_collector.TikTokPublisher") as mock_cls:
            collect_analytics(storage=mock_storage)
        mock_cls.assert_not_called()


class TestCollectAnalyticsWithRuns:
    @pytest.fixture(autouse=True)
    def setup_publisher(self):
        self.mock_pub = MagicMock()
        self.mock_pub.refresh_token.return_value = "new_token"
        self.mock_pub.fetch_video_analytics.return_value = {
            "vid_1": {
                "view_count": 500,
                "like_count": 50,
                "comment_count": 5,
                "share_count": 2,
            },
        }
        with patch("pipeline.analytics_collector.TikTokPublisher",
                   return_value=self.mock_pub):
            yield

    def test_fetches_analytics_for_published_runs(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
        ]
        mock_storage.update_run_analytics.return_value = True
        result = collect_analytics(storage=mock_storage)
        assert result["collected"] == 1
        assert result["failed"] == 0

    def test_refreshes_token(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
        ]
        mock_storage.update_run_analytics.return_value = True
        collect_analytics(storage=mock_storage)
        self.mock_pub.refresh_token.assert_called_once()
        assert self.mock_pub.access_token == "new_token"

    def test_passes_video_ids_to_publisher(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
            _make_run("pub_2", "vid_2"),
        ]
        self.mock_pub.fetch_video_analytics.return_value = {}
        mock_storage.update_run_analytics.return_value = True
        collect_analytics(storage=mock_storage)
        call_args = self.mock_pub.fetch_video_analytics.call_args[0][0]
        assert set(call_args) == {"vid_1", "vid_2"}

    def test_updates_run_history(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
        ]
        mock_storage.update_run_analytics.return_value = True
        collect_analytics(storage=mock_storage)
        mock_storage.update_run_analytics.assert_called_once_with(
            "pub_1",
            {
                "view_count": 500,
                "like_count": 50,
                "comment_count": 5,
                "share_count": 2,
            },
        )

    def test_counts_failed_updates(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
        ]
        mock_storage.update_run_analytics.return_value = False
        result = collect_analytics(storage=mock_storage)
        assert result["collected"] == 0
        assert result["failed"] == 1

    def test_counts_not_found_videos(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
            _make_run("pub_2", "vid_2"),
        ]
        self.mock_pub.fetch_video_analytics.return_value = {
            "vid_1": {"view_count": 100, "like_count": 10,
                      "comment_count": 1, "share_count": 0},
        }
        mock_storage.update_run_analytics.return_value = True
        result = collect_analytics(storage=mock_storage)
        assert result["collected"] == 1
        assert result["failed"] == 1

    def test_handles_api_error(self, mock_storage):
        mock_storage.get_runs_needing_analytics.return_value = [
            _make_run("pub_1", "vid_1"),
        ]
        self.mock_pub.fetch_video_analytics.side_effect = RuntimeError("API down")
        result = collect_analytics(storage=mock_storage)
        assert result["collected"] == 0
        assert result["failed"] == 1

    def test_uses_configured_delay(self, mock_storage):
        with patch("pipeline.analytics_collector.settings") as mock_settings:
            mock_settings.ANALYTICS_DELAY_HOURS = 48
            collect_analytics(storage=mock_storage)
        mock_storage.get_runs_needing_analytics.assert_called_once_with(delay_hours=48)

    def test_creates_storage_when_none(self, mock_storage):
        with patch("pipeline.analytics_collector.StorageManager",
                   return_value=mock_storage) as cls:
            collect_analytics()
        cls.assert_called_once()
