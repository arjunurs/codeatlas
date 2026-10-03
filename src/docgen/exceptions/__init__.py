"""Exceptions module for the documentation generator.

This module provides custom exceptions used throughout the codebase.
"""

from .errors import (
    ApiKeyError,
    CodeParseError,
    DiagramGenerationError,
    DocumentationError,
    EmbeddingError,
    FileEncodingError,
    LLMError,
    PathValidationError,
    TemplateError,
    VectorStoreError,
)

__all__ = [
    "ApiKeyError",
    "CodeParseError",
    "DiagramGenerationError",
    "DocumentationError",
    "EmbeddingError",
    "FileEncodingError",
    "LLMError",
    "PathValidationError",
    "TemplateError",
    "VectorStoreError",
]
