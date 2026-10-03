"""Unit tests for the DiagramGenerator class.

This module contains comprehensive tests for diagram generation functionality,
including architecture, class, sequence, dependency, and function call diagrams.
"""

from unittest.mock import MagicMock

import pytest

from docgen.core.diagrams import DiagramGenerator, select_diagrams
from docgen.exceptions.errors import DiagramGenerationError, DiagramValidationError
from docgen.models.code_entity import CodeEntity, EntityType
from docgen.models.diagram_validation import DiagramType
from docgen.models.file_analysis import FileAnalysis
from docgen.utils.diagram_validator import DiagramValidator


@pytest.fixture
def diagram_generator():
    """Create a DiagramGenerator instance for testing."""
    # Disable validation for tests to avoid issues with synthetic test data
    return DiagramGenerator(validate_diagrams=False)


@pytest.fixture
def sample_analyses():
    """Create sample FileAnalysis objects for testing."""
    return [
        FileAnalysis(
            file_path="/path/to/module1.py",
            entities=[
                CodeEntity(
                    name="Class1",
                    docstring="First test class",
                    type=EntityType.CLASS,
                    methods=["method1", "method2"],
                    start_line=1,
                    end_line=5,
                    source="class Class1:\n    def method1(self):\n        pass\n    def method2(self):\n        pass",
                    parent_class="BaseClass",
                ),
                CodeEntity(
                    name="function1",
                    docstring="First test function",
                    type=EntityType.FUNCTION,
                    start_line=10,
                    end_line=12,
                    source="def function1():\n    pass",
                ),
            ],
            imports=["os", "module2.Class2"],
            content="",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="/path/to/module2.py",
            entities=[
                CodeEntity(
                    name="Class2",
                    docstring="Second test class",
                    type=EntityType.CLASS,
                    methods=["method3"],
                    start_line=1,
                    end_line=3,
                    source="class Class2:\n    def method3(self):\n        pass",
                )
            ],
            imports=["module1.Class1"],
            content="",
            _skip_validation=True,
        ),
    ]


def test_generate_architecture_diagram(diagram_generator, sample_analyses):
    """Test architecture diagram generation."""
    diagram = diagram_generator.generate_architecture_diagram(sample_analyses)

    # Verify diagram structure
    assert diagram.startswith("graph TD")
    assert "module1" in diagram
    assert "module2" in diagram
    assert "-->" in diagram  # Should have at least one connection


def test_generate_class_diagram(diagram_generator, sample_analyses):
    """Test class diagram generation."""
    diagram = diagram_generator.generate_class_diagram(sample_analyses)

    # Verify diagram structure
    assert diagram.startswith("classDiagram")
    assert "class Class1" in diagram
    assert "class Class2" in diagram
    assert "Class1 --|> BaseClass" in diagram
    assert "+method1()" in diagram
    assert "+method2()" in diagram
    assert "+method3()" in diagram


def test_generate_sequence_diagram(diagram_generator):
    """Test sequence diagram generation."""
    call_graph = {"func1": {"func2", "func3"}, "func2": {"func4"}}

    diagram = diagram_generator.generate_sequence_diagram(call_graph)

    # Verify diagram structure
    assert diagram.startswith("sequenceDiagram")
    assert "func1->>+func2: call()" in diagram
    assert "func2-->>-func1: return" in diagram
    assert "func1->>+func3: call()" in diagram
    assert "func3-->>-func1: return" in diagram
    assert "func2->>+func4: call()" in diagram
    assert "func4-->>-func2: return" in diagram


def test_sequence_diagram_declares_participants(diagram_generator):
    """Participants are declared in first-use order, so validation is clean."""
    call_graph = {"cli.main": {"load"}, "load": {"parse"}}

    diagram = diagram_generator.generate_sequence_diagram(call_graph)

    assert diagram.splitlines()[1:4] == [
        "    participant cli_main",
        "    participant load",
        "    participant parse",
    ]
    result = DiagramValidator().validate(diagram, DiagramType.SEQUENCE)
    assert result.is_valid
    assert result.warnings == []


def test_generate_dependency_diagram(diagram_generator):
    """Test dependency diagram generation."""
    dependencies = {"package1": {"dep1", "dep2"}, "package2": {"dep3"}}

    diagram = diagram_generator.generate_dependency_diagram(dependencies)

    # Verify diagram structure
    assert diagram.startswith("graph LR")
    assert 'package1["package1"]' in diagram
    assert 'dep1["dep1"]' in diagram
    assert "package1 --> dep1" in diagram


def test_generate_call_graph_diagram(diagram_generator):
    """Test function call graph diagram generation."""
    call_graph = {
        "main": {"helper1", "helper2"},
        "helper1": {"helper3"},
        "helper2": set(),
        "helper3": set(),
    }

    diagram = diagram_generator.generate_call_graph_diagram(call_graph)

    # Verify diagram structure
    assert diagram.startswith("graph TD")
    assert 'main["main"]' in diagram
    assert 'helper1["helper1"]' in diagram
    assert 'helper2["helper2"]' in diagram
    assert "main --> helper1" in diagram
    assert "main --> helper2" in diagram
    assert "helper1 --> helper3" in diagram


