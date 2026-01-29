"""Tests for diagram validation data models."""

import pytest

from docgen.models.diagram_validation import (
    DiagramType,
    ValidationConfig,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
)


class TestDiagramType:
    """Tests for DiagramType enum."""

    def test_all_types_defined(self):
        """Test that all expected diagram types are defined."""
        expected = {"architecture", "class", "sequence", "callgraph", "dependency"}
        actual = {dt.value for dt in DiagramType}
        assert actual == expected


class TestValidationSeverity:
    """Tests for ValidationSeverity enum."""

    def test_all_severities_defined(self):
        """Test that all severity levels are defined."""
        expected = {"error", "warning", "info"}
        actual = {vs.value for vs in ValidationSeverity}
        assert actual == expected


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_minimal_error(self):
        """Test creating error with minimal fields."""
        error = ValidationError(
            severity=ValidationSeverity.ERROR,
            message="Test error",
        )
        assert error.severity == ValidationSeverity.ERROR
        assert error.message == "Test error"
        assert error.line_number is None
        assert error.suggestion is None

    def test_complete_error(self):
        """Test creating error with all fields."""
        error = ValidationError(
            severity=ValidationSeverity.WARNING,
            message="Test warning",
            line_number=42,
            line_content="graph TD",
            rule_name="test_rule",
            suggestion="Fix the thing",
        )
        assert error.severity == ValidationSeverity.WARNING
        assert error.line_number == 42
        assert error.line_content == "graph TD"
        assert error.rule_name == "test_rule"
        assert error.suggestion == "Fix the thing"

    def test_error_string_minimal(self):
        """Test string representation with minimal fields."""
        error = ValidationError(
            severity=ValidationSeverity.ERROR,
            message="Test error",
        )
        result = str(error)
        assert "[ERROR]" in result
        assert "Test error" in result

    def test_error_string_complete(self):
        """Test string representation with all fields."""
        error = ValidationError(
            severity=ValidationSeverity.WARNING,
            message="Test warning",
            line_number=42,
            line_content="graph TD",
            rule_name="test_rule",
            suggestion="Fix the thing",
        )
        result = str(error)
        assert "[WARNING]" in result
        assert "(test_rule)" in result
        assert "Test warning" in result
        assert "line 42" in result
        assert "'graph TD'" in result
        assert "Fix the thing" in result


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result with no errors."""
        result = ValidationResult(
            diagram_type=DiagramType.ARCHITECTURE,
            is_valid=True,
            errors=[],
            warnings=[],
            info=[],
            diagram_content="graph TD\nA --> B",
        )
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings
        assert not result.has_info

    def test_result_with_errors(self):
        """Test result with errors."""
        error = ValidationError(
            severity=ValidationSeverity.ERROR,
            message="Test error",
        )
        result = ValidationResult(
            diagram_type=DiagramType.CLASS,
            is_valid=False,
            errors=[error],
            warnings=[],
            info=[],
            diagram_content="classDiagram",
        )
        assert not result.is_valid
        assert result.has_errors
        assert len(result.errors) == 1

    def test_result_with_warnings(self):
        """Test result with warnings but no errors."""
        warning = ValidationError(
            severity=ValidationSeverity.WARNING,
            message="Test warning",
        )
        result = ValidationResult(
            diagram_type=DiagramType.SEQUENCE,
            is_valid=True,
            errors=[],
            warnings=[warning],
            info=[],
            diagram_content="sequenceDiagram",
        )
        assert result.is_valid
        assert not result.has_errors
        assert result.has_warnings

    def test_all_issues_property(self):
        """Test all_issues property combines all severity levels."""
        error = ValidationError(
            severity=ValidationSeverity.ERROR,
            message="Error",
        )
        warning = ValidationError(
            severity=ValidationSeverity.WARNING,
            message="Warning",
        )
        info = ValidationError(
            severity=ValidationSeverity.INFO,
            message="Info",
        )
        result = ValidationResult(
            diagram_type=DiagramType.ARCHITECTURE,
            is_valid=False,
            errors=[error],
            warnings=[warning],
            info=[info],
            diagram_content="graph TD",
        )
        all_issues = result.all_issues
        assert len(all_issues) == 3
        assert error in all_issues
        assert warning in all_issues
        assert info in all_issues

    def test_result_string_representation(self):
        """Test string representation of validation result."""
        result = ValidationResult(
            diagram_type=DiagramType.ARCHITECTURE,
            is_valid=True,
            errors=[],
            warnings=[],
            info=[],
            diagram_content="graph TD\nA --> B",
        )
        result_str = str(result)
        assert "✓ PASS" in result_str or "PASS" in result_str
        assert "architecture" in result_str


class TestValidationConfig:
    """Tests for ValidationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ValidationConfig()
        assert config.mode == "strict"
        assert not config.fail_on_warnings
        assert config.enabled_rules is None
        assert config.disabled_rules is None
        assert config.validate_on_generation

    def test_custom_config(self):
        """Test custom configuration."""
        config = ValidationConfig(
            mode="permissive",
            fail_on_warnings=True,
            enabled_rules={"rule1", "rule2"},
            validate_on_generation=False,
        )
        assert config.mode == "permissive"
        assert config.fail_on_warnings
        assert config.enabled_rules == {"rule1", "rule2"}
        assert not config.validate_on_generation

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Mode must be"):
            ValidationConfig(mode="invalid")

    def test_overlapping_rules_raises_error(self):
        """Test that overlapping enabled/disabled rules raises error."""
        with pytest.raises(ValueError, match="cannot be both enabled and disabled"):
            ValidationConfig(
                enabled_rules={"rule1", "rule2"},
                disabled_rules={"rule2", "rule3"},
            )

    def test_is_rule_enabled_default(self):
        """Test rule enabled check with default config."""
        config = ValidationConfig()
        assert config.is_rule_enabled("any_rule")

    def test_is_rule_enabled_with_enabled_list(self):
        """Test rule enabled check with enabled_rules set."""
        config = ValidationConfig(enabled_rules={"rule1", "rule2"})
        assert config.is_rule_enabled("rule1")
        assert config.is_rule_enabled("rule2")
        assert not config.is_rule_enabled("rule3")

    def test_is_rule_enabled_with_disabled_list(self):
        """Test rule enabled check with disabled_rules set."""
        config = ValidationConfig(disabled_rules={"rule1"})
        assert not config.is_rule_enabled("rule1")
        assert config.is_rule_enabled("rule2")

    def test_disabled_takes_precedence(self):
        """Test that disabled_rules takes precedence over enabled_rules."""
        # This should not happen due to validation, but test the logic
        config = ValidationConfig()
        config.disabled_rules = {"rule1"}
        config.enabled_rules = {"rule1", "rule2"}
        # Disabled takes precedence
        assert not config.is_rule_enabled("rule1")
