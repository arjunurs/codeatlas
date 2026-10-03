"""Provider registry for dynamic provider loading.

This module provides a registry pattern for managing LLM and embedding
providers, allowing for dynamic provider selection and easy extension.

Provider classes are imported lazily so that heavy dependencies
(``langchain_anthropic``, ``langchain_openai``) are only loaded when a
provider is actually instantiated.
"""

import importlib
from collections.abc import Callable

from ..config import (
    DEFAULT_CONFIG,
    GeneratorConfig,
    QualityMode,
    get_model_for_quality_mode,
)
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


def create_default_providers(
    anthropic_api_key: str,
    openai_api_key: str,
    *,
    anthropic_model: str | None = None,
    quality_mode: QualityMode | None = None,
    embedding_model: str | None = None,
    temperature: float | None = None,
    config: GeneratorConfig = DEFAULT_CONFIG,
) -> tuple[LLMProvider, EmbeddingProvider]:
    """Create the providers the command line uses: Claude writes, OpenAI embeds.

    The Claude model is ``anthropic_model`` if given, then the quality mode's
    model, then the configured default.

    Args:
        anthropic_api_key: Anthropic API key
        openai_api_key: OpenAI API key
        anthropic_model: Claude model; overrides the quality mode
        quality_mode: Preset that picks the Claude model
        embedding_model: OpenAI embedding model, or the configured default
        temperature: Sampling temperature, or None for the model's default
        config: Supplies the default models and the output token limit

    Returns:
        The LLM provider and the embedding provider

    Raises:
        ValueError: If a key is empty or the temperature is out of range
    """
    if anthropic_model:
        model = anthropic_model
    elif quality_mode is not None:
        model = get_model_for_quality_mode(quality_mode)
    else:
        model = config.DEFAULT_ANTHROPIC_MODEL

    registry = get_default_registry()
    llm_provider = registry.create_llm_provider(
        "anthropic",
        api_key=anthropic_api_key,
        model=model,
        temperature=temperature,
        max_tokens=config.DEFAULT_MAX_OUTPUT_TOKENS,
    )
    embedding_provider = registry.create_embedding_provider(
        "openai",
        api_key=openai_api_key,
        model=embedding_model or config.DEFAULT_OPENAI_EMBEDDING_MODEL,
    )
    return llm_provider, embedding_provider
