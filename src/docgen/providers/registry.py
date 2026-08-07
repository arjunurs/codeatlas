"""Provider registry for dynamic provider loading.

This module provides a registry pattern for managing LLM and embedding
providers, allowing for dynamic provider selection and easy extension.

Provider classes are imported lazily so that heavy dependencies
(``langchain_anthropic``, ``langchain_openai``) are only loaded when a
provider is actually instantiated.
"""

import importlib
from collections.abc import Callable

from .base import EmbeddingProvider, LLMProvider

# Type aliases for provider factories
LLMProviderFactory = Callable[..., LLMProvider]
EmbeddingProviderFactory = Callable[..., EmbeddingProvider]

# Lazy-import descriptors: (module_path, class_name)
_DEFAULT_LLM_PROVIDERS: dict[str, tuple[str, str]] = {
    "anthropic": ("docgen.providers.anthropic", "AnthropicProvider"),
    "claude": ("docgen.providers.anthropic", "AnthropicProvider"),
    "openai": ("docgen.providers.openai", "OpenAIProvider"),
    "gpt": ("docgen.providers.openai", "OpenAIProvider"),
}
_DEFAULT_EMBEDDING_PROVIDERS: dict[str, tuple[str, str]] = {
    "openai": ("docgen.providers.openai", "OpenAIEmbeddingProvider"),
}


def _resolve(module_path: str, class_name: str) -> type:
    """Import *class_name* from *module_path* on first use."""
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


class ProviderRegistry:
    """Registry for LLM and embedding providers.

    Provider classes are stored as lazy references (module path + class
    name) and only imported when ``create_*`` is called.
    """

    def __init__(self) -> None:
        """Initialize the provider registry with default providers."""
        self._llm_providers: dict[str, type | tuple[str, str]] = {}
        self._embedding_providers: dict[str, type | tuple[str, str]] = {}

        # Register default providers (lazy)
        self._llm_providers.update(_DEFAULT_LLM_PROVIDERS)
        self._embedding_providers.update(_DEFAULT_EMBEDDING_PROVIDERS)

    def register_llm_provider(
        self,
        name: str,
        provider_class: type,
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
        provider_class: type,
    ) -> None:
        """Register an embedding provider.

        Args:
            name: Name to register the provider under
            provider_class: The provider class to register
        """
        self._embedding_providers[name.lower()] = provider_class

    def _resolve_llm(self, name: str) -> type:
        entry = self._llm_providers[name]
        if isinstance(entry, tuple):
            cls = _resolve(*entry)
            self._llm_providers[name] = cls  # cache
            return cls
        return entry

    def _resolve_embedding(self, name: str) -> type:
        entry = self._embedding_providers[name]
        if isinstance(entry, tuple):
            cls = _resolve(*entry)
            self._embedding_providers[name] = cls
            return cls
        return entry

    def create_llm_provider(
        self,
        name: str,
        api_key: str,
        model: str | None = None,
        temperature: float | None = None,
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

        provider_class = self._resolve_llm(name_lower)
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

        provider_class = self._resolve_embedding(name_lower)
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
