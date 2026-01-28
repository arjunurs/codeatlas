"""Unit tests for OpenAI providers."""

import pytest
from unittest.mock import MagicMock, patch

from docgen.providers.openai import OpenAIProvider, OpenAIEmbeddingProvider
from docgen.exceptions.errors import LLMError, EmbeddingError


class TestOpenAIProvider:
    """Test cases for OpenAIProvider."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        with patch('docgen.providers.openai.ChatOpenAI') as mock_chat:
            provider = OpenAIProvider(api_key="test-key")
            assert provider.model_name == OpenAIProvider.DEFAULT_MODEL

    def test_custom_model(self):
        """Test that custom model is used when specified."""
        with patch('docgen.providers.openai.ChatOpenAI') as mock_chat:
            provider = OpenAIProvider(api_key="test-key", model="gpt-4-turbo")
            assert provider.model_name == "gpt-4-turbo"

    def test_custom_temperature(self):
        """Test that custom temperature is used."""
        with patch('docgen.providers.openai.ChatOpenAI') as mock_chat:
            provider = OpenAIProvider(api_key="test-key", temperature=0.8)
            assert provider.temperature == 0.8

    def test_create_llm_success(self):
        """Test successful LLM creation."""
        mock_llm = MagicMock()
        with patch('docgen.providers.openai.ChatOpenAI', return_value=mock_llm) as mock_chat:
            provider = OpenAIProvider(api_key="test-key")
            llm = provider.get_langchain_llm()

            mock_chat.assert_called_once_with(
                api_key="test-key",
                model=OpenAIProvider.DEFAULT_MODEL,
                temperature=0.2,
            )
            assert llm is mock_llm

    def test_create_llm_failure(self):
        """Test LLM creation failure raises LLMError."""
        with patch('docgen.providers.openai.ChatOpenAI', side_effect=Exception("API error")):
            provider = OpenAIProvider.__new__(OpenAIProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._temperature = 0.2
            provider._llm = None

            with pytest.raises(LLMError, match="Failed to create OpenAI LLM"):
                provider.get_langchain_llm()

    def test_invoke_success(self):
        """Test successful invocation."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "Generated response"

        with patch('docgen.providers.openai.ChatOpenAI', return_value=mock_llm):
            provider = OpenAIProvider(api_key="test-key")
            result = provider.invoke("Test prompt")

            mock_llm.invoke.assert_called_once_with("Test prompt")
            assert result == "Generated response"

    def test_invoke_failure(self):
        """Test invocation failure raises LLMError."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API error")

        with patch('docgen.providers.openai.ChatOpenAI', return_value=mock_llm):
            provider = OpenAIProvider(api_key="test-key")

            with pytest.raises(LLMError, match="Failed to invoke OpenAI LLM"):
                provider.invoke("Test prompt")


class TestOpenAIEmbeddingProvider:
    """Test cases for OpenAIEmbeddingProvider."""

    def test_default_model(self):
        """Test that default model is used when not specified."""
        with patch('docgen.providers.openai.OpenAIEmbeddings') as mock_emb:
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            assert provider.model_name == OpenAIEmbeddingProvider.DEFAULT_MODEL

    def test_custom_model(self):
        """Test that custom model is used when specified."""
        with patch('docgen.providers.openai.OpenAIEmbeddings') as mock_emb:
            provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-ada-002")
            assert provider.model_name == "text-embedding-ada-002"

    def test_create_embeddings_success(self):
        """Test successful embeddings creation."""
        mock_emb = MagicMock()
        with patch('docgen.providers.openai.OpenAIEmbeddings', return_value=mock_emb) as mock_class:
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            emb = provider.get_langchain_embeddings()

            mock_class.assert_called_once_with(
                api_key="test-key",
                model=OpenAIEmbeddingProvider.DEFAULT_MODEL,
            )
            assert emb is mock_emb

    def test_create_embeddings_failure(self):
        """Test embeddings creation failure raises EmbeddingError."""
        with patch('docgen.providers.openai.OpenAIEmbeddings', side_effect=Exception("API error")):
            provider = OpenAIEmbeddingProvider.__new__(OpenAIEmbeddingProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._embeddings = None

            with pytest.raises(EmbeddingError, match="Failed to create OpenAI embeddings"):
                provider.get_langchain_embeddings()

    def test_embed_documents_success(self):
        """Test successful document embedding."""
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        with patch('docgen.providers.openai.OpenAIEmbeddings', return_value=mock_emb):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            result = provider.embed_documents(["doc1", "doc2"])

            mock_emb.embed_documents.assert_called_once_with(["doc1", "doc2"])
            assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    def test_embed_documents_failure(self):
        """Test document embedding failure raises EmbeddingError."""
        mock_emb = MagicMock()
        mock_emb.embed_documents.side_effect = Exception("API error")

        with patch('docgen.providers.openai.OpenAIEmbeddings', return_value=mock_emb):
            provider = OpenAIEmbeddingProvider(api_key="test-key")

            with pytest.raises(EmbeddingError, match="Failed to embed documents"):
                provider.embed_documents(["doc1"])

    def test_embed_query_success(self):
        """Test successful query embedding."""
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch('docgen.providers.openai.OpenAIEmbeddings', return_value=mock_emb):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            result = provider.embed_query("test query")

            mock_emb.embed_query.assert_called_once_with("test query")
            assert result == [0.1, 0.2, 0.3]

    def test_embed_query_failure(self):
        """Test query embedding failure raises EmbeddingError."""
        mock_emb = MagicMock()
        mock_emb.embed_query.side_effect = Exception("API error")

        with patch('docgen.providers.openai.OpenAIEmbeddings', return_value=mock_emb):
            provider = OpenAIEmbeddingProvider(api_key="test-key")

            with pytest.raises(EmbeddingError, match="Failed to embed query"):
                provider.embed_query("test query")
