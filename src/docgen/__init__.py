"""Code Documentation Generator.

A tool for automatically generating comprehensive documentation for Python codebases
using Large Language Models (LLMs). It analyzes code structure, relationships, and
patterns to create rich, interactive documentation with architectural diagrams.
"""

__version__ = "0.1.0"

from .core.generator import CodeDocumentationGenerator
from .models.code_entity import CodeEntity
from .models.file_analysis import FileAnalysis
from .exceptions.errors import (
    DocumentationError,
    CodeParseError,
    DiagramGenerationError,
    ApiKeyError
)

__all__ = [
    'CodeDocumentationGenerator',
    'CodeEntity',
    'FileAnalysis',
    'DocumentationError',
    'CodeParseError',
    'DiagramGenerationError',
    'ApiKeyError'
] 