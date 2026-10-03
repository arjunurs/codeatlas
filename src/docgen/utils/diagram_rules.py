"""Validation rules for Mermaid diagrams.

This module defines validation rules that check for common syntax errors
and best practices in Mermaid diagrams.
"""

import re
from typing import Protocol

from docgen.models.diagram_validation import (
    DiagramType,
    ValidationError,
    ValidationSeverity,
)


class ValidationRule(Protocol):
    """Protocol for validation rules.

    All validation rules must implement this interface.
    """

    rule_name: str

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Validate diagram content.

        Args:
            diagram_content: The diagram content to validate
            diagram_type: The type of diagram being validated

        Returns:
            List of validation errors found (empty if valid)
        """
        ...


class SyntaxHeaderRule:
    """Validates that diagram starts with correct type declaration."""

    rule_name = "syntax_header"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check if diagram has correct header."""
        errors = []
        lines = diagram_content.strip().split("\n")

        if not lines or not lines[0].strip():
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.ERROR,
                    message="Diagram is empty",
                    rule_name=self.rule_name,
                    suggestion="Add diagram content with proper type declaration",
                )
            )
            return errors

        first_line = lines[0].strip()

        # Expected headers for each diagram type
        expected_headers = {
            DiagramType.ARCHITECTURE: ["graph", "flowchart"],
            DiagramType.CLASS: ["classDiagram"],
            DiagramType.SEQUENCE: ["sequenceDiagram"],
            DiagramType.CALL_GRAPH: ["graph", "flowchart"],
            DiagramType.DEPENDENCY: ["graph", "flowchart"],
        }

        headers = expected_headers.get(diagram_type, [])
        if not any(first_line.startswith(header) for header in headers):
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid diagram header for {diagram_type.value}",
                    line_number=1,
                    line_content=first_line,
                    rule_name=self.rule_name,
                    suggestion=f"Expected one of: {', '.join(headers)}",
                )
            )

        return errors


class QuoteEscapingRule:
    """Validates that quoted labels contain no double quotes.

    Mermaid ends a ["..."] label at its next double quote, and does not
    accept a backslash before one, so either breaks the diagram. A quote is
    written as #quot; instead.
    """

    rule_name = "quote_escaping"

    # From [" to the first "] after it, so a label's own quotes are inside
    _QUOTED_LABEL = re.compile(r'\["(.*?)"\]')

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for double quotes inside quoted labels."""
        errors = []
        lines = diagram_content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("%%"):
                continue

            if any('"' in label for label in self._QUOTED_LABEL.findall(line)):
                errors.append(
                    ValidationError(
                        severity=ValidationSeverity.ERROR,
                        message="Double quote inside a quoted label",
                        line_number=line_num,
                        line_content=line.strip(),
                        rule_name=self.rule_name,
                        suggestion="Write the quote as #quot; or use single quotes",
                    )
                )

        return errors


class SpecialCharactersRule:
    """Validates that Mermaid special characters are properly handled."""

    rule_name = "special_characters"

    # Special characters that need escaping or quoting in Mermaid
    # A tuple, so a line with several is always reported by the same one
    SPECIAL_CHARS = tuple("[];{}|:")

    # Known valid Mermaid operators that contain special chars
    _VALID_OPERATORS = (
        "--|>",
        "--*",
        "--o",
        "-->",
        "-.->",
        "==>",
        "->>",
        "-->>",
        "<<--",
        "<--",
    )

    _HEADER_PREFIXES = ("graph", "flowchart", "classDiagram", "sequenceDiagram")

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for unhandled special characters."""
        errors = []
        is_sequence = diagram_type == DiagramType.SEQUENCE
        is_class = diagram_type == DiagramType.CLASS

        for line_num, line in enumerate(diagram_content.split("\n"), 1):
            if self._should_skip_line(line, is_class):
                continue

            temp_line = self._strip_quoted_sections(line)
            temp_line = self._strip_valid_operators(temp_line, is_sequence)

            for char in self.SPECIAL_CHARS:
                if is_sequence and char == ":":
                    continue
                if char in temp_line:
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.WARNING,
                            message=f"Special character '{char}' may need quoting",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion=f"Wrap text containing '{char}' in quotes or brackets",
                        )
                    )
                    break  # Only report once per line

        return errors

    def _should_skip_line(self, line: str, is_class: bool) -> bool:
        """Check if a line should be skipped during validation."""
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            return True
        if any(stripped.startswith(h) for h in self._HEADER_PREFIXES):
            return True
        if is_class:
            if stripped in ("{", "}"):
                return True
            if re.match(r"\s*class\s+\w+\s*\{", line):
                return True
        return False

    @staticmethod
    def _strip_quoted_sections(line: str) -> str:
        """Remove quoted and bracketed sections from a line."""
        result = re.sub(r"\[[^\]]*\]", "", line)
        result = re.sub(r'"[^"]*"', "", result)
        return re.sub(r"'[^']*'", "", result)

    def _strip_valid_operators(self, line: str, is_sequence: bool) -> str:
        """Remove valid Mermaid operators from a line."""
        for op in self._VALID_OPERATORS:
            line = line.replace(op, "")
        if is_sequence:
            line = re.sub(r":\s*\w+\(\)", "", line)
        return line


class NodeIdFormatRule:
    """Validates that node IDs match Mermaid identifier rules."""

    rule_name = "node_id_format"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check if node IDs follow valid format."""
        errors = []

        # Only applies to graph-based diagrams
        if diagram_type not in (
            DiagramType.ARCHITECTURE,
            DiagramType.CALL_GRAPH,
            DiagramType.DEPENDENCY,
        ):
            return errors

        lines = diagram_content.split("\n")

        # Pattern to match node IDs at the start of nodes or edges
        # Matches: "nodeId[label]", "nodeId --> ", etc.
        node_id_pattern = re.compile(r"^\s*(\w+)[\[\s]")

        for line_num, line in enumerate(lines, 1):
            # Skip header, comments, and empty lines
            if (
                line.strip().startswith(("graph", "flowchart", "%%"))
                or not line.strip()
            ):
                continue

            # Check for node IDs at the start of the line
            match = node_id_pattern.match(line)
            if match:
                node_id = match.group(1)
                # Check if it starts with a digit (invalid)
                if node_id[0].isdigit():
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.ERROR,
                            message=f"Invalid node ID: {node_id} (starts with digit)",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion=(
                                "Node IDs must start with a letter or underscore"
                            ),
                        )
                    )

        return errors


class EmptyDiagramRule:
    """Validates that diagram has content beyond header."""

    rule_name = "empty_diagram"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check if diagram has meaningful content."""
        errors = []
        lines = [
            line.strip() for line in diagram_content.strip().split("\n") if line.strip()
        ]

        # Remove comments
        lines = [line for line in lines if not line.startswith("%%")]

        # Check if we only have a header
        if len(lines) <= 1:
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.ERROR,
                    message="Diagram has no content beyond header",
                    rule_name=self.rule_name,
                    suggestion="Add nodes, edges, or other diagram elements",
                )
            )

        return errors


# Common rules that apply to all diagram types
COMMON_RULES: list[ValidationRule] = [
    SyntaxHeaderRule(),
    QuoteEscapingRule(),
    SpecialCharactersRule(),
    NodeIdFormatRule(),
    EmptyDiagramRule(),
]
