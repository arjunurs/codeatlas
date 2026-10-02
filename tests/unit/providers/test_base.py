"""Unit tests for base provider classes."""

from unittest.mock import MagicMock

import pytest

from docgen.providers.base import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    EmbeddingProvider,
    LLMProvider,
    classify_api_error,
)


class TestLLMProviderProtocol:
    """Test cases for LLMProvider protocol."""

    def test_protocol_check_valid(self):
        """Test that valid objects satisfy the protocol."""
        mock = MagicMock()
        mock.model_name = "test-model"
        mock.invoke = MagicMock(return_value="response")

        # Protocol check should pass
        assert isinstance(mock, LLMProvider)

    def test_protocol_check_missing_method(self):
        """Test that objects missing methods don't satisfy protocol."""

        class IncompleteProvider:
            model_name = "test"
            # Missing invoke

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


class TestClassifyApiError:
    """Test cases for classify_api_error function."""

    def test_rate_limit_match(self):
        """Test that rate limit errors are classified correctly."""
        assert classify_api_error(Exception("rate limit exceeded")) == "rate_limit"
        assert classify_api_error(Exception("Rate Limit hit")) == "rate_limit"

    def test_rate_or_limit_alone_is_not_rate_limit(self):
        """Test that "rate" or "limit" on its own does not mean a rate limit."""
        assert classify_api_error(Exception("rate exceeded")) is None
        assert classify_api_error(Exception("limit reached")) is None

    def test_auth_errors(self):
        """Test authentication error classification."""
        assert classify_api_error(Exception("api_key invalid")) == "auth"
        assert classify_api_error(Exception("authentication failed")) == "auth"
        assert classify_api_error(Exception("unauthorized access")) == "auth"
        assert classify_api_error(Exception("401 error")) == "auth"

    def test_timeout_errors(self):
        """Test timeout error classification."""
        assert classify_api_error(Exception("request timeout")) == "timeout"
        assert classify_api_error(Exception("timed out")) == "timeout"

    def test_connection_errors(self):
        """Test connection error classification."""
        assert classify_api_error(Exception("connection refused")) == "connection"

    def test_quota_errors(self):
        """Test quota error classification."""
        assert classify_api_error(Exception("quota exceeded")) == "quota"
        assert classify_api_error(Exception("billing issue")) == "quota"

    def test_context_length_errors(self):
        """Test context length error classification."""
        assert classify_api_error(Exception("context too long")) == "context_length"
        assert classify_api_error(Exception("max length exceeded")) == "context_length"

    def test_no_match(self):
        """Test that unrecognized errors return None."""
        assert classify_api_error(Exception("some random error")) is None
        assert classify_api_error(Exception("")) is None

    @pytest.mark.parametrize(
        "message",
        [
            "Failed to generate documentation section",
            "Could not separate the input",
            "Inaccurate response format",
            "Delimiter missing in output",
            "Contextual information missing",
            "Invalid wavelength value",
        ],
    )
    def test_keyword_inside_longer_word_does_not_match(self, message):
        """Keywords only match as whole words, not inside longer words."""
        assert classify_api_error(Exception(message)) is None

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("Rate limit exceeded", "rate_limit"),
            ("429 Too Many Requests", "rate_limit"),
            (
                "Error code: 429 - {'type': 'error', 'error': {'type': "
                "'rate_limit_error', 'message': 'Number of request tokens has "
                "exceeded your per-minute rate limit'}}",
                "rate_limit",
            ),
            (
                "Error code: 401 - {'type': 'error', 'error': {'type': "
                "'authentication_error', 'message': 'invalid x-api-key'}}",
                "auth",
            ),
            (
                "Error code: 401 - {'error': {'message': 'Incorrect API key "
                "provided', 'code': 'invalid_api_key'}}",
                "auth",
            ),
            (
                "Error code: 429 - {'error': {'message': 'You exceeded your "
                "current quota, please check your plan and billing details.', "
                "'code': 'insufficient_quota'}}",
                "quota",
            ),
            ("Request timed out.", "timeout"),
            ("Connection error.", "connection"),
            (
                "Error code: 400 - {'error': {'message': \"This model's maximum "
                "context length is 8192 tokens.\", 'code': "
                "'context_length_exceeded'}}",
                "context_length",
            ),
            ("prompt is too long: 215000 tokens > 200000 maximum", "context_length"),
        ],
    )
    def test_provider_style_messages(self, message, expected):
        """Messages shaped like real provider errors map to the right type."""
        assert classify_api_error(Exception(message)) == expected
