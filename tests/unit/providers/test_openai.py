"""Unit tests for OpenAI providers."""

from unittest.mock import MagicMock, patch

import pytest

from docgen.exceptions.errors import EmbeddingError, LLMError
from docgen.providers.openai import OpenAIEmbeddingProvider, OpenAIProvider


class TestOpenAIProvider:
    """Test cases for OpenAIProvider."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        with patch("docgen.providers.openai.ChatOpenAI"):
            provider = OpenAIProvider(api_key="test-key")
            assert provider.model_name == OpenAIProvider.DEFAULT_MODEL

    def test_custom_model(self):
        """Test that custom model is used when specified."""
        with patch("docgen.providers.openai.ChatOpenAI"):
            provider = OpenAIProvider(api_key="test-key", model="gpt-4-turbo")
            assert provider.model_name == "gpt-4-turbo"

    def test_custom_temperature(self):
        """Test that custom temperature is used."""
        with patch("docgen.providers.openai.ChatOpenAI"):
            provider = OpenAIProvider(api_key="test-key", temperature=0.8)
            assert provider.temperature == 0.8

    def test_create_llm_success(self):
        """Test successful LLM creation."""
        mock_llm = MagicMock()
        with patch(
            "docgen.providers.openai.ChatOpenAI", return_value=mock_llm
        ) as mock_chat:
            provider = OpenAIProvider(api_key="test-key")
            llm = provider.get_langchain_llm()

            mock_chat.assert_called_once_with(
                api_key="test-key",
                model=OpenAIProvider.DEFAULT_MODEL,
            )
            assert llm is mock_llm

    def test_create_llm_with_temperature(self):
        """Test that an explicit temperature is passed through."""
        mock_llm = MagicMock()
        with patch(
            "docgen.providers.openai.ChatOpenAI", return_value=mock_llm
        ) as mock_chat:
            provider = OpenAIProvider(api_key="test-key", temperature=0.2)
            provider.get_langchain_llm()

            mock_chat.assert_called_once_with(
                api_key="test-key",
                model=OpenAIProvider.DEFAULT_MODEL,
                temperature=0.2,
            )

    def test_create_llm_failure(self):
        """Test LLM creation failure raises LLMError."""
        with patch(
            "docgen.providers.openai.ChatOpenAI", side_effect=Exception("API error")
        ):
            provider = OpenAIProvider.__new__(OpenAIProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._temperature = 0.2
            provider._llm = None

            with pytest.raises(LLMError, match="Failed to create OpenAI LLM"):
                provider.get_langchain_llm()


class TestOpenAIEmbeddingProvider:
    """Test cases for OpenAIEmbeddingProvider."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        with patch("docgen.providers.openai.OpenAIEmbeddings"):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            assert provider.model_name == OpenAIEmbeddingProvider.DEFAULT_MODEL

    def test_custom_model(self):
        """Test that custom model is used when specified."""
        with patch("docgen.providers.openai.OpenAIEmbeddings"):
            provider = OpenAIEmbeddingProvider(
                api_key="test-key", model="text-embedding-ada-002"
            )
            assert provider.model_name == "text-embedding-ada-002"

    def test_create_embeddings_success(self):
        """Test successful embeddings creation."""
        mock_emb = MagicMock()
        with patch(
            "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_emb
        ) as mock_class:
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            emb = provider.get_langchain_embeddings()

            mock_class.assert_called_once_with(
                api_key="test-key",
                model=OpenAIEmbeddingProvider.DEFAULT_MODEL,
            )
            assert emb is mock_emb

    def test_create_embeddings_failure(self):
        """Test embeddings creation failure raises EmbeddingError."""
        with patch(
            "docgen.providers.openai.OpenAIEmbeddings",
            side_effect=Exception("API error"),
        ):
            provider = OpenAIEmbeddingProvider.__new__(OpenAIEmbeddingProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._embeddings = None

            with pytest.raises(
                EmbeddingError, match="Failed to create OpenAI embeddings"
            ):
                provider.get_langchain_embeddings()


def test_openaiprovider_passes_max_tokens():
    """The output token limit reaches the LangChain chat model."""
    provider = OpenAIProvider(api_key="test-key", max_tokens=8192)

    assert provider.get_langchain_llm().max_tokens == 8192
