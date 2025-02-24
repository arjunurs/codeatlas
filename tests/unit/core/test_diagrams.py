"""Unit tests for the DiagramGenerator class.

This module contains comprehensive tests for diagram generation functionality,
including architecture, class, sequence, dependency, and function call diagrams.
"""

import pytest
from docgen.core.diagrams import DiagramGenerator
from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis
from docgen.exceptions.errors import DiagramGenerationError

@pytest.fixture
def diagram_generator():
    """Create a DiagramGenerator instance for testing."""
    return DiagramGenerator()

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
                    lineno=1,
                    type="class",
                    methods=["method1", "method2"],
                    parent_class="BaseClass",
                    file_path="/path/to/module1.py"
                ),
                CodeEntity(
                    name="function1",
                    docstring="First test function",
                    lineno=10,
                    type="function",
                    file_path="/path/to/module1.py"
                )
            ],
            imports=["os", "module2.Class2"],
            content="",
            _skip_validation=True
        ),
        FileAnalysis(
            file_path="/path/to/module2.py",
            entities=[
                CodeEntity(
                    name="Class2",
                    docstring="Second test class",
                    lineno=1,
                    type="class",
                    methods=["method3"],
                    file_path="/path/to/module2.py"
                )
            ],
            imports=["module1.Class1"],
            content="",
            _skip_validation=True
        )
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
    assert "Class1" in diagram
    assert "Class2" in diagram
    assert "method1" in diagram
    assert "method2" in diagram
    assert "method3" in diagram
    assert "BaseClass" in diagram
    assert "<|--" in diagram  # Should show inheritance

def test_generate_sequence_diagram(diagram_generator, sample_analyses):
    """Test sequence diagram generation."""
    diagram = diagram_generator.generate_sequence_diagram(sample_analyses)
    
    # Verify diagram structure
    assert diagram.startswith("sequenceDiagram")
    assert "participant" in diagram
    assert "Class1" in diagram
    assert "Class2" in diagram

def test_generate_dependency_diagram(diagram_generator):
    """Test dependency diagram generation."""
    dependencies = {
        "package1": {"dep1", "dep2"},
        "package2": {"dep3"}
    }
    
    diagram = diagram_generator.generate_dependency_diagram(dependencies)
    
    # Verify diagram structure
    assert diagram.startswith("graph TD")
    assert "package1" in diagram
    assert "package2" in diagram
    assert "dep1" in diagram
    assert "dep2" in diagram
    assert "dep3" in diagram
    assert "-->" in diagram  # Should have dependency arrows

def test_generate_call_graph_diagram(diagram_generator):
    """Test function call graph diagram generation."""
    call_graph = {
        "main": {"helper1", "helper2"},
        "helper1": {"helper3"},
        "helper2": set(),
        "helper3": set()
    }
    
    diagram = diagram_generator.generate_call_graph_diagram(call_graph)
    
    # Verify diagram structure
    assert diagram.startswith("graph TD")
    assert "main" in diagram
    assert "helper1" in diagram
    assert "helper2" in diagram
    assert "-->" in diagram  # Should have call arrows

def test_generate_call_graph_diagram_with_limit(diagram_generator):
    """Test function call graph diagram with node limit."""
    # Create more than MAX_NODES functions
    call_graph = {f"func{i}": {f"func{i+1}"} for i in range(100)}
    
    diagram = diagram_generator.generate_call_graph_diagram(call_graph)
    
    # Verify diagram respects node limit
    assert "Note: Showing top" in diagram
    assert diagram.count("func") <= 50  # MAX_NODES constant from DiagramGenerator

def test_clean_names_in_diagrams(diagram_generator):
    """Test name cleaning in diagrams."""
    dependencies = {
        "package-name": {"dep.name", "@scope/name"}
    }
    
    diagram = diagram_generator.generate_dependency_diagram(dependencies)
    
    # Verify special characters are handled
    assert "package-name" not in diagram  # Should be replaced with package_name
    assert "dep.name" not in diagram  # Should be replaced with dep_name
    assert "@scope/name" not in diagram  # Should be replaced with at_scope_name

def test_empty_inputs(diagram_generator):
    """Test diagram generation with empty inputs."""
    # Empty analyses
    arch_diagram = diagram_generator.generate_architecture_diagram([])
    assert arch_diagram.startswith("graph TD")
    
    # Empty dependencies
    dep_diagram = diagram_generator.generate_dependency_diagram({})
    assert dep_diagram.startswith("graph TD")
    
    # Empty call graph
    call_diagram = diagram_generator.generate_call_graph_diagram({})
    assert call_diagram.startswith("graph TD")

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
        diagram_generator.generate_call_graph_diagram(None)

def test_sequence_diagram_no_interactions(diagram_generator):
    """Test sequence diagram generation with no clear interactions."""
    analyses = [
        FileAnalysis(
            file_path="test.py",
            entities=[
                CodeEntity(
                    name="Class1",
                    docstring="Test class",
                    lineno=1,
                    type="class",
                    methods=["standalone_method"],
                    file_path="test.py"
                )
            ],
            imports=[],
            content="",
            _skip_validation=True
        )
    ]
    
    diagram = diagram_generator.generate_sequence_diagram(analyses)
    assert "No clear interactions detected" in diagram 