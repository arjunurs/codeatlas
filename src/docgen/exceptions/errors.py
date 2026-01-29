"""Custom exceptions for the documentation generator.

This module defines custom exception classes used throughout the documentation
generator to handle specific error cases.
"""


class DocumentationError(Exception):
    """Base exception class for documentation generation errors."""

    pass


class CodeParseError(DocumentationError):
    """Raised when there is an error parsing Python source code."""

    pass


class DiagramGenerationError(DocumentationError):
    """Raised when there is an error generating documentation diagrams."""

    pass


class DiagramValidationError(DiagramGenerationError):
    """Raised when diagram validation fails."""

    pass


class ApiKeyError(DocumentationError):
    """Raised when there are issues with the API key configuration."""

    pass


class VectorStoreError(DocumentationError):
    """Raised when there are issues with vector store operations."""

    pass


class FileEncodingError(DocumentationError):
    """Raised when there are file encoding issues."""

    pass


class TemplateError(DocumentationError):
    """Raised when there are template rendering issues."""

    pass


class LLMError(DocumentationError):
    """Raised when there are LLM communication issues."""

    pass


class EmbeddingError(DocumentationError):
    """Raised when there are embedding generation issues."""

    pass


class PathValidationError(DocumentationError):
    """Raised when a path fails security validation."""

    pass


class CacheError(DocumentationError):
    """Raised when there are cache management issues."""

    pass
