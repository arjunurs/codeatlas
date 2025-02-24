"""Unit tests for the CodeDocumentationGenerator class.

This module contains comprehensive tests for the documentation generation process,
including initialization, file analysis, and HTML generation.
"""

import os
import pytest
from unittest.mock import patch, Mock, MagicMock, mock_open
from docgen.core.generator import CodeDocumentationGenerator
from docgen.models.file_analysis import FileAnalysis
from docgen.models.code_entity import CodeEntity
from docgen.exceptions.errors import DocumentationError

@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    mock = Mock()
    mock.run = Mock(return_value="Generated content")
    return mock

@pytest.fixture
def mock_embeddings():
    """Create mock embeddings."""
    return Mock()

@pytest.fixture
def mock_analyzer():
    """Create a mock CodeAnalyzer."""
    mock = Mock()
    mock.analyze_directory.return_value = [
        FileAnalysis(
            file_path="/path/to/test.py",
            entities=[
                CodeEntity(
                    name="TestClass",
                    docstring="Test class docstring",
                    lineno=1,
                    type="class",
                    methods=["test_method"],
                    file_path="/path/to/test.py"
                )
            ],
            imports=["os"],
            content='"""File docstring."""\n\nclass TestClass:\n    pass',
            _skip_validation=True
        )
    ]
    return mock

@pytest.fixture
def mock_diagram_generator():
    """Create a mock DiagramGenerator."""
    mock = Mock()
    mock.generate_architecture_diagram.return_value = "graph TD\n    A-->B"
    mock.generate_class_diagram.return_value = "classDiagram\n    class Test"
    mock.generate_sequence_diagram.return_value = "sequenceDiagram\n    A->>B: call"
    mock.generate_dependency_diagram.return_value = "graph TD\n    pkg1-->pkg2"
    mock.generate_call_graph_diagram.return_value = "graph TD\n    func1-->func2"
    return mock

