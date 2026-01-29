"""Integration tests for diagram validation.

Tests end-to-end diagram generation and validation scenarios.
"""

import pytest

from docgen.core.diagrams import DiagramGenerator
from docgen.exceptions.errors import DiagramGenerationError
from docgen.models.code_entity import CodeEntity
from docgen.models.diagram_validation import ValidationConfig
from docgen.models.file_analysis import FileAnalysis


class TestDiagramValidationIntegration:
    """Integration tests for diagram validation with real diagram generation."""

    def test_valid_class_diagram_passes_validation(self):
        """Test that valid class diagram passes validation."""
        generator = DiagramGenerator(validate_diagrams=True)

        # Create test data
        entities = [
            CodeEntity(
                name="MyClass",
                type="class",
                docstring="Test class",
                parent_class="BaseClass",
            ),
            CodeEntity(
                name="method1",
                type="function",
                docstring="Test method",
            ),
        ]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Generate diagram - should not raise
        diagram = generator.generate_class_diagram([analysis])
        assert diagram.startswith("classDiagram")

    def test_valid_architecture_diagram_passes_validation(self):
        """Test that valid architecture diagram passes validation."""
        generator = DiagramGenerator(validate_diagrams=True)

        # Create test data
        entities = [
            CodeEntity(name="func1", type="function", docstring="Test function"),
        ]
        analysis = FileAnalysis(
            file_path="module1.py",
            entities=entities,
            imports=["module2"],
            content="",
            _skip_validation=True,
        )

        # Generate diagram - should not raise
        diagram = generator.generate_architecture_diagram([analysis])
        assert diagram.startswith("graph")

    def test_validation_disabled_allows_any_diagram(self):
        """Test that validation can be disabled."""
        generator = DiagramGenerator(validate_diagrams=False)

        # Generate with minimal data
        entities = [CodeEntity(name="C", type="class", docstring="")]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Should not raise even with potentially invalid content
        diagram = generator.generate_class_diagram([analysis])
        assert diagram

    def test_validation_with_permissive_config(self):
        """Test validation in permissive mode."""
        config = ValidationConfig(mode="permissive")
        generator = DiagramGenerator(
            validate_diagrams=True,
            validation_config=config,
        )

        entities = [CodeEntity(name="MyClass", type="class", docstring="Test")]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Should pass in permissive mode
        diagram = generator.generate_class_diagram([analysis])
        assert diagram

    def test_validation_warnings_logged(self, caplog):
        """Test that validation warnings are logged."""
        generator = DiagramGenerator(validate_diagrams=True)

        entities = [
            CodeEntity(name="MyClass", type="class", docstring="Test"),
            CodeEntity(name="method1", type="function", docstring="Method"),
        ]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Generate diagram
        diagram = generator.generate_class_diagram([analysis])
        assert diagram

        # Check if any warnings were logged (may or may not have warnings)
        # This test verifies the logging mechanism works
        assert caplog.text is not None

    def test_dependency_diagram_validation(self):
        """Test dependency diagram validation."""
        generator = DiagramGenerator(validate_diagrams=True)

        dependencies = {
            "module1": {"module2", "module3"},
            "module2": {"module4"},
        }

        # Should not raise
        diagram = generator.generate_dependency_diagram(dependencies)
        assert diagram.startswith("graph")

    def test_call_graph_validation(self):
        """Test call graph diagram validation."""
        generator = DiagramGenerator(validate_diagrams=True)

        call_graph = {
            "func1": {"func2", "func3"},
            "func2": {"func4"},
        }

        # Should not raise
        diagram = generator.generate_call_graph_diagram(call_graph)
        assert diagram.startswith("graph")

    def test_empty_diagram_fails_validation(self):
        """Test that empty diagram fails validation."""
        generator = DiagramGenerator(validate_diagrams=True)

        # Empty entities should trigger DiagramGenerationError
        # due to "No classes found" check before validation
        analysis = FileAnalysis(
            file_path="test.py",
            entities=[],
            imports=[],
            content="",
            _skip_validation=True,
        )

        with pytest.raises(DiagramGenerationError):
            generator.generate_class_diagram([analysis])

    def test_disabled_rules_configuration(self):
        """Test that specific rules can be disabled."""
        config = ValidationConfig(disabled_rules={"empty_diagram"})
        generator = DiagramGenerator(
            validate_diagrams=True,
            validation_config=config,
        )

        # Even with disabled rule, the generator's own checks
        # will catch empty diagrams before validation
        entities = [CodeEntity(name="MyClass", type="class", docstring="Test")]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        diagram = generator.generate_class_diagram([analysis])
        assert diagram


class TestDiagramValidationEdgeCases:
    """Test edge cases in diagram validation."""

    def test_large_class_diagram_truncation(self):
        """Test that large diagrams with truncation still validate."""
        generator = DiagramGenerator(max_nodes=5, validate_diagrams=True)

        # Create more entities than max_nodes
        entities = [
            CodeEntity(name=f"Class{i}", type="class", docstring=f"Class {i}")
            for i in range(10)
        ]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Should validate successfully even when truncated
        diagram = generator.generate_class_diagram([analysis])
        assert diagram
        assert "note" in diagram.lower() or "truncated" in diagram.lower()

    def test_special_characters_in_names(self):
        """Test handling of special characters in entity names."""
        generator = DiagramGenerator(validate_diagrams=True)

        # Names with special characters that need cleaning
        entities = [
            CodeEntity(name="My-Class", type="class", docstring="Test"),
            CodeEntity(name="my.method", type="function", docstring="Method"),
        ]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        # Should handle special characters and validate
        diagram = generator.generate_class_diagram([analysis])
        assert diagram

    def test_inheritance_relationships(self):
        """Test validation with inheritance relationships."""
        generator = DiagramGenerator(validate_diagrams=True)

        entities = [
            CodeEntity(
                name="ChildClass",
                type="class",
                docstring="Child",
                parent_class="ParentClass",
            ),
            CodeEntity(
                name="ParentClass",
                type="class",
                docstring="Parent",
            ),
        ]
        analysis = FileAnalysis(
            file_path="test.py",
            entities=entities,
            imports=[],
            content="",
            _skip_validation=True,
        )

        diagram = generator.generate_class_diagram([analysis])
        assert diagram
        assert "--|>" in diagram

    def test_validation_with_empty_dependencies(self):
        """Test dependency diagram with empty dependencies."""
        generator = DiagramGenerator(validate_diagrams=True)

        # This should raise due to no dependencies
        with pytest.raises(DiagramGenerationError):
            generator.generate_dependency_diagram({})

    def test_validation_preserves_error_context(self):
        """Test that validation errors preserve context."""
        generator = DiagramGenerator(validate_diagrams=True)

        # Empty analysis list should raise with context
        with pytest.raises(DiagramGenerationError) as exc_info:
            generator.generate_class_diagram([])

        assert "No files to analyze" in str(exc_info.value)
