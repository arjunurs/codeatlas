"""LLM provider abstractions for the documentation generator.

This module provides abstract interfaces and concrete implementations
for various LLM and embedding providers, allowing for extensibility
and easier testing.
"""

from .anthropic import AnthropicProvider
from .base import EmbeddingProvider, LLMProvider
from .openai import OpenAIEmbeddingProvider, OpenAIProvider
from .registry import (
    ProviderRegistry,
    create_default_providers,
    get_default_registry,
)

__all__ = [
    "AnthropicProvider",
    "EmbeddingProvider",
    "LLMProvider",
    "OpenAIEmbeddingProvider",
    "OpenAIProvider",
    "ProviderRegistry",
    "create_default_providers",
    "get_default_registry",
]
