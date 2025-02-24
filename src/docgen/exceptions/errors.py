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

class ApiKeyError(DocumentationError):
    """Raised when there are issues with the API key configuration."""
    pass 