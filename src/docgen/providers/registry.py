"""Provider registry for dynamic provider loading.

This module provides a registry pattern for managing LLM and embedding
providers, allowing for dynamic provider selection and easy extension.
"""

from collections.abc import Callable

from .anthropic import AnthropicProvider
from .base import BaseEmbeddingProvider, BaseLLMProvider, EmbeddingProvider, LLMProvider
from .openai import OpenAIEmbeddingProvider, OpenAIProvider

# Type aliases for provider factories
LLMProviderFactory = Callable[..., LLMProvider]
EmbeddingProviderFactory = Callable[..., EmbeddingProvider]


class ProviderRegistry:
    """Registry for LLM and embedding providers.

    This class maintains registries of available providers and provides
    methods to create provider instances by name.
    """

    def __init__(self) -> None:
        """Initialize the provider registry with default providers."""
        self._llm_providers: dict[str, type[BaseLLMProvider]] = {}
        self._embedding_providers: dict[str, type[BaseEmbeddingProvider]] = {}

        # Register default providers
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Register the default set of providers."""
        # LLM providers
        self.register_llm_provider("anthropic", AnthropicProvider)
        self.register_llm_provider("claude", AnthropicProvider)  # Alias
        self.register_llm_provider("openai", OpenAIProvider)
        self.register_llm_provider("gpt", OpenAIProvider)  # Alias

        # Embedding providers
        self.register_embedding_provider("openai", OpenAIEmbeddingProvider)

    def register_llm_provider(
        self,
        name: str,
        provider_class: type[BaseLLMProvider],
    ) -> None:
        """Register an LLM provider.

        Args:
            name: Name to register the provider under
            provider_class: The provider class to register
        """
        self._llm_providers[name.lower()] = provider_class

    def register_embedding_provider(
        self,
        name: str,
        provider_class: type[BaseEmbeddingProvider],
    ) -> None:
        """Register an embedding provider.

        Args:
            name: Name to register the provider under
            provider_class: The provider class to register
        """
        self._embedding_providers[name.lower()] = provider_class

    def create_llm_provider(
        self,
        name: str,
        api_key: str,
        model: str | None = None,
        temperature: float = 0.2,
        **kwargs,
    ) -> LLMProvider:
        """Create an LLM provider instance by name.

        Args:
            name: Name of the provider to create
            api_key: API key for the provider
            model: Optional model name
            temperature: Temperature for generation
            **kwargs: Additional provider-specific arguments

        Returns:
            An LLM provider instance

        Raises:
            ValueError: If the provider name is not registered
        """
        name_lower = name.lower()
        if name_lower not in self._llm_providers:
            available = ", ".join(sorted(self._llm_providers.keys()))
            raise ValueError(
                f"Unknown LLM provider: {name}. Available providers: {available}"
            )

        provider_class = self._llm_providers[name_lower]
        return provider_class(
            api_key=api_key,
            model=model,
            temperature=temperature,
            **kwargs,
        )

    def create_embedding_provider(
        self,
        name: str,
        api_key: str,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingProvider:
        """Create an embedding provider instance by name.

        Args:
            name: Name of the provider to create
            api_key: API key for the provider
            model: Optional model name
            **kwargs: Additional provider-specific arguments

        Returns:
            An embedding provider instance

        Raises:
            ValueError: If the provider name is not registered
        """
        name_lower = name.lower()
        if name_lower not in self._embedding_providers:
            available = ", ".join(sorted(self._embedding_providers.keys()))
            raise ValueError(
                f"Unknown embedding provider: {name}. Available providers: {available}"
            )

        provider_class = self._embedding_providers[name_lower]
        return provider_class(
            api_key=api_key,
            model=model,
            **kwargs,
        )

    def get_available_llm_providers(self) -> list:
        """Get list of available LLM provider names.

        Returns:
            List of registered LLM provider names
        """
        return sorted(self._llm_providers.keys())

    def get_available_embedding_providers(self) -> list:
        """Get list of available embedding provider names.

        Returns:
            List of registered embedding provider names
        """
        return sorted(self._embedding_providers.keys())


# Global default registry instance
_default_registry: ProviderRegistry | None = None


def get_default_registry() -> ProviderRegistry:
    """Get the default provider registry instance.

    Returns:
        The default ProviderRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
    return _default_registry
