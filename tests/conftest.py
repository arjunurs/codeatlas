"""Shared pytest fixtures for the documentation generator tests.

This module provides common fixtures used across multiple test modules,
including mock LLM components, sample data objects, and temporary directories.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis

# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_code_entity() -> CodeEntity:
    """Create a sample CodeEntity for testing.

    Returns:
        A CodeEntity representing a test class with one method.
    """
    return CodeEntity(
        name="TestClass",
        type="class",
        docstring="A test class for documentation testing.",
        methods=["test_method", "__init__"],
        start_line=1,
        end_line=10,
        source="class TestClass:\n    def __init__(self):\n        pass\n    def test_method(self):\n        pass",
        parent_class=None,
    )


@pytest.fixture
def sample_function_entity() -> CodeEntity:
    """Create a sample function CodeEntity for testing.

    Returns:
        A CodeEntity representing a test function.
    """
    return CodeEntity(
        name="test_function",
        type="function",
        docstring="A test function for documentation testing.",
        start_line=1,
        end_line=3,
        source="def test_function(arg1, arg2):\n    return arg1 + arg2",
    )


@pytest.fixture
def sample_file_analysis(
    sample_code_entity: CodeEntity, tmp_path: Path
) -> FileAnalysis:
    """Create a sample FileAnalysis for testing.

    Args:
        sample_code_entity: A sample CodeEntity fixture
        tmp_path: Pytest temporary path fixture

    Returns:
        A FileAnalysis with the sample entity.
    """
    # Create actual file so validation passes
    test_file = tmp_path / "test_module.py"
    test_file.write_text(sample_code_entity.source)

    return FileAnalysis(
        file_path=str(test_file),
        entities=[sample_code_entity],
        imports=["import os", "from typing import List"],
        content=sample_code_entity.source,
    )


@pytest.fixture
def sample_file_analysis_no_validation(sample_code_entity: CodeEntity) -> FileAnalysis:
    """Create a sample FileAnalysis without file validation.

    Useful for tests that don't need actual files on disk.

    Args:
        sample_code_entity: A sample CodeEntity fixture

    Returns:
        A FileAnalysis with validation skipped.
    """
    return FileAnalysis(
        file_path="/path/to/test_module.py",
        entities=[sample_code_entity],
        imports=["import os", "from typing import List"],
        content=sample_code_entity.source,
        _skip_validation=True,
    )


# =============================================================================
# Mock LLM Fixtures
# =============================================================================


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing.

    Returns:
        A MagicMock configured to simulate LLM responses.
    """
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Generated documentation content")
    return mock


@pytest.fixture
def mock_embeddings():
    """Create mock embeddings for testing.

    Returns:
        A MagicMock configured to simulate embedding operations.
    """
    mock = MagicMock()
    mock.embed_documents.return_value = [[0.1, 0.2, 0.3] for _ in range(10)]
    mock.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock


@pytest.fixture
def mock_rag_chain():
    """Create a mock RAG chain for testing (LCEL pattern).

    LCEL chains with StrOutputParser return strings directly,
    not message objects with .content attributes.

    Returns:
        A MagicMock configured to simulate LCEL RAG chain responses.
    """
    mock = MagicMock()
    # LCEL chains return the string directly (after StrOutputParser)
    mock.invoke.return_value = "Generated section content"
    return mock


@pytest.fixture
def mock_analyzer(sample_file_analysis_no_validation: FileAnalysis):
    """Create a mock CodeAnalyzer for testing.

    Args:
        sample_file_analysis_no_validation: Sample file analysis fixture

    Returns:
        A MagicMock configured to simulate code analysis.
    """
    mock = MagicMock()
    mock.analyze_directory.return_value = [sample_file_analysis_no_validation]
    mock.analyze_file.return_value = sample_file_analysis_no_validation
    mock.analyze_function_calls.return_value = {
        "test_function": {"called_function"},
        "called_function": set(),
    }
    mock.analyze_package_dependencies.return_value = {
        "docgen": {"langchain", "jinja2"},
        "langchain": set(),
    }
    return mock


@pytest.fixture
def mock_diagram_generator():
    """Create a mock DiagramGenerator for testing.

    Returns:
        A MagicMock configured to simulate diagram generation.
    """
    mock = MagicMock()
    mock.generate_architecture_diagram.return_value = "graph TD\n    A[A] --> B[B]"
    mock.generate_class_diagram.return_value = "classDiagram\n    class Test"
    mock.generate_sequence_diagram.return_value = "sequenceDiagram\n    A->>B: call"
    mock.generate_dependency_diagram.return_value = "graph LR\n    pkg1 --> pkg2"
    mock.generate_call_graph_diagram.return_value = "graph TD\n    func1 --> func2"
    return mock


