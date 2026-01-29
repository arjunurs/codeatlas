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
    """Validates that quotes are properly escaped in labels."""

    rule_name = "quote_escaping"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for unescaped quotes in labels."""
        errors = []
        lines = diagram_content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("%%"):
                continue

            # Check for labels in brackets with double quotes: ["..."]
            bracket_double = re.finditer(r'\["([^"]*)"\]', line)
            for match in bracket_double:
                label = match.group(1)
                # Look for embedded unescaped quotes (not at boundaries)
                if '"' in label:
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.WARNING,
                            message="Unescaped double quote in label",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion='Escape quotes as \\" or use single quotes',
                        )
                    )

        return errors


class SpecialCharactersRule:
    """Validates that Mermaid special characters are properly handled."""

    rule_name = "special_characters"

    # Special characters that need escaping or quoting in Mermaid
    SPECIAL_CHARS = set("[];{}|:")

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for unhandled special characters."""
        errors = []
        lines = diagram_content.split("\n")

        # Known valid Mermaid operators that contain special chars
        valid_operators = [
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
        ]

        # For sequence diagrams, : is valid syntax in messages
        is_sequence_diagram = diagram_type == DiagramType.SEQUENCE
        # For class diagrams, { and } are valid syntax for class bodies
        is_class_diagram = diagram_type == DiagramType.CLASS

        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            if line.strip().startswith("%%") or not line.strip():
                continue

            # Skip header lines
            if any(
                line.strip().startswith(h)
                for h in ["graph", "flowchart", "classDiagram", "sequenceDiagram"]
            ):
                continue

            # Skip class body delimiters in class diagrams
            if is_class_diagram:
                # Skip standalone braces
                if line.strip() in ["{", "}"]:
                    continue
                # Skip "class Name {" lines
                if re.match(r"\s*class\s+\w+\s*\{", line):
                    continue

            # Check if the line has special chars outside of quoted/bracketed sections
            # Remove quoted and bracketed sections first
            temp_line = re.sub(r"\[[^\]]*\]", "", line)  # Remove [...] sections
            temp_line = re.sub(r'"[^"]*"', "", temp_line)  # Remove "..." sections
            temp_line = re.sub(r"'[^']*'", "", temp_line)  # Remove '...' sections

            # Remove valid Mermaid operators
            for op in valid_operators:
                temp_line = temp_line.replace(op, "")

            # For sequence diagrams, remove message syntax (: is valid)
            if is_sequence_diagram:
                # Remove ": message" pattern from sequence diagram arrows
                temp_line = re.sub(
                    r":\s*\w+\(\)", "", temp_line
                )  # Remove ": call()" or ": return"

            # Now check for special characters in the remaining text
            for char in self.SPECIAL_CHARS:
                # Skip : check for sequence diagrams (already handled)
                if is_sequence_diagram and char == ":":
                    continue

                if char in temp_line:
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.WARNING,
                            message=f"Special character '{char}' may need quoting",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion=(
                                f"Wrap text containing '{char}' in quotes or brackets"
                            ),
                        )
                    )
                    break  # Only report once per line

        return errors


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
