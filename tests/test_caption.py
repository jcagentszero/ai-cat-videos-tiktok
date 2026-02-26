import pytest
from unittest.mock import patch, MagicMock

from generators.caption import generate_caption, SYSTEM_PROMPT


@pytest.fixture
def mock_api_key():
    with patch("generators.caption.settings.ANTHROPIC_API_KEY", "sk-test-key"):
        yield


@pytest.fixture
def mock_client(mock_api_key):
    client = MagicMock()
    block = MagicMock()
    block.text = "just a cat being a cat"
    client.messages.create.return_value = MagicMock(content=[block])
    with patch("generators.caption.anthropic.Anthropic", return_value=client) as cls:
        yield cls, client


class TestGenerateCaption:
    def test_returns_string(self, mock_client):
        result = generate_caption("A fluffy cat on a couch, warm light")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_llm_response(self, mock_client):
        _, client = mock_client
        block = MagicMock()
        block.text = "this cat is living the dream"
        client.messages.create.return_value = MagicMock(content=[block])
        result = generate_caption("A fluffy cat on a couch, warm light")
        assert result == "this cat is living the dream"

    def test_passes_prompt_to_llm(self, mock_client):
        _, client = mock_client
        generate_caption("A kitten chasing a feather toy")
        call_args = client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "A kitten chasing a feather toy" in user_msg

    def test_passes_category_to_llm(self, mock_client):
        _, client = mock_client
        generate_caption("A cozy cat prompt", category="cozy")
        call_args = client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "cozy" in user_msg

    def test_omits_category_when_none(self, mock_client):
        _, client = mock_client
        generate_caption("A cat on a couch")
        call_args = client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "Category/vibe" not in user_msg

    def test_uses_system_prompt(self, mock_client):
        _, client = mock_client
        generate_caption("A cat on a couch")
        call_args = client.messages.create.call_args
        assert call_args[1]["system"] == SYSTEM_PROMPT

    def test_uses_configured_model(self, mock_client):
        _, client = mock_client
        with patch("generators.caption.settings.CAPTION_MODEL", "claude-sonnet-4-6"):
            generate_caption("A cat on a couch")
        call_args = client.messages.create.call_args
        assert call_args[1]["model"] == "claude-sonnet-4-6"

    def test_strips_quotes_from_response(self, mock_client):
        _, client = mock_client
        block = MagicMock()
        block.text = '"when your cat finds the one sunbeam"'
        client.messages.create.return_value = MagicMock(content=[block])
        result = generate_caption("A cat in a sunbeam")
        assert not result.startswith('"')
        assert not result.endswith('"')

    def test_truncates_long_response(self, mock_client):
        _, client = mock_client
        block = MagicMock()
        block.text = "x" * 200
        client.messages.create.return_value = MagicMock(content=[block])
        result = generate_caption("A cat on a couch")
        assert len(result) <= 150
        assert result.endswith("...")

    def test_raises_when_no_api_key(self):
        with patch("generators.caption.settings.ANTHROPIC_API_KEY", ""):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not configured"):
                generate_caption("A cat on a couch")

    def test_raises_on_api_error(self, mock_api_key):
        import anthropic
        with patch("generators.caption.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = (
                anthropic.APIError(
                    message="rate limited",
                    request=MagicMock(),
                    body=None,
                )
            )
            with pytest.raises(RuntimeError, match="Caption LLM API error"):
                generate_caption("A cat on a couch")

    def test_creates_client_with_api_key(self, mock_client):
        cls, _ = mock_client
        generate_caption("A cat on a couch")
        cls.assert_called_once_with(api_key="sk-test-key")

    def test_max_tokens_is_100(self, mock_client):
        _, client = mock_client
        generate_caption("A cat on a couch")
        call_args = client.messages.create.call_args
        assert call_args[1]["max_tokens"] == 100
