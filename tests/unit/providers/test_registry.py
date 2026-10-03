"""Unit tests for provider registry."""

from unittest.mock import MagicMock, patch

import pytest

from docgen.config import DEFAULT_CONFIG, QualityMode
from docgen.providers.anthropic import AnthropicProvider
from docgen.providers.base import BaseEmbeddingProvider, BaseLLMProvider
from docgen.providers.openai import OpenAIEmbeddingProvider, OpenAIProvider
from docgen.providers.registry import (
    ProviderRegistry,
    create_default_providers,
    get_default_registry,
)


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

        with patch("docgen.providers.anthropic.ChatAnthropic"):
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

        with patch("docgen.providers.openai.ChatOpenAI"):
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

        with patch("docgen.providers.anthropic.ChatAnthropic"):
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

        with patch("docgen.providers.openai.OpenAIEmbeddings"):
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


@pytest.mark.parametrize(
    ("anthropic_model", "quality_mode", "expected"),
    [
        (None, None, "claude-sonnet-5"),
        (None, QualityMode.FAST, "claude-haiku-4-5"),
        (None, QualityMode.BALANCED, "claude-sonnet-5"),
        (None, QualityMode.BEST, "claude-opus-5"),
        ("claude-custom", QualityMode.FAST, "claude-custom"),
        ("claude-custom", None, "claude-custom"),
    ],
)
def test_default_providers_model_precedence(anthropic_model, quality_mode, expected):
    """An explicit model wins, then the quality mode, then the default."""
    llm_provider, _ = create_default_providers(
        "test-anthropic",
        "test-openai",
        anthropic_model=anthropic_model,
        quality_mode=quality_mode,
    )

    assert llm_provider.model_name == expected
    assert llm_provider.get_langchain_llm().model == expected


def test_default_providers_set_output_token_limit():
    """Sections get an explicit output limit instead of the library default."""
    llm_provider, _ = create_default_providers("test-anthropic", "test-openai")

    llm = llm_provider.get_langchain_llm()
    assert llm.max_tokens == DEFAULT_CONFIG.DEFAULT_MAX_OUTPUT_TOKENS
    assert DEFAULT_CONFIG.DEFAULT_MAX_OUTPUT_TOKENS > 4096


def test_default_providers_embedding_model():
    """The embedding model is the one given, or the configured default."""
    _, default = create_default_providers("test-anthropic", "test-openai")
    _, chosen = create_default_providers(
        "test-anthropic", "test-openai", embedding_model="text-embedding-3-large"
    )

    assert default.model_name == DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL
    assert chosen.model_name == "text-embedding-3-large"


def test_default_providers_reject_out_of_range_temperature():
    """A temperature outside 0 to 1 is rejected when the providers are made."""
    with pytest.raises(ValueError, match="Temperature must be between 0 and 1"):
        create_default_providers("test-anthropic", "test-openai", temperature=2.0)
