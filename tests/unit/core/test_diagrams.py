"""Unit tests for the DiagramGenerator class.

This module contains comprehensive tests for diagram generation functionality,
including architecture, class, sequence, dependency, and function call diagrams.
"""

import pytest

from docgen.core.diagrams import DiagramGenerator
from docgen.exceptions.errors import DiagramGenerationError
from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis


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
                    type="class",
                    methods=["method1", "method2"],
                    start_line=1,
                    end_line=5,
                    source="class Class1:\n    def method1(self):\n        pass\n    def method2(self):\n        pass",
                    parent_class="BaseClass",
                ),
                CodeEntity(
                    name="function1",
                    docstring="First test function",
                    type="function",
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
                    type="class",
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
    call_graph = {f"func{i}": {f"func{i+1}"} for i in range(100)}

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
    # Test with invalid analysis object
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_architecture_diagram([None])

    # Test with invalid dependencies
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_dependency_diagram(None)

    # Test with invalid call graph
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_sequence_diagram(None)


def test_sequence_diagram_no_interactions(diagram_generator):
    """Test sequence diagram generation with no clear interactions."""
    call_graph = {"func1": set()}

    with pytest.raises(
        DiagramGenerationError, match="No function calls found in call graph"
    ):
        diagram_generator.generate_sequence_diagram(call_graph)