@pytest.fixture
def generator(mock_llm, mock_embeddings, mock_analyzer, mock_diagram_generator):
    """Create a CodeDocumentationGenerator instance with mocked dependencies."""
    with patch("docgen.core.generator.ChatAnthropic") as mock_chat:
        mock_chat.return_value = mock_llm
        with patch("docgen.core.generator.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value = mock_embeddings
            with patch("docgen.core.generator.CodeAnalyzer") as mock_ana:
                mock_ana.return_value = mock_analyzer
                with patch("docgen.core.generator.DiagramGenerator") as mock_diag:
                    mock_diag.return_value = mock_diagram_generator
                    
                    generator = CodeDocumentationGenerator(
                        anthropic_api_key="test_anthropic_key",
                        openai_api_key="test_openai_key"
                    )
                    return generator

def test_initialization():
    """Test generator initialization."""
    with pytest.raises(ValueError):
        CodeDocumentationGenerator(
            anthropic_api_key="test",
            openai_api_key="test",
            temperature=2.0  # Invalid temperature
        )

def test_generate_documentation_invalid_directory(generator):
    """Test documentation generation with invalid directory."""
    with pytest.raises(ValueError) as exc_info:
        generator.generate_documentation("/nonexistent/dir", "./output")
    assert "Invalid source directory" in str(exc_info.value)

def test_generate_documentation_success(generator, tmp_path):
    """Test successful documentation generation."""
    output_dir = tmp_path / "docs"
    
    # Mock vector store and QA chain
    mock_vector_store = Mock()
    mock_vector_store.as_retriever.return_value = Mock()
    
    with patch("docgen.core.generator.Chroma") as mock_chroma:
        mock_chroma.from_documents.return_value = mock_vector_store
        with patch("docgen.core.generator.RetrievalQA") as mock_qa:
            mock_qa.from_chain_type.return_value.run.return_value = "Generated content"
            with patch("docgen.core.generator.get_documentation_template") as mock_template:
                mock_template.return_value.render.return_value = "<html>Test</html>"
                with patch("builtins.open", mock_open()) as mock_file:
                    
                    # Create source directory with a Python file
                    source_dir = tmp_path / "src"
                    source_dir.mkdir()
                    (source_dir / "test.py").write_text("print('test')")
                    
                    # Generate documentation
                    generator.generate_documentation(str(source_dir), str(output_dir))
                    
                    # Verify file operations
                    mock_file.assert_called_with(
                        os.path.join(str(output_dir), "documentation.html"),
                        "w",
                        encoding="utf-8"
                    )
                    mock_file().write.assert_called_with("<html>Test</html>")

def test_generate_documentation_no_files(generator, tmp_path):
    """Test documentation generation with no Python files."""
    source_dir = tmp_path / "empty"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    generator.analyzer.analyze_directory.return_value = []
    
    with pytest.raises(DocumentationError) as exc_info:
        generator.generate_documentation(str(source_dir), str(output_dir))
    assert "No files could be successfully analyzed" in str(exc_info.value)

def test_generate_documentation_with_errors(generator, tmp_path):
    """Test documentation generation with various errors."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    # Test analyzer error
    generator.analyzer.analyze_directory.side_effect = Exception("Analysis failed")
    with pytest.raises(DocumentationError) as exc_info:
        generator.generate_documentation(str(source_dir), str(output_dir))
    assert "Failed to generate documentation" in str(exc_info.value)
    
    # Test diagram generation error
    generator.analyzer.analyze_directory.side_effect = None
    generator.diagram_generator.generate_architecture_diagram.side_effect = Exception("Diagram failed")
    with pytest.raises(DocumentationError) as exc_info:
        generator.generate_documentation(str(source_dir), str(output_dir))
    assert "Failed to generate documentation" in str(exc_info.value)

def test_generate_html_documentation(generator, tmp_path):
    """Test HTML documentation generation."""
    output_dir = tmp_path / "docs"
    output_dir.mkdir()
    
    documentation = {
        'title': 'Test Documentation',
        'generated_date': '2024-03-14 12:00:00',
        'sections': [
            {
                'title': 'Overview',
                'content': 'Test content'
            }
        ]
    }
    
    diagrams = {
        'architecture': 'graph TD\n    A-->B',
        'class_diagram': 'classDiagram\n    class Test'
    }
    
    with patch("docgen.core.generator.get_documentation_template") as mock_template:
        mock_template.return_value.render.return_value = "<html>Test</html>"
        with patch("builtins.open", mock_open()) as mock_file:
            generator._generate_html_documentation(documentation, diagrams, str(output_dir))
            
            # Verify template rendering
            mock_template.return_value.render.assert_called_with(
                documentation=documentation,
                diagrams=diagrams
            )
            
            # Verify file writing
            mock_file.assert_called_with(
                os.path.join(str(output_dir), "documentation.html"),
                "w",
                encoding="utf-8"
            )
            mock_file().write.assert_called_with("<html>Test</html>")

def test_generate_html_documentation_error(generator, tmp_path):
    """Test HTML documentation generation errors."""
    output_dir = tmp_path / "docs"
    output_dir.mkdir()
    
    with patch("docgen.core.generator.get_documentation_template") as mock_template:
        # Test template rendering error
        mock_template.return_value.render.side_effect = Exception("Template error")
        with pytest.raises(DocumentationError) as exc_info:
            generator._generate_html_documentation({}, {}, str(output_dir))
        assert "Failed to generate HTML documentation" in str(exc_info.value)
        
        # Test file writing error
        mock_template.return_value.render.side_effect = None
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = Exception("File error")
            with pytest.raises(DocumentationError) as exc_info:
                generator._generate_html_documentation({}, {}, str(output_dir))
            assert "Failed to generate HTML documentation" in str(exc_info.value)

def test_documentation_content_structure(generator, tmp_path):
    """Test the structure of generated documentation content."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    # Create a mock QA chain that returns structured content
    mock_qa_chain = Mock()
    mock_qa_chain.run.return_value = """
    # Section Title
    
    - Point 1
    - Point 2
    
    ## Subsection
    
    Example code:
    ```python
    def test():
        pass
    ```
    """
    
    with patch("docgen.core.generator.Chroma"):
        with patch("docgen.core.generator.RetrievalQA") as mock_qa:
            mock_qa.from_chain_type.return_value = mock_qa_chain
            with patch("docgen.core.generator.get_documentation_template") as mock_template:
                with patch("builtins.open", mock_open()):
                    generator.generate_documentation(str(source_dir), str(output_dir))
                    
                    # Verify QA chain was called for each section
                    assert mock_qa_chain.run.call_count == 5  # Number of documentation sections
                    
                    # Verify template received structured content
                    template_args = mock_template.return_value.render.call_args[1]
                    assert 'documentation' in template_args
                    assert 'sections' in template_args['documentation']
                    assert len(template_args['documentation']['sections']) == 5 