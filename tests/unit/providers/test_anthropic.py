"""Unit tests for Anthropic provider."""

from unittest.mock import MagicMock, patch

import pytest

from docgen.exceptions.errors import LLMError
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

    def test_create_llm_failure(self):
        """Test LLM creation failure raises LLMError."""
        with patch(
            "docgen.providers.anthropic.ChatAnthropic",
            side_effect=Exception("API error"),
        ):
            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._temperature = 0.2
            provider._llm = None

            with pytest.raises(LLMError, match="Failed to create Anthropic LLM"):
                provider.get_langchain_llm()

    def test_invoke_success(self):
        """Test successful invocation."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "Generated response"

        with patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm):
            provider = AnthropicProvider(api_key="test-key")
            result = provider.invoke("Test prompt")

            mock_llm.invoke.assert_called_once_with("Test prompt")
            assert result == "Generated response"

    def test_invoke_failure(self):
        """Test invocation failure raises LLMError."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API error")

        with patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm):
            provider = AnthropicProvider(api_key="test-key")

            with pytest.raises(LLMError, match="Failed to invoke Anthropic LLM"):
                provider.invoke("Test prompt")