@pytest.fixture
def mock_template_manager():
    """Create a mock TemplateManager for testing.

    Returns:
        A MagicMock configured to simulate template rendering.
    """
    mock = MagicMock()
    mock.render_template = MagicMock()
    mock.templates = {
        "base": MagicMock(render=MagicMock(return_value="<html>Base</html>")),
        "index": MagicMock(render=MagicMock(return_value="<html>Index</html>")),
        "section": MagicMock(render=MagicMock(return_value="<html>Section</html>")),
        "diagrams": MagicMock(render=MagicMock(return_value="<html>Diagrams</html>")),
        "search": MagicMock(render=MagicMock(return_value="<html>Search</html>")),
        "navigation": MagicMock(render=MagicMock(return_value="<nav>Nav</nav>")),
    }
    return mock


# =============================================================================
# Directory Fixtures
# =============================================================================


@pytest.fixture
def temp_source_dir(tmp_path: Path) -> Path:
    """Create a temporary source directory with sample Python files.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to the created source directory.
    """
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    # Create a simple Python module
    (source_dir / "__init__.py").write_text('"""Package init."""')

    (source_dir / "main.py").write_text('''"""Main module."""

import os
from typing import List


class MainClass:
    """The main class of the application."""

    def __init__(self):
        """Initialize the main class."""
        self.data = []

    def process(self, items: List[str]) -> List[str]:
        """Process a list of items."""
        return [item.upper() for item in items]


def helper_function(value: int) -> int:
    """A helper function."""
    return value * 2
''')

    (source_dir / "utils.py").write_text('''"""Utility functions."""


def format_string(text: str) -> str:
    """Format a string."""
    return text.strip().lower()


def parse_int(value: str) -> int:
    """Parse an integer from a string."""
    return int(value)
''')

    return source_dir


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for documentation.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to the created output directory.
    """
    output_dir = tmp_path / "docs"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def empty_source_dir(tmp_path: Path) -> Path:
    """Create an empty temporary source directory.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to the created empty directory.
    """
    source_dir = tmp_path / "empty_src"
    source_dir.mkdir()
    return source_dir


# =============================================================================
# Generator Fixtures
# =============================================================================


@pytest.fixture
def mock_generator(
    mock_llm,
    mock_embeddings,
    mock_analyzer,
    mock_diagram_generator,
    mock_template_manager,
):
    """Create a CodeDocumentationGenerator with all dependencies mocked.

    This fixture patches all external dependencies and returns a generator
    ready for testing.

    Returns:
        A CodeDocumentationGenerator instance with mocked dependencies.
    """
    from docgen.core.generator import CodeDocumentationGenerator

    # Configure mock_llm to return content (for LCEL StrOutputParser)
    mock_llm.invoke.return_value = MagicMock(content="Generated content")

    with (
        patch("docgen.core.generator.CodeAnalyzer", return_value=mock_analyzer),
        patch(
            "docgen.core.generator.DiagramGenerator",
            return_value=mock_diagram_generator,
        ),
        patch(
            "docgen.core.generator.get_template_manager",
            return_value=mock_template_manager,
        ),
        patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
        patch("docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings),
    ):
        generator = CodeDocumentationGenerator(
            anthropic_api_key="test-anthropic-key",
            openai_api_key="test-openai-key",
        )
        generator.llm = mock_llm
        generator.embeddings = mock_embeddings
        generator.analyzer = mock_analyzer
        generator.diagram_generator = mock_diagram_generator
        generator.template_manager = mock_template_manager

        yield generator


# =============================================================================
# Fake LangChain Models (real LangChain classes, no network)
# =============================================================================


class FakeChatModelWithUsage(BaseChatModel):
    """Chat model that returns fixed text and reports fixed token usage.

    stop_reason mimics Anthropic's response metadata and finish_reason mimics
    OpenAI's generation info, so tests can simulate a truncated response.
    """

    input_tokens: int = 120
    output_tokens: int = 30
    stop_reason: str | None = None
    finish_reason: str | None = None

    @property
    def _llm_type(self) -> str:
        return "fake-with-usage"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = AIMessage(
            content="generated text",
            usage_metadata={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
            response_metadata=(
                {"stop_reason": self.stop_reason} if self.stop_reason else {}
            ),
        )
        generation_info = (
            {"finish_reason": self.finish_reason} if self.finish_reason else None
        )
        return ChatResult(
            generations=[
                ChatGeneration(message=message, generation_info=generation_info)
            ]
        )


class FakeEmbeddings(Embeddings):
    """Embeddings that return constant vectors."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


@pytest.fixture
def fake_chat_model_with_usage() -> FakeChatModelWithUsage:
    """A chat model reporting 120 input and 30 output tokens per call."""
    return FakeChatModelWithUsage()


@pytest.fixture
def fake_embeddings() -> FakeEmbeddings:
    """An embeddings model returning constant vectors."""
    return FakeEmbeddings()