def test_generate_call_graph_diagram_with_limit(diagram_generator):
    """Test function call graph diagram with node limit."""
    # Create more than MAX_NODES functions
    call_graph = {f"func{i}": {f"func{i + 1}"} for i in range(100)}

    diagram = diagram_generator.generate_call_graph_diagram(call_graph)

    # Verify diagram respects node limit
    assert "Diagram truncated: showing top" in diagram
    # Each function appears once in node definition and once in edge
    node_count = sum(
        1 for line in diagram.split("\n") if line.strip().startswith("func")
    )
    assert node_count <= diagram_generator.max_nodes * 2


def test_clean_names_in_diagrams(diagram_generator):
    """Test name cleaning in diagrams."""
    dependencies = {"package-name": {"dep.name", "@scope/name"}}

    diagram = diagram_generator.generate_dependency_diagram(dependencies)

    # Verify special characters are handled - node IDs are cleaned, labels are quoted
    assert 'package_name["package-name"]' in diagram
    assert 'dep_name["dep.name"]' in diagram
    assert 'scope_name["@scope/name"]' in diagram


def test_empty_inputs(diagram_generator):
    """Test diagram generation with empty inputs."""
    # Empty analyses
    with pytest.raises(DiagramGenerationError, match="No files to analyze"):
        diagram_generator.generate_class_diagram([])

    # Empty dependencies
    with pytest.raises(DiagramGenerationError, match="No dependencies to analyze"):
        diagram_generator.generate_dependency_diagram({})

    # Empty call graph
    with pytest.raises(DiagramGenerationError, match="Empty call graph"):
        diagram_generator.generate_sequence_diagram({})


def test_diagram_generation_error_handling(diagram_generator):
    """Test error handling in diagram generation."""
    # Test with invalid dependencies
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_dependency_diagram(None)

    # Test with invalid call graph
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_sequence_diagram(None)


@pytest.mark.parametrize(
    ("builder", "diagram_type", "make_input"),
    [
        ("generate_class_diagram", "class", lambda analyses: analyses),
        ("generate_architecture_diagram", "architecture", lambda analyses: analyses),
        ("generate_call_graph_diagram", "callgraph", lambda _: {"main": {"helper"}}),
    ],
)
def test_validation_failure_is_reported_once(
    sample_analyses, builder, diagram_type, make_input
):
    """A diagram that fails validation says so once, without a second prefix."""
    generator = DiagramGenerator(validate_diagrams=True)
    generator.validator = MagicMock()
    generator.validator.validate.side_effect = DiagramValidationError("bad syntax")

    with pytest.raises(
        DiagramGenerationError,
        match=f"^Generated {diagram_type} diagram failed validation: bad syntax$",
    ):
        getattr(generator, builder)(make_input(sample_analyses))


def test_sequence_diagram_no_interactions(diagram_generator):
    """Test sequence diagram generation with no clear interactions."""
    call_graph = {"func1": set()}

    with pytest.raises(
        DiagramGenerationError, match="No function calls found in call graph"
    ):
        diagram_generator.generate_sequence_diagram(call_graph)


ALL_DIAGRAMS = ["architecture", "class", "sequence", "callgraph", "dependency"]


@pytest.mark.parametrize("selection", [None, [], [""], ["", " "]])
def test_no_diagram_selection_returns_all(selection):
    """Without a selection, every diagram type is generated."""
    assert select_diagrams(selection) == ALL_DIAGRAMS


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (["class"], ["class"]),
        (["Class"], ["class"]),
        ([" CLASS "], ["class"]),
        (["class", ""], ["class"]),
        (["call_graph"], ["callgraph"]),
        (["call-graph"], ["callgraph"]),
        (["dependency", "architecture"], ["architecture", "dependency"]),
    ],
)
def test_diagram_selection_normalizes_names(selection, expected):
    """Names match case-insensitively, ignoring "_", "-", and blanks."""
    assert select_diagrams(selection) == expected


def test_unknown_diagram_raises_with_available_names():
    """A name that is not a diagram type is rejected, listing the valid names."""
    with pytest.raises(ValueError, match="Unknown diagram") as excinfo:
        select_diagrams(["class", "clas"])

    message = str(excinfo.value)
    assert "Unknown diagram(s): clas." in message
    assert "callgraph" in message


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AbstractAsyncContextManager[_T]", "AbstractAsyncContextManager"),
        ("Getter[Headers]", "Getter"),
        ("Sequence[Tuple[bytes, bytes]]", "Sequence"),
        ("typing.NamedTuple('Url', [('scheme', str)])", "typing_NamedTuple"),
        ("my pkg:mod", "my_pkg_mod"),
    ],
)
def test_clean_name_produces_identifier(name, expected):
    """Generic arguments and call arguments are dropped from node IDs."""
    assert DiagramGenerator._clean_name(name) == expected


def test_class_diagram_handles_generic_base_classes(diagram_generator):
    """Generic base classes do not leak brackets into the class diagram."""
    analyses = [
        FileAnalysis(
            file_path="/path/to/context.py",
            entities=[
                CodeEntity(
                    name="AsyncLiftContextManager",
                    docstring=None,
                    type=EntityType.CLASS,
                    parent_class="AbstractAsyncContextManager[_T]",
                ),
                CodeEntity(
                    name="HeadersGetter",
                    docstring=None,
                    type=EntityType.CLASS,
                    parent_class="Getter[Headers]",
                ),
            ],
            imports=[],
            content="",
            _skip_validation=True,
        )
    ]

    diagram = diagram_generator.generate_class_diagram(analyses)

    assert "AsyncLiftContextManager --|> AbstractAsyncContextManager" in diagram
    assert "HeadersGetter --|> Getter" in diagram
    assert "[" not in diagram
