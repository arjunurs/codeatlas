"""Unit tests for the CodeDocumentationGenerator class.

This module contains comprehensive tests for the documentation generation process,
including initialization, file analysis, and HTML generation.
"""

import logging
import os
from dataclasses import replace
from unittest.mock import MagicMock, Mock, patch

import pytest

from docgen.config import DEFAULT_CONFIG, GenerationOptions
from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import CodeParseError, DocumentationError
from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis


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
                    file_path="/path/to/test.py",
                )
            ],
            imports=["os"],
            content='"""File docstring."""\n\nclass TestClass:\n    pass',
            _skip_validation=True,
        )
    ]
    return mock


@pytest.fixture
def mock_diagram_generator():
    """Create a mock DiagramGenerator."""
    mock = Mock()
    mock.generate_architecture_diagram.return_value = (
        "graph TD\n    A[A]\n    B[B]\n    A --> B"
    )
    mock.generate_class_diagram.return_value = (
        "classDiagram\n    class Test {\n        +method()\n    }"
    )
    mock.generate_sequence_diagram.return_value = (
        "sequenceDiagram\n    A->>+B: call()\n    B-->>-A: return"
    )
    mock.generate_dependency_diagram.return_value = (
        "graph LR\n    pkg1[pkg1]\n    pkg2[pkg2]\n    pkg1 --> pkg2"
    )
    mock.generate_call_graph_diagram.return_value = (
        "graph TD\n    func1[func1]\n    func2[func2]\n    func1 --> func2"
    )
    return mock


@pytest.fixture
def mock_template_manager():
    """Create a mock TemplateManager."""
    mock = Mock()
    mock.render_template = Mock()
    mock.templates = {
        "navigation": Mock(render=Mock(return_value="<nav>Test Navigation</nav>"))
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
        methods=["test_method"],
    )
    sample_analysis = FileAnalysis(
        file_path="test.py",
        entities=[sample_entity],
        imports=["os", "sys"],
        content="class TestClass:\n    def test_method(self):\n        pass",
        _skip_validation=True,
    )

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
    ):
        # Set up mock return values
        mock_analyzer.analyze_directory.return_value = [sample_analysis]

        generator = CodeDocumentationGenerator(
            llm_provider=MagicMock(model_name="claude-sonnet-5"),
            embedding_provider=MagicMock(model_name="text-embedding-3-small"),
        )
        generator.analyzer = mock_analyzer
        generator.diagram_generator = mock_diagram_generator
        generator.template_manager = mock_template_manager
        yield generator


@pytest.fixture
def mock_generator():
    """Create a mock generator with test data."""
    generator = CodeDocumentationGenerator(
        llm_provider=MagicMock(model_name="claude-sonnet-5"),
        embedding_provider=MagicMock(model_name="text-embedding-3-small"),
    )

    # Create sample test data
    sample_entity = CodeEntity(
        name="TestClass",
        type="class",
        docstring="Test class docstring",
        methods=["test_method"],
        start_line=1,
        end_line=2,
        source="class TestClass:\n    pass",
    )

    sample_analysis = FileAnalysis(
        file_path="test.py",
        entities=[sample_entity],
        imports=["import os"],
        content="class TestClass:\n    pass",
        error=None,
        _skip_validation=True,
    )

    # Setup mocks
    generator.analyzer = MagicMock()
    generator.diagram_generator = MagicMock()
    generator.analyzer.analyze_directory.return_value = [sample_analysis]

    return generator


def test_generate_documentation_invalid_directory(mock_generator):
    """Test documentation generation with invalid directory."""
    with pytest.raises(ValueError, match="Invalid source directory"):
        mock_generator.generate_documentation("nonexistent", "docs")


def test_generate_documentation_success(generator, tmp_path):
    """Test successful documentation generation."""
    output_dir = tmp_path / "docs"

    # Create a mock RAG chain that returns strings directly (as LCEL chains do after StrOutputParser)
    mock_rag_chain = Mock()
    mock_rag_chain.invoke.return_value = "Generated content"

    with patch.object(
        generator, "_create_vector_store_and_rag_chain", return_value=mock_rag_chain
    ):
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
            "index.html",
            "sections/overview.html",
            "sections/dependencies.html",
            "sections/key_classes_and_functions.html",
            "sections/data_flow.html",
            "sections/integration_points.html",
            "diagrams/architecture.html",
            "diagrams/dependencies.html",
            "diagrams/classes.html",
            "diagrams/sequence.html",
            "diagrams/call_graph.html",
            "search.html",
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


