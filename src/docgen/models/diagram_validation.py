"""Data models for diagram validation.

This module defines the data structures used by the diagram validation system
to represent validation results, errors, and configuration.
"""

from dataclasses import dataclass
from enum import Enum


class DiagramType(Enum):
    """Types of diagrams that can be generated and validated."""

    ARCHITECTURE = "architecture"
    CLASS = "class"
    SEQUENCE = "sequence"
    CALL_GRAPH = "callgraph"
    DEPENDENCY = "dependency"


class ValidationMode(Enum):
    """Validation strictness modes."""

    STRICT = "strict"
    PERMISSIVE = "permissive"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Breaks Mermaid rendering
    WARNING = "warning"  # May cause issues
    INFO = "info"  # Style/best practice


@dataclass
class ValidationError:
    """Represents a single validation issue found in a diagram.

    Attributes:
        severity: The severity level of this issue
        message: Human-readable description of the issue
        line_number: Optional line number where the issue occurs
        line_content: Optional content of the problematic line
        rule_name: Optional name of the validation rule that caught this
        suggestion: Optional suggestion for fixing the issue
    """

    severity: ValidationSeverity
    message: str
    line_number: int | None = None
    line_content: str | None = None
    rule_name: str | None = None
    suggestion: str | None = None

    def __str__(self) -> str:
        """Format the validation error as a readable string."""
        parts = [f"[{self.severity.value.upper()}]"]

        if self.rule_name:
            parts.append(f"({self.rule_name})")

        parts.append(self.message)

        if self.line_number is not None:
            parts.append(f"at line {self.line_number}")

        if self.line_content:
            parts.append(f": {self.line_content!r}")

        result = " ".join(parts)

        if self.suggestion:
            result += f"\n  → Suggestion: {self.suggestion}"

        return result


@dataclass
class ValidationResult:
    """Results of validating a diagram.

    Attributes:
        diagram_type: The type of diagram that was validated
        is_valid: Whether the diagram passed validation
        errors: List of error-level issues found
        warnings: List of warning-level issues found
        info: List of info-level issues found
        diagram_content: The original diagram content that was validated
    """

    diagram_type: DiagramType
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    info: list[ValidationError]
    diagram_content: str

    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return len(self.warnings) > 0

    @property
    def has_info(self) -> bool:
        """Check if there are any info-level issues."""
        return len(self.info) > 0

    @property
    def all_issues(self) -> list[ValidationError]:
        """Get all issues sorted by severity."""
        return self.errors + self.warnings + self.info

    def __str__(self) -> str:
        """Format the validation result as a readable string."""
        status = "✓ PASS" if self.is_valid else "✗ FAIL"
        result = f"{status} {self.diagram_type.value}\n"

        if self.has_errors:
            result += f"\nErrors ({len(self.errors)}):\n"
            for error in self.errors:
                result += f"  • {error}\n"

        if self.has_warnings:
            result += f"\nWarnings ({len(self.warnings)}):\n"
            for warning in self.warnings:
                result += f"  • {warning}\n"

        if self.has_info:
            result += f"\nInfo ({len(self.info)}):\n"
            for info_item in self.info:
                result += f"  • {info_item}\n"

        if not (self.has_errors or self.has_warnings or self.has_info):
            result += "  No issues found\n"

        return result


@dataclass
class ValidationConfig:
    """Configuration for diagram validation.

    Attributes:
        mode: Validation strictness ('strict' or 'permissive')
        fail_on_warnings: Whether to treat warnings as errors
        enabled_rules: Set of rule names to enable (None = all enabled)
        disabled_rules: Set of rule names to disable (None = none disabled)
        validate_on_generation: Whether to validate during diagram generation
    """

    mode: ValidationMode = ValidationMode.STRICT
    fail_on_warnings: bool = False
    enabled_rules: set[str] | None = None
    disabled_rules: set[str] | None = None
    validate_on_generation: bool = True

    def __post_init__(self):
        """Validate configuration values."""
        # Auto-convert string to ValidationMode for backward compatibility
        if isinstance(self.mode, str):
            try:
                self.mode = ValidationMode(self.mode)
            except ValueError:
                raise ValueError("Mode must be 'strict' or 'permissive'")

        if self.enabled_rules and self.disabled_rules:
            overlap = self.enabled_rules & self.disabled_rules
            if overlap:
                raise ValueError(
                    f"Rules cannot be both enabled and disabled: {overlap}"
                )

    def is_rule_enabled(self, rule_name: str) -> bool:
        """Check if a specific validation rule is enabled.

        Args:
            rule_name: Name of the rule to check

        Returns:
            True if the rule should be applied, False otherwise
        """
        # If explicitly disabled, return False
        if self.disabled_rules and rule_name in self.disabled_rules:
            return False

        # If enabled_rules is set, only those rules are enabled
        if self.enabled_rules:
            return rule_name in self.enabled_rules

        # Otherwise, all rules are enabled by default
        return True
