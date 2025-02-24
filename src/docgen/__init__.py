"""Code Documentation Generator Package.

This package provides tools for generating comprehensive documentation for Python codebases.
"""

__version__ = "0.1.0"

import ast
from dotenv import find_dotenv, load_dotenv
from langchain.chains import RetrievalQA
from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings

from .cli import parse_args, main
from .core.analyzer import CodeAnalyzer
from .core.diagrams import DiagramGenerator
from .core.generator import CodeDocumentationGenerator
from .exceptions.errors import ApiKeyError, CodeParseError, DocumentationError
from .models.code_entity import CodeEntity
from .models.file_analysis import FileAnalysis
from .utils.api_keys import get_api_keys
from .utils.logging import setup_logging

__all__ = [
    'ast',
    'find_dotenv',
    'load_dotenv',
    'RetrievalQA',
    'ChatAnthropic',
    'OpenAIEmbeddings',
    'parse_args',
    'main',
    'CodeAnalyzer',
    'DiagramGenerator',
    'CodeDocumentationGenerator',
    'ApiKeyError',
    'CodeParseError',
    'DocumentationError',
    'CodeEntity',
    'FileAnalysis',
    'get_api_keys',
    'setup_logging',
] 