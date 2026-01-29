"""Core diagram validation framework.

This module provides the main DiagramValidator class that dispatches to
type-specific validators for comprehensive diagram validation.
"""

import logging
from typing import Protocol

from docgen.exceptions.errors import DiagramValidationError
from docgen.models.diagram_validation import (
    DiagramType,
    ValidationConfig,
    ValidationResult,
)
from docgen.utils.diagram_rules import COMMON_RULES, ValidationRule

logger = logging.getLogger(__name__)


class TypedValidator(Protocol):
    """Protocol for type-specific diagram validators."""

    def validate(
        self,
        diagram_content: str,
        *,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """Validate a diagram and return results."""
        ...


class BaseValidator:
    """Base class for type-specific diagram validators.

    Provides common validation logic that can be extended by specific diagram types.
    """

    def __init__(
        self,
        diagram_type: DiagramType,
        config: ValidationConfig,
        additional_rules: list[ValidationRule] | None = None,
    ):
        """Initialize base validator.

        Args:
            diagram_type: The type of diagram this validator handles
            config: Validation configuration
            additional_rules: Type-specific validation rules to add
        """
        self.diagram_type = diagram_type
        self.config = config
        self.rules = list(COMMON_RULES)
        if additional_rules:
            self.rules.extend(additional_rules)

    def validate(
        self,
        diagram_content: str,
        *,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """Validate diagram content.

        Args:
            diagram_content: The diagram to validate
            raise_on_error: Whether to raise DiagramValidationError on
                validation failure

        Returns:
            ValidationResult with all issues found

        Raises:
            DiagramValidationError: If raise_on_error=True and validation fails
        """
        errors = []
        warnings = []
        info = []

        # Run all enabled rules
        for rule in self.rules:
            if not self.config.is_rule_enabled(rule.rule_name):
                continue

            try:
                issues = rule.validate(diagram_content, self.diagram_type)
                for issue in issues:
                    if issue.severity.value == "error":
                        errors.append(issue)
                    elif issue.severity.value == "warning":
                        warnings.append(issue)
                    else:
                        info.append(issue)
            except Exception as e:
                logger.warning(f"Rule {rule.rule_name} failed: {e}")

        # Determine if diagram is valid
        is_valid = len(errors) == 0
        if self.config.fail_on_warnings and len(warnings) > 0:
            is_valid = False

        result = ValidationResult(
            diagram_type=self.diagram_type,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            info=info,
            diagram_content=diagram_content,
        )

        if raise_on_error and not is_valid:
            error_msg = f"{self.diagram_type.value} diagram validation failed"
            if errors:
                error_msg += f" with {len(errors)} error(s)"
            if warnings and self.config.fail_on_warnings:
                error_msg += f" and {len(warnings)} warning(s)"
            raise DiagramValidationError(error_msg)

        return result


class DiagramValidator:
    """Main validator that dispatches to type-specific validators.

    This is the primary entry point for diagram validation.
    """

    def __init__(self, config: ValidationConfig | None = None):
        """Initialize diagram validator.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()

        # Import type-specific validators here to avoid circular imports
        from docgen.utils.diagram_validators import (
            ArchitectureDiagramValidator,
            CallGraphValidator,
            ClassDiagramValidator,
            DependencyDiagramValidator,
            SequenceDiagramValidator,
        )

        self.validators: dict[DiagramType, TypedValidator] = {
            DiagramType.ARCHITECTURE: ArchitectureDiagramValidator(self.config),
            DiagramType.CLASS: ClassDiagramValidator(self.config),
            DiagramType.SEQUENCE: SequenceDiagramValidator(self.config),
            DiagramType.CALL_GRAPH: CallGraphValidator(self.config),
            DiagramType.DEPENDENCY: DependencyDiagramValidator(self.config),
        }

    def validate(
        self,
        diagram_content: str,
        diagram_type: DiagramType,
        *,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """Validate a diagram of a specific type.

        Args:
            diagram_content: The diagram content to validate
            diagram_type: The type of diagram
            raise_on_error: Whether to raise exception on validation failure

        Returns:
            ValidationResult with all issues found

        Raises:
            DiagramValidationError: If raise_on_error=True and validation fails
            KeyError: If diagram_type is not supported
        """
        validator = self.validators.get(diagram_type)
        if not validator:
            type_str = (
                diagram_type.value
                if isinstance(diagram_type, DiagramType)
                else str(diagram_type)
            )
            raise KeyError(f"No validator found for diagram type: {type_str}")

        return validator.validate(diagram_content, raise_on_error=raise_on_error)

    def validate_auto_detect(
        self,
        diagram_content: str,
        *,
        raise_on_error: bool = False,
    ) -> ValidationResult:
        """Auto-detect diagram type from content and validate.

        Args:
            diagram_content: The diagram content to validate
            raise_on_error: Whether to raise exception on validation failure

        Returns:
            ValidationResult with all issues found

        Raises:
            DiagramValidationError: If diagram type cannot be detected or
                validation fails
        """
        diagram_type = self._detect_diagram_type(diagram_content)
        return self.validate(
            diagram_content, diagram_type, raise_on_error=raise_on_error
        )

    def _detect_diagram_type(self, diagram_content: str) -> DiagramType:
        """Detect diagram type from content.

        Args:
            diagram_content: The diagram content

        Returns:
            Detected DiagramType

        Raises:
            DiagramValidationError: If type cannot be detected
        """
        first_line = diagram_content.strip().split("\n")[0].lower()

        if first_line.startswith("classdiagram"):
            return DiagramType.CLASS
        if first_line.startswith("sequencediagram"):
            return DiagramType.SEQUENCE
        if first_line.startswith(("graph", "flowchart")):
            # Try to distinguish between architecture, call graph, and dependency
            # For now, default to architecture (can be refined with content analysis)
            return DiagramType.ARCHITECTURE

        raise DiagramValidationError(
            f"Cannot detect diagram type from header: {first_line}"
        )
