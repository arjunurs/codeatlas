"""Unit tests for the CodeDocumentationGenerator class.

This module contains comprehensive tests for the documentation generation process,
including initialization, file analysis, and HTML generation.
"""

import os
import pytest
from unittest.mock import patch, Mock, MagicMock, mock_open, call
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
    mock.generate_architecture_diagram.return_value = "graph TD\n    A[A]\n    B[B]\n    A --> B"
    mock.generate_class_diagram.return_value = "classDiagram\n    class Test {\n        +method()\n    }"
    mock.generate_sequence_diagram.return_value = "sequenceDiagram\n    A->>+B: call()\n    B-->>-A: return"
    mock.generate_dependency_diagram.return_value = "graph LR\n    pkg1[pkg1]\n    pkg2[pkg2]\n    pkg1 --> pkg2"
    mock.generate_call_graph_diagram.return_value = "graph TD\n    func1[func1]\n    func2[func2]\n    func1 --> func2"
    return mock

@pytest.fixture
def mock_template_manager():
    """Create a mock TemplateManager."""
    mock = Mock()
    mock.render_template = Mock()
    mock.templates = {
        'navigation': Mock(render=Mock(return_value="<nav>Test Navigation</nav>"))
    }
    
    # Set up render_template to store call arguments
    def store_call_args(*args, **kwargs):
        store_call_args.calls.append((args, kwargs))
    store_call_args.calls = []
    mock.render_template.side_effect = store_call_args
    
    return mock

@pytest.fixture
def generator(mock_template_manager):
    """Create a CodeDocumentationGenerator instance with mocked dependencies."""
    mock_llm = MagicMock()
    mock_embeddings = MagicMock()
    mock_analyzer = MagicMock()
    mock_diagram_generator = MagicMock()

    # Create a sample FileAnalysis for testing
    sample_entity = CodeEntity(
        name="TestClass",
        type="class",
        docstring="Test class",
        start_line=1,
        end_line=5,
        source="class TestClass:\n    def test_method(self):\n        pass",
        methods=["test_method"]
    )
    sample_analysis = FileAnalysis(
        file_path="test.py",
        entities=[sample_entity],
        imports=["os", "sys"],
        content="class TestClass:\n    def test_method(self):\n        pass",
        _skip_validation=True
    )

    with patch('docgen.core.generator.ChatAnthropic', return_value=mock_llm), \
         patch('docgen.core.generator.OpenAIEmbeddings', return_value=mock_embeddings), \
         patch('docgen.core.generator.CodeAnalyzer', return_value=mock_analyzer), \
         patch('docgen.core.generator.DiagramGenerator', return_value=mock_diagram_generator), \
         patch('docgen.core.generator.get_template_manager', return_value=mock_template_manager):
        
        # Set up mock return values
        mock_analyzer.analyze_directory.return_value = [sample_analysis]
        mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
        
        generator = CodeDocumentationGenerator(
            anthropic_api_key="test-anthropic",
            openai_api_key="test-openai"
        )
        generator.analyzer = mock_analyzer
        generator.embeddings = mock_embeddings
        generator.llm = mock_llm
        generator.diagram_generator = mock_diagram_generator
        generator.template_manager = mock_template_manager
        yield generator

@pytest.fixture
def mock_generator():
    """Create a mock generator with test data."""
    generator = CodeDocumentationGenerator(
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key"
    )
    
    # Create sample test data
    sample_entity = CodeEntity(
        name="TestClass",
        type="class",
        docstring="Test class docstring",
        methods=["test_method"],
        start_line=1,
        end_line=2,
        source="class TestClass:\n    pass"
    )
    
    sample_analysis = FileAnalysis(
        file_path="test.py",
        entities=[sample_entity],
        imports=["import os"],
        content="class TestClass:\n    pass",
        error=None,
        _skip_validation=True
    )
    
    # Setup mocks
    generator.analyzer = MagicMock()
    generator.embeddings = MagicMock()
    generator.diagram_generator = MagicMock()
    generator.analyzer.analyze_directory.return_value = [sample_analysis]
    
    return generator

def test_initialization():
    """Test generator initialization."""
    with pytest.raises(ValueError):
        CodeDocumentationGenerator(
            anthropic_api_key="test",
            openai_api_key="test",
            temperature=2.0  # Invalid temperature
        )