def test_unexpected_error_propagates_unchanged(mock_generator, tmp_path):
    """An error that is not codeatlas's own is not disguised as one."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"

    mock_generator.analyzer.analyze_directory.side_effect = RuntimeError(
        "Analysis failed"
    )

    with pytest.raises(RuntimeError, match=r"^Analysis failed$"):
        mock_generator.generate_documentation(str(source_dir), str(output_dir))


def test_documentation_error_propagates_unchanged(generator, tmp_path):
    """A codeatlas error reaches the caller without another prefix."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"

    generator.analyzer.analyze_directory.side_effect = CodeParseError("Analysis failed")

    with pytest.raises(CodeParseError, match=r"^Analysis failed$"):
        generator.generate_documentation(str(source_dir), str(output_dir))


def test_documentation_content_structure(generator, tmp_path):
    """Test the structure of generated documentation content."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "docs"

    # Track RAG chain invocations
    invocation_count = 0

    def mock_rag_invoke(prompt, config=None):
        nonlocal invocation_count
        invocation_count += 1
        # Return string directly (as LCEL chains do after StrOutputParser)
        return """
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

    mock_rag_chain = Mock()
    mock_rag_chain.invoke.side_effect = mock_rag_invoke

    with patch.object(
        generator, "_create_vector_store_and_rag_chain", return_value=mock_rag_chain
    ):
        generator.generate_documentation(str(source_dir), str(output_dir))

        # Verify RAG chain was invoked for each section (5 sections)
        assert invocation_count == 5

        # Verify template received structured content
        render_calls = generator.template_manager.render_template.call_args_list

        # Find the index page call
        index_call = None
        for call in render_calls:
            args = call[0]  # Positional arguments
            if (
                len(args) >= 4 and args[3] == "index.html"
            ):  # Check filename in fourth position
                index_call = call
                break

        assert index_call is not None, "Index page template call not found"
        context = index_call[0][1]  # Context is in the second position of args
        assert "documentation" in context
        assert "sections" in context["documentation"]
        assert len(context["documentation"]["sections"]) == 5


@pytest.mark.parametrize(
    ("selection", "expected_file"),
    [
        (["overview"], "overview.html"),
        (["code_quality"], "code_quality_insights.html"),
    ],
)
def test_dry_run_writes_only_selected_sections(
    temp_source_dir, tmp_path, selection, expected_file
):
    """A dry run matches --sections the same way as a real run."""
    output_dir = tmp_path / "docs"
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(
            skip_diagrams=True, selected_sections=selection, dry_run=True
        ),
    )

    generator.generate_documentation(str(temp_source_dir), str(output_dir))

    section_files = sorted(p.name for p in (output_dir / "sections").iterdir())
    assert section_files == [expected_file]


def test_unknown_section_rejected_at_construction():
    """A misspelled section name fails before any analysis or API call."""
    with pytest.raises(ValueError, match="overveiw"):
        CodeDocumentationGenerator(
            llm_provider=MagicMock(),
            embedding_provider=MagicMock(),
            generation_options=GenerationOptions(selected_sections=["overveiw"]),
        )


def test_unknown_diagram_rejected_at_construction():
    """A misspelled diagram name fails before any analysis or API call."""
    with pytest.raises(ValueError, match="clas"):
        CodeDocumentationGenerator(
            llm_provider=MagicMock(),
            embedding_provider=MagicMock(),
            generation_options=GenerationOptions(selected_diagrams=["clas"]),
        )


