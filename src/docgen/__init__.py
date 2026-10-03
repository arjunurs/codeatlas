"""Code Documentation Generator Package.

This package provides tools for generating comprehensive documentation for Python codebases.
"""

# Import main components for easy access
from .cli import __version__, main, parse_args
from .core.generator import CodeDocumentationGenerator
from .utils.logging import setup_logging

__all__ = [
    "CodeDocumentationGenerator",
    "__version__",
    "main",
    "parse_args",
    "setup_logging",
]
