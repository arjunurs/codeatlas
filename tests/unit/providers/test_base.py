"""Unit tests for base provider classes."""

from unittest.mock import MagicMock

import pytest

from docgen.providers.base import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    EmbeddingProvider,
    LLMProvider,
)


class TestLLMProviderProtocol:
    """Test cases for LLMProvider protocol."""

    def test_protocol_check_valid(self):
        """Test that valid objects satisfy the protocol."""
        mock = MagicMock()
        mock.model_name = "test-model"
        mock.invoke = MagicMock(return_value="response")
        mock.get_langchain_llm = MagicMock(return_value=MagicMock())

        # Protocol check should pass
        assert isinstance(mock, LLMProvider)

    def test_protocol_check_missing_method(self):
        """Test that objects missing methods don't satisfy protocol."""

        class IncompleteProvider:
            model_name = "test"
            # Missing invoke and get_langchain_llm

        # This will not satisfy the protocol at runtime
        provider = IncompleteProvider()
        assert not isinstance(provider, LLMProvider)


class TestEmbeddingProviderProtocol:
    """Test cases for EmbeddingProvider protocol."""

    def test_protocol_check_valid(self):
        """Test that valid objects satisfy the protocol."""
        mock = MagicMock()
        mock.model_name = "test-model"
        mock.embed_documents = MagicMock(return_value=[[0.1, 0.2]])
        mock.embed_query = MagicMock(return_value=[0.1, 0.2])
        mock.get_langchain_embeddings = MagicMock(return_value=MagicMock())

        assert isinstance(mock, EmbeddingProvider)


class TestBaseLLMProvider:
    """Test cases for BaseLLMProvider abstract class."""

    def test_init_empty_api_key(self):
        """Test that empty API key raises ValueError."""

        class TestProvider(BaseLLMProvider):
            def _create_llm(self):
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        with pytest.raises(ValueError, match="API key cannot be empty"):
            TestProvider(api_key="", model="test-model")

    def test_init_invalid_temperature(self):
        """Test that invalid temperature raises ValueError."""

        class TestProvider(BaseLLMProvider):
            def _create_llm(self):
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        with pytest.raises(ValueError, match="Temperature must be between 0 and 1"):
            TestProvider(api_key="test-key", model="test-model", temperature=1.5)

        with pytest.raises(ValueError, match="Temperature must be between 0 and 1"):
            TestProvider(api_key="test-key", model="test-model", temperature=-0.1)

    def test_model_name_property(self):
        """Test model_name property returns correct value."""

        class TestProvider(BaseLLMProvider):
            def _create_llm(self):
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        provider = TestProvider(api_key="test-key", model="my-model")
        assert provider.model_name == "my-model"

    def test_temperature_property(self):
        """Test temperature property returns correct value."""

        class TestProvider(BaseLLMProvider):
            def _create_llm(self):
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        provider = TestProvider(api_key="test-key", model="my-model", temperature=0.5)
        assert provider.temperature == 0.5

    def test_get_langchain_llm_caches(self):
        """Test that get_langchain_llm caches the LLM instance."""

        class TestProvider(BaseLLMProvider):
            create_count = 0

            def _create_llm(self):
                self.create_count += 1
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        provider = TestProvider(api_key="test-key", model="my-model")

        # First call should create
        llm1 = provider.get_langchain_llm()
        assert provider.create_count == 1

        # Second call should return cached
        llm2 = provider.get_langchain_llm()
        assert provider.create_count == 1
        assert llm1 is llm2


class TestBaseEmbeddingProvider:
    """Test cases for BaseEmbeddingProvider abstract class."""

    def test_init_empty_api_key(self):
        """Test that empty API key raises ValueError."""

        class TestProvider(BaseEmbeddingProvider):
            def _create_embeddings(self):
                return MagicMock()

            def embed_documents(self, texts):
                return [[0.1, 0.2]]

            def embed_query(self, text):
                return [0.1, 0.2]

        with pytest.raises(ValueError, match="API key cannot be empty"):
            TestProvider(api_key="", model="test-model")

    def test_model_name_property(self):
        """Test model_name property returns correct value."""

        class TestProvider(BaseEmbeddingProvider):
            def _create_embeddings(self):
                return MagicMock()

            def embed_documents(self, texts):
                return [[0.1, 0.2]]

            def embed_query(self, text):
                return [0.1, 0.2]

        provider = TestProvider(api_key="test-key", model="my-embedding-model")
        assert provider.model_name == "my-embedding-model"

    def test_get_langchain_embeddings_caches(self):
        """Test that get_langchain_embeddings caches the embeddings instance."""

        class TestProvider(BaseEmbeddingProvider):
            create_count = 0

            def _create_embeddings(self):
                self.create_count += 1
                return MagicMock()

            def embed_documents(self, texts):
                return [[0.1, 0.2]]

            def embed_query(self, text):
                return [0.1, 0.2]

        provider = TestProvider(api_key="test-key", model="my-model")

        # First call should create
        emb1 = provider.get_langchain_embeddings()
        assert provider.create_count == 1

        # Second call should return cached
        emb2 = provider.get_langchain_embeddings()
        assert provider.create_count == 1
        assert emb1 is emb2
