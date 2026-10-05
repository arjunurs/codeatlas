"""Type-specific diagram validators with specialized rules.

This module provides validators for each diagram type with their own
specialized validation rules beyond the common ones.
"""

import re

from docgen.models.diagram_validation import (
    DiagramType,
    ValidationConfig,
    ValidationError,
    ValidationSeverity,
)
from docgen.utils.diagram_validator import BaseValidator


# Graph-specific validation rules
class GraphDirectionRule:
    """Validates that graph has valid direction specified."""

    rule_name = "graph_direction"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for valid graph direction."""
        errors = []
        first_line = diagram_content.strip().split("\n")[0]

        if first_line.startswith(("graph", "flowchart")):
            # Check for direction specifier
            valid_directions = ["TD", "TB", "LR", "RL", "BT"]
            has_direction = any(
                direction in first_line for direction in valid_directions
            )

            if not has_direction:
                errors.append(
                    ValidationError(
                        severity=ValidationSeverity.WARNING,
                        message="Graph direction not specified",
                        line_number=1,
                        line_content=first_line,
                        rule_name=self.rule_name,
                        suggestion=f"Add direction: {', '.join(valid_directions)}",
                    )
                )

        return errors


class NodeDefinitionRule:
    """Validates that nodes are defined before use in edges."""

    rule_name = "node_definition"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check that nodes are defined before use."""
        errors = []
        lines = diagram_content.split("\n")

        defined_nodes = set()
        referenced_nodes = set()

        for line in lines:
            # Skip header, comments, empty lines
            if (
                line.strip().startswith(("graph", "flowchart", "%%"))
                or not line.strip()
            ):
                continue

            # Extract node definitions (nodes with labels: node[label]). Each
            # pattern starts only at the start of a word: a match never begins
            # inside one, and without (?<!\w) a long name with no match is
            # rescanned from every character, in quadratic time
            node_defs = re.findall(r"(?<!\w)(\w+)\[", line)
            defined_nodes.update(node_defs)

            # Extract node references in edges (node1 --> node2)
            edge_matches = re.findall(r"(?<!\w)(\w+)\s*(?:-->|\.\.>|==>)\s*(\w+)", line)
            for source, target in edge_matches:
                referenced_nodes.update([source, target])

        # Check for undefined nodes
        undefined = referenced_nodes - defined_nodes
        if undefined:
            undefined_list = ", ".join(sorted(undefined))
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.WARNING,
                    message=f"Nodes referenced but not defined: {undefined_list}",
                    rule_name=self.rule_name,
                    suggestion="Define nodes with labels before using in edges",
                )
            )

        return errors


class EdgeSyntaxRule:
    """Validates that edges use correct syntax."""

    rule_name = "edge_syntax"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for valid edge connectors."""
        errors = []
        lines = diagram_content.split("\n")

        valid_connectors = ["-->", "-.->", "==>", "---", "-.-", "==="]

        for line_num, line in enumerate(lines, 1):
            if (
                line.strip().startswith(("graph", "flowchart", "%%"))
                or not line.strip()
            ):
                continue

            # Check for potential invalid connectors
            if "--" in line or "==" in line:
                has_valid = any(conn in line for conn in valid_connectors)
                if not has_valid:
                    connector_list = ", ".join(valid_connectors)
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.ERROR,
                            message="Invalid edge connector syntax",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion=f"Use valid connectors: {connector_list}",
                        )
                    )

        return errors


def create_graph_validator(
    diagram_type: DiagramType, config: ValidationConfig
) -> BaseValidator:
    """Create a validator for graph-based diagrams (architecture, call graph, dependency).

    These diagram types share the same validation rules.

    Args:
        diagram_type: The type of graph diagram
        config: Validation configuration

    Returns:
        A configured BaseValidator instance
    """
    return BaseValidator(
        diagram_type=diagram_type,
        config=config,
        additional_rules=[
            GraphDirectionRule(),
            NodeDefinitionRule(),
            EdgeSyntaxRule(),
        ],
    )


# Class diagram specific rules
class ClassDeclarationRule:
    """Validates class declarations."""

    rule_name = "class_declaration"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check for valid class declarations."""
        errors = []
        lines = diagram_content.split("\n")

        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("%%") or not line.strip():
                continue

            # Check for class keyword
            if line.strip().startswith("class "):
                # Validate class name format
                match = re.match(r"class\s+(\w+)", line.strip())
                if not match:
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.ERROR,
                            message="Invalid class declaration syntax",
                            line_number=line_num,
                            line_content=line.strip(),
                            rule_name=self.rule_name,
                            suggestion="Use: class ClassName",
                        )
                    )

        return errors


# Class diagram validator
class ClassDiagramValidator(BaseValidator):
    """Validator for class diagrams."""

    def __init__(self, config: ValidationConfig):
        """Initialize with class diagram rules."""
        super().__init__(
            diagram_type=DiagramType.CLASS,
            config=config,
            additional_rules=[
                ClassDeclarationRule(),
            ],
        )


# Sequence diagram specific rules
class ParticipantReferenceRule:
    """Validates that all participants are defined."""

    rule_name = "participant_references"

    def validate(
        self, diagram_content: str, diagram_type: DiagramType
    ) -> list[ValidationError]:
        """Check that participants are defined before use."""
        errors = []
        lines = diagram_content.split("\n")

        defined_participants = set()
        referenced_participants = set()

        for line in lines:
            if line.strip().startswith("sequenceDiagram") or not line.strip():
                continue

            # Extract participant definitions
            if line.strip().startswith("participant "):
                match = re.match(r"participant\s+(\w+)", line.strip())
                if match:
                    defined_participants.add(match.group(1))

            # Extract participant references in messages, starting only at the
            # start of a word (see NodeDefinitionRule)
            message_matches = re.findall(r"(?<!\w)(\w+)\s*-[>-]+\s*(\w+)", line)
            for source, target in message_matches:
                referenced_participants.update([source, target])

        # Check for undefined participants
        # Note: Mermaid allows implicit participant definitions (first use defines them)
        # So this is a WARNING, not an ERROR
        undefined = referenced_participants - defined_participants
        if undefined:
            # Format participant list with truncation for readability
            participant_list = ", ".join(sorted(undefined)[:10])
            truncated = "..." if len(undefined) > 10 else ""
            message = (
                f"Implicit participants (no explicit declaration): "
                f"{participant_list}{truncated}"
            )
            suggestion = (
                "Optional: Add 'participant name' declarations for clarity "
                "(implicit definitions are valid)"
            )
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.WARNING,
                    message=message,
                    rule_name=self.rule_name,
                    suggestion=suggestion,
                )
            )

        return errors


# Sequence diagram validator
class SequenceDiagramValidator(BaseValidator):
    """Validator for sequence diagrams."""

    def __init__(self, config: ValidationConfig):
        """Initialize with sequence diagram rules."""
        super().__init__(
            diagram_type=DiagramType.SEQUENCE,
            config=config,
            additional_rules=[
                ParticipantReferenceRule(),
            ],
        )
