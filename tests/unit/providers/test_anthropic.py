"""Unit tests for Anthropic provider."""

from unittest.mock import MagicMock, patch

from docgen.providers.anthropic import AnthropicProvider


class TestAnthropicProvider:
    """Test cases for AnthropicProvider."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        with patch("docgen.providers.anthropic.ChatAnthropic"):
            provider = AnthropicProvider(api_key="test-key")
            assert provider.model_name == AnthropicProvider.DEFAULT_MODEL

    def test_custom_model(self):
        """Test that custom model is used when specified."""
        with patch("docgen.providers.anthropic.ChatAnthropic"):
            provider = AnthropicProvider(
                api_key="test-key", model="claude-3-opus-20240229"
            )
            assert provider.model_name == "claude-3-opus-20240229"

    def test_custom_temperature(self):
        """Test that custom temperature is used."""
        with patch("docgen.providers.anthropic.ChatAnthropic"):
            provider = AnthropicProvider(api_key="test-key", temperature=0.7)
            assert provider.temperature == 0.7

    def test_create_llm_success(self):
        """Test successful LLM creation omits temperature by default."""
        mock_llm = MagicMock()
        with patch(
            "docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm
        ) as mock_chat:
            provider = AnthropicProvider(api_key="test-key")
            llm = provider.get_langchain_llm()

            mock_chat.assert_called_once_with(
                api_key="test-key",
                model=AnthropicProvider.DEFAULT_MODEL,
            )
            assert llm is mock_llm

    def test_create_llm_with_temperature(self):
        """Test that an explicit temperature is passed through."""
        mock_llm = MagicMock()
        with patch(
            "docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm
        ) as mock_chat:
            provider = AnthropicProvider(api_key="test-key", temperature=0.2)
            provider.get_langchain_llm()

            mock_chat.assert_called_once_with(
                api_key="test-key",
                model=AnthropicProvider.DEFAULT_MODEL,
                temperature=0.2,
            )


def test_anthropicprovider_passes_max_tokens():
    """The output token limit reaches the LangChain chat model."""
    provider = AnthropicProvider(api_key="test-key", max_tokens=8192)

    assert provider.get_langchain_llm().max_tokens == 8192
