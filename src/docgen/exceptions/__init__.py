"""Exceptions module for the documentation generator.

This module provides custom exceptions used throughout the codebase.
"""

from .errors import (
    DocumentationError,
    CodeParseError,
    DiagramGenerationError,
    ApiKeyError,
    VectorStoreError,
    FileEncodingError,
    TemplateError,
    LLMError,
    EmbeddingError,
    PathValidationError,
)

__all__ = [
    'DocumentationError',
    'CodeParseError',
    'DiagramGenerationError',
    'ApiKeyError',
    'VectorStoreError',
    'FileEncodingError',
    'TemplateError',
    'LLMError',
    'EmbeddingError',
    'PathValidationError',
]
