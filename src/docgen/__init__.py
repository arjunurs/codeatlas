"""Code Documentation Generator Package.

This package provides tools for generating comprehensive documentation for Python codebases.
"""

__version__ = "0.1.0"

# Import main components for easy access
from .cli import main, parse_args
from .core.generator import CodeDocumentationGenerator
from .utils.logging import setup_logging

__all__ = ["parse_args", "main", "CodeDocumentationGenerator", "setup_logging"]
