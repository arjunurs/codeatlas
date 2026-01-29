from unittest.mock import Mock, patch

import pytest

from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import ApiKeyError, DocumentationError


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    return Mock()


@pytest.fixture
def mock_embeddings():
    """Create mock embeddings."""
    return Mock()


@pytest.fixture
def mock_analyzer():
    """Create a mock CodeAnalyzer."""
    return Mock()


@pytest.fixture
def mock_diagram_generator():
    """Create a mock DiagramGenerator."""
    return Mock()


@pytest.fixture
def generator(mock_llm, mock_embeddings, mock_analyzer, mock_diagram_generator):
    """Create a CodeDocumentationGenerator with mocked dependencies."""
    with (
        patch("docgen.providers.anthropic.ChatAnthropic") as mock_chat_anthropic,
        patch("docgen.providers.openai.OpenAIEmbeddings") as mock_openai_emb,
        patch("docgen.core.generator.CodeAnalyzer") as mock_code_analyzer,
        patch("docgen.core.generator.DiagramGenerator") as mock_diagram_gen,
    ):
        mock_chat_anthropic.return_value = mock_llm
        mock_openai_emb.return_value = mock_embeddings
        mock_code_analyzer.return_value = mock_analyzer
        mock_diagram_gen.return_value = mock_diagram_generator

        gen = CodeDocumentationGenerator(
            anthropic_api_key="test-anthropic-key", openai_api_key="test-openai-key"
        )
        return gen


def test_init_with_api_key(generator):
    """Test successful initialization with API keys."""
    assert isinstance(generator, CodeDocumentationGenerator)


def test_init_no_api_key():
    """Test initialization without API keys."""
    with pytest.raises(
        ApiKeyError, match="Both Anthropic and OpenAI API keys are required"
    ):
        CodeDocumentationGenerator(
            anthropic_api_key=None, openai_api_key="test-openai-key"
        )


def test_init_invalid_temperature():
    """Test initialization with invalid temperature."""
    with pytest.raises(ValueError, match="Temperature must be between 0 and 1"):
        CodeDocumentationGenerator(
            anthropic_api_key="test-key", openai_api_key="test-key", temperature=2.0
        )


def test_generate_documentation_no_files(generator, tmp_path):
    """Test documentation generation with no Python files."""
    source_dir = tmp_path / "empty"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"

    # Mock analyzer to return empty list
    generator.analyzer.analyze_directory.return_value = []

    with pytest.raises(DocumentationError, match="No Python files found in directory"):
        generator.generate_documentation(str(source_dir), str(output_dir))


def test_generate_documentation_invalid_dir(generator):
    """Test documentation generation with invalid directory."""
    with pytest.raises(ValueError, match="Invalid source directory"):
        generator.generate_documentation("nonexistent_dir", "docs")