def test_diagram_selection_ignores_case():
    """--diagrams Class generates the class diagram and nothing else."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(
            selected_diagrams=["Class"], diagrams_only=True
        ),
    )
    generator.diagram_generator = MagicMock()
    generator.diagram_generator.generate_class_diagram.return_value = "classDiagram"

    diagrams, errors = generator._generate_all_diagrams([])

    assert diagrams == {"class_diagram": "classDiagram"}
    assert errors == []


def test_failed_diagram_is_reported_as_warning(temp_source_dir, tmp_path, caplog):
    """A diagram that fails to generate is reported on the console, not only in HTML."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(
            selected_diagrams=["class", "architecture"], diagrams_only=True
        ),
    )
    generator.diagram_generator = MagicMock()
    generator.diagram_generator.generate_class_diagram.side_effect = DocumentationError(
        "no classes found"
    )
    generator.diagram_generator.generate_architecture_diagram.return_value = "graph TD"

    with caplog.at_level(logging.WARNING, logger="docgen"):
        generator.generate_documentation(str(temp_source_dir), str(tmp_path / "docs"))

    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("docgen") and r.levelno == logging.WARNING
    ]
    assert warnings == ["1 of 2 diagrams failed:\n  - class_diagram: no classes found"]


def test_diagrams_only_run_fails_when_every_diagram_fails(temp_source_dir, tmp_path):
    """A diagrams-only run with no diagram fails, after writing its pages."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(
            selected_diagrams=["class"], diagrams_only=True
        ),
    )
    generator.diagram_generator = MagicMock()
    generator.diagram_generator.generate_class_diagram.side_effect = DocumentationError(
        "no classes found"
    )

    with pytest.raises(
        DocumentationError, match=r"^No diagram could be generated: no classes found$"
    ):
        generator.generate_documentation(str(temp_source_dir), str(tmp_path / "docs"))

    assert (tmp_path / "docs" / "index.html").exists()


def test_full_run_succeeds_when_only_diagrams_fail(temp_source_dir, tmp_path):
    """Diagrams are extra in a run that writes sections, so losing them all is a warning."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(selected_diagrams=["class"], dry_run=True),
    )
    generator.diagram_generator = MagicMock()
    generator.diagram_generator.generate_class_diagram.side_effect = DocumentationError(
        "no classes found"
    )

    generator.generate_documentation(str(temp_source_dir), str(tmp_path / "docs"))

    assert (tmp_path / "docs" / "index.html").exists()


def test_no_files_error_is_left_to_the_caller_to_log(mock_generator, tmp_path, caplog):
    """The generator raises the error without also logging it."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    mock_generator.analyzer.analyze_directory.return_value = []

    with (
        caplog.at_level(logging.DEBUG, logger="docgen"),
        pytest.raises(DocumentationError, match="No Python files found"),
    ):
        mock_generator.generate_documentation(str(source_dir), str(tmp_path / "docs"))

    problems = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [r for r in problems if r.name.startswith("docgen")] == []


def test_diagram_node_limit_comes_from_the_config():
    """MAX_DIAGRAM_NODES in the config sets the diagram generator's node limit."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(diagrams_only=True),
        config=replace(DEFAULT_CONFIG, MAX_DIAGRAM_NODES=7),
    )

    assert generator.diagram_generator.max_nodes == 7


def _diagrams_only_generator():
    """A diagrams-only generator whose analyzer and diagram generator are mocks."""
    generator = CodeDocumentationGenerator(
        generation_options=GenerationOptions(diagrams_only=True)
    )
    generator.analyzer = MagicMock()
    generator.diagram_generator = MagicMock()
    for method in (
        "generate_architecture_diagram",
        "generate_class_diagram",
        "generate_sequence_diagram",
        "generate_call_graph_diagram",
        "generate_dependency_diagram",
    ):
        getattr(generator.diagram_generator, method).return_value = method
    return generator


def test_failed_call_analysis_is_reported_for_each_diagram_that_needs_it():
    """The sequence and call graph diagrams fail; the others are still built."""
    generator = _diagrams_only_generator()
    generator.analyzer.analyze_function_calls.side_effect = RuntimeError("bad calls")

    diagrams, errors = generator._generate_all_diagrams([])

    assert set(diagrams) == {"architecture", "class_diagram", "package_dependencies"}
    assert errors == [
        ("sequence", "RuntimeError: bad calls"),
        ("function_calls", "RuntimeError: bad calls"),
    ]


def test_call_analysis_runs_once_for_both_diagrams_that_use_it():
    """The sequence and call graph diagrams share one function call analysis."""
    generator = _diagrams_only_generator()

    diagrams, errors = generator._generate_all_diagrams([])

    assert errors == []
    assert len(diagrams) == 5
    generator.analyzer.analyze_function_calls.assert_called_once()
