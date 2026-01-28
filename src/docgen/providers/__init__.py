"""LLM provider abstractions for the documentation generator.

This module provides abstract interfaces and concrete implementations
for various LLM and embedding providers, allowing for extensibility
and easier testing.
"""

from .base import LLMProvider, EmbeddingProvider, LLMResponse
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider, OpenAIEmbeddingProvider
from .registry import ProviderRegistry, get_default_registry

__all__ = [
    "LLMProvider",
    "EmbeddingProvider",
    "LLMResponse",
    "AnthropicProvider",
    "OpenAIProvider",
    "OpenAIEmbeddingProvider",
    "ProviderRegistry",
    "get_default_registry",
]