def test_generate_documentation_invalid_directory(mock_generator):
    """Test documentation generation with invalid directory."""
    with pytest.raises(ValueError, match="Invalid source directory"):
        mock_generator.generate_documentation("nonexistent", "docs")

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
            
            # Create source directory with a Python file
            source_dir = tmp_path / "src"
            source_dir.mkdir()
            (source_dir / "test.py").write_text("print('test')")
            
            # Generate documentation
            generator.generate_documentation(str(source_dir), str(output_dir))
            
            # Verify directory structure
            assert os.path.exists(output_dir / "sections")
            assert os.path.exists(output_dir / "diagrams")
            assert os.path.exists(output_dir / "assets")
            
            # Verify template calls
            render_calls = generator.template_manager.render_template.call_args_list
            expected_files = {
                'index.html',
                'sections/overview.html',
                'sections/dependencies.html',
                'sections/key_classes_and_functions.html',
                'sections/data_flow.html',
                'sections/integration_points.html',
                'diagrams/architecture.html',
                'diagrams/dependencies.html',
                'diagrams/classes.html',
                'diagrams/sequence.html',
                'diagrams/call_graph.html',
                'search.html'
            }
            
            # Extract filenames from call arguments
            actual_files = set()
            for call in render_calls:
                args = call[0]  # Positional arguments
                if len(args) >= 4:  # Check for filename in fourth position
                    filename = args[3]
                    if filename:
                        actual_files.add(filename)
            
            # Verify all expected files were generated
            missing_files = expected_files - actual_files
            assert not missing_files, f"Missing expected files: {missing_files}"

def test_generate_documentation_no_files(mock_generator, tmp_path):
    """Test documentation generation with no Python files."""
    source_dir = tmp_path / "empty"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    # Mock analyzer to return empty list
    mock_generator.analyzer.analyze_directory.return_value = []
    
    with pytest.raises(DocumentationError, match="No Python files found in directory"):
        mock_generator.generate_documentation(str(source_dir), str(output_dir))

def test_generate_documentation_analysis_error(mock_generator, tmp_path):
    """Test documentation generation with analysis error."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    # Mock analyzer to raise error
    mock_generator.analyzer.analyze_directory.side_effect = Exception("Analysis failed")
    
    with pytest.raises(DocumentationError, match="Failed to generate documentation: Analysis failed"):
        mock_generator.generate_documentation(str(source_dir), str(output_dir))

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

def test_generate_navigation(generator):
    """Test navigation generation."""
    sections = [
        {'title': 'Overview'},
        {'title': 'Dependencies'}
    ]
    
    nav_html = generator._generate_navigation('Overview', sections, './')
    assert isinstance(nav_html, str)
    assert generator.template_manager.templates['navigation'].render.called
    assert generator.template_manager.templates['navigation'].render.call_args[1]['active'] == 'Overview'
    assert generator.template_manager.templates['navigation'].render.call_args[1]['sections'] == ['Overview', 'Dependencies']
    assert generator.template_manager.templates['navigation'].render.call_args[1]['base_url'] == './'

def test_documentation_content_structure(generator, tmp_path):
    """Test the structure of generated documentation content."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"
    
    # Create a mock QA chain that returns structured content
    mock_qa_chain = Mock()
    mock_qa_chain.invoke.return_value = {"answer": """
    # Section Title
    
    - Point 1
    - Point 2
    
    ## Subsection
    
    Example code:
    ```python
    def test():
        pass
    ```
    """}
    
    with patch("docgen.core.generator.Chroma"):
        with patch("docgen.core.generator.RetrievalQA") as mock_qa:
            mock_qa.from_chain_type.return_value = mock_qa_chain
            generator.generate_documentation(str(source_dir), str(output_dir))
            
            # Verify QA chain was called for each section
            assert mock_qa_chain.invoke.call_count == 5  # Number of documentation sections
            
            # Verify template received structured content
            render_calls = generator.template_manager.render_template.call_args_list
            
            # Find the index page call
            index_call = None
            for call in render_calls:
                args = call[0]  # Positional arguments
                if len(args) >= 4 and args[3] == 'index.html':  # Check filename in fourth position
                    index_call = call
                    break
            
            assert index_call is not None, "Index page template call not found"
            context = index_call[0][1]  # Context is in the second position of args
            assert 'documentation' in context
            assert 'sections' in context['documentation']
            assert len(context['documentation']['sections']) == 5 