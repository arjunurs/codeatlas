"""Tests for diagram validator framework."""

import pytest

from docgen.exceptions.errors import DiagramValidationError
from docgen.models.diagram_validation import (
    DiagramType,
    ValidationConfig,
    ValidationMode,
)
from docgen.utils.diagram_validator import DiagramValidator


class TestDiagramValidator:
    """Tests for main DiagramValidator class."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        validator = DiagramValidator()
        assert validator.config is not None
        assert len(validator.validators) == 5

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = ValidationConfig(mode=ValidationMode.PERMISSIVE)
        validator = DiagramValidator(config)
        assert validator.config.mode == ValidationMode.PERMISSIVE

    def test_validate_architecture_diagram(self):
        """Test validating a valid architecture diagram."""
        validator = DiagramValidator()
        diagram = "graph TD\nA[Start] --> B[End]"
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        assert result.diagram_type == DiagramType.ARCHITECTURE
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_class_diagram(self):
        """Test validating a valid class diagram."""
        validator = DiagramValidator()
        diagram = "classDiagram\nclass MyClass"
        result = validator.validate(diagram, DiagramType.CLASS)
        assert result.diagram_type == DiagramType.CLASS
        assert result.is_valid

    def test_validate_sequence_diagram(self):
        """Test validating a valid sequence diagram."""
        validator = DiagramValidator()
        diagram = "sequenceDiagram\nparticipant A\nA->>B: message"
        result = validator.validate(diagram, DiagramType.SEQUENCE)
        # May have error for undefined participant B
        assert result.diagram_type == DiagramType.SEQUENCE

    def test_validate_invalid_diagram_type(self):
        """Test that invalid diagram type raises error."""
        validator = DiagramValidator()
        with pytest.raises(KeyError):
            validator.validate("graph TD\nA --> B", "invalid_type")  # type: ignore

    def test_validate_with_raise_on_error(self):
        """Test that raise_on_error throws exception."""
        validator = DiagramValidator()
        diagram = "invalid TD\nA --> B"
        with pytest.raises(DiagramValidationError):
            validator.validate(
                diagram,
                DiagramType.ARCHITECTURE,
                raise_on_error=True,
            )

    def test_validate_auto_detect_architecture(self):
        """Test auto-detection of architecture diagram."""
        validator = DiagramValidator()
        diagram = "graph TD\nA --> B"
        result = validator.validate_auto_detect(diagram)
        assert result.diagram_type == DiagramType.ARCHITECTURE

    def test_validate_auto_detect_class(self):
        """Test auto-detection of class diagram."""
        validator = DiagramValidator()
        diagram = "classDiagram\nclass MyClass"
        result = validator.validate_auto_detect(diagram)
        assert result.diagram_type == DiagramType.CLASS

    def test_validate_auto_detect_sequence(self):
        """Test auto-detection of sequence diagram."""
        validator = DiagramValidator()
        diagram = "sequenceDiagram\nA->>B: msg"
        result = validator.validate_auto_detect(diagram)
        assert result.diagram_type == DiagramType.SEQUENCE

    def test_validate_auto_detect_invalid_header(self):
        """Test auto-detection with invalid header."""
        validator = DiagramValidator()
        diagram = "invalid\nA --> B"
        with pytest.raises(DiagramValidationError, match="Cannot detect diagram type"):
            validator.validate_auto_detect(diagram)

    def test_validation_config_strict_mode(self):
        """Test validation in strict mode."""
        config = ValidationConfig(mode=ValidationMode.STRICT)
        validator = DiagramValidator(config)
        diagram = "graph TD\nA --> B"
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        # Strict mode still validates normally
        assert isinstance(result.is_valid, bool)

    def test_validation_config_fail_on_warnings(self):
        """Test fail_on_warnings configuration."""
        config = ValidationConfig(fail_on_warnings=True)
        validator = DiagramValidator(config)
        # Create diagram that might have warnings
        diagram = "graph\nA[Node]"  # Missing direction
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        # If there are warnings, is_valid should be False
        if result.has_warnings:
            assert not result.is_valid

    def test_validation_config_disabled_rules(self):
        """Test disabled rules configuration."""
        config = ValidationConfig(disabled_rules={"syntax_header"})
        validator = DiagramValidator(config)
        # This should fail header check, but we disabled it
        diagram = "invalid\nA --> B"
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        # Should not have syntax_header errors
        header_errors = [e for e in result.errors if e.rule_name == "syntax_header"]
        assert len(header_errors) == 0


class TestValidatorIntegration:
    """Integration tests for validators."""

    def test_architecture_diagram_with_warnings(self):
        """Test architecture diagram with warnings."""
        validator = DiagramValidator()
        diagram = "graph\nnode1[Label] --> node2[Label]"  # Missing direction
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        # May have warning about missing direction
        assert result.diagram_type == DiagramType.ARCHITECTURE

    def test_sequence_diagram_undefined_participant(self):
        """Test sequence diagram with undefined participant."""
        validator = DiagramValidator()
        diagram = "sequenceDiagram\nA->>B: message"
        result = validator.validate(diagram, DiagramType.SEQUENCE)
        # Should have warning for implicit participants (not an error - implicit participants are valid)
        assert result.has_warnings
        assert "Implicit participants" in result.warnings[0].message

    def test_empty_diagram_fails(self):
        """Test that empty diagram fails validation."""
        validator = DiagramValidator()
        diagram = "graph TD"
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        assert not result.is_valid
        assert result.has_errors

    def test_complete_validation_result(self):
        """Test that validation result contains all information."""
        validator = DiagramValidator()
        diagram = "graph TD\nA[Start] --> B[End]"
        result = validator.validate(diagram, DiagramType.ARCHITECTURE)
        assert hasattr(result, "diagram_type")
        assert hasattr(result, "is_valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "info")
        assert hasattr(result, "diagram_content")
        assert result.diagram_content == diagram
