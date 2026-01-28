"""Unit tests for provider registry."""

import pytest
from unittest.mock import MagicMock, patch

from docgen.providers.registry import ProviderRegistry, get_default_registry
from docgen.providers.anthropic import AnthropicProvider
from docgen.providers.openai import OpenAIProvider, OpenAIEmbeddingProvider
from docgen.providers.base import BaseLLMProvider, BaseEmbeddingProvider


class TestProviderRegistry:
    """Test cases for ProviderRegistry."""

    def test_default_llm_providers_registered(self):
        """Test that default LLM providers are registered."""
        registry = ProviderRegistry()
        available = registry.get_available_llm_providers()

        assert "anthropic" in available
        assert "claude" in available  # Alias
        assert "openai" in available
        assert "gpt" in available  # Alias

    def test_default_embedding_providers_registered(self):
        """Test that default embedding providers are registered."""
        registry = ProviderRegistry()
        available = registry.get_available_embedding_providers()

        assert "openai" in available

    def test_register_custom_llm_provider(self):
        """Test registering a custom LLM provider."""

        class CustomProvider(BaseLLMProvider):
            def _create_llm(self):
                return MagicMock()

            def invoke(self, prompt):
                return "response"

        registry = ProviderRegistry()
        registry.register_llm_provider("custom", CustomProvider)

        assert "custom" in registry.get_available_llm_providers()

    def test_register_custom_embedding_provider(self):
        """Test registering a custom embedding provider."""

        class CustomEmbedding(BaseEmbeddingProvider):
            def _create_embeddings(self):
                return MagicMock()

            def embed_documents(self, texts):
                return [[0.1]]

            def embed_query(self, text):
                return [0.1]

        registry = ProviderRegistry()
        registry.register_embedding_provider("custom", CustomEmbedding)

        assert "custom" in registry.get_available_embedding_providers()

    def test_create_llm_provider_anthropic(self):
        """Test creating Anthropic provider."""
        registry = ProviderRegistry()

        with patch('docgen.providers.anthropic.ChatAnthropic'):
            provider = registry.create_llm_provider(
                "anthropic",
                api_key="test-key",
                model="claude-3-sonnet-20240229",
                temperature=0.5,
            )

            assert isinstance(provider, AnthropicProvider)
            assert provider.model_name == "claude-3-sonnet-20240229"
            assert provider.temperature == 0.5

    def test_create_llm_provider_openai(self):
        """Test creating OpenAI provider."""
        registry = ProviderRegistry()

        with patch('docgen.providers.openai.ChatOpenAI'):
            provider = registry.create_llm_provider(
                "openai",
                api_key="test-key",
                model="gpt-4",
            )

            assert isinstance(provider, OpenAIProvider)
            assert provider.model_name == "gpt-4"

    def test_create_llm_provider_case_insensitive(self):
        """Test that provider names are case-insensitive."""
        registry = ProviderRegistry()

        with patch('docgen.providers.anthropic.ChatAnthropic'):
            provider1 = registry.create_llm_provider("ANTHROPIC", api_key="test")
            provider2 = registry.create_llm_provider("Anthropic", api_key="test")
            provider3 = registry.create_llm_provider("anthropic", api_key="test")

            assert isinstance(provider1, AnthropicProvider)
            assert isinstance(provider2, AnthropicProvider)
            assert isinstance(provider3, AnthropicProvider)

    def test_create_llm_provider_unknown(self):
        """Test that unknown provider raises ValueError."""
        registry = ProviderRegistry()

        with pytest.raises(ValueError, match="Unknown LLM provider: unknown"):
            registry.create_llm_provider("unknown", api_key="test")

    def test_create_embedding_provider_openai(self):
        """Test creating OpenAI embedding provider."""
        registry = ProviderRegistry()

        with patch('docgen.providers.openai.OpenAIEmbeddings'):
            provider = registry.create_embedding_provider(
                "openai",
                api_key="test-key",
                model="text-embedding-3-large",
            )

            assert isinstance(provider, OpenAIEmbeddingProvider)
            assert provider.model_name == "text-embedding-3-large"

    def test_create_embedding_provider_unknown(self):
        """Test that unknown embedding provider raises ValueError."""
        registry = ProviderRegistry()

        with pytest.raises(ValueError, match="Unknown embedding provider: unknown"):
            registry.create_embedding_provider("unknown", api_key="test")


class TestGetDefaultRegistry:
    """Test cases for get_default_registry function."""

    def test_returns_registry(self):
        """Test that function returns a ProviderRegistry."""
        # Reset the global registry
        import docgen.providers.registry as registry_module
        registry_module._default_registry = None

        registry = get_default_registry()
        assert isinstance(registry, ProviderRegistry)

    def test_returns_same_instance(self):
        """Test that function returns the same instance on multiple calls."""
        # Reset the global registry
        import docgen.providers.registry as registry_module
        registry_module._default_registry = None

        registry1 = get_default_registry()
        registry2 = get_default_registry()

        assert registry1 is registry2
