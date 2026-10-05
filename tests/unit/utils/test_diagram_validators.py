"""Tests for the type-specific diagram validation rules."""

import time

import pytest

from docgen.models.diagram_validation import DiagramType
from docgen.utils.diagram_validators import (
    NodeDefinitionRule,
    ParticipantReferenceRule,
)

# A function name this long comes only from generated or hostile code; the
# rules used to rescan it from every character, which took seconds
LONG_NAME = "x" * 30_000


def test_node_definition_rule_reports_nodes_used_without_a_label():
    diagram = "graph TD\n    a[A] --> b[B]\n    b --> c\n    d ==> a"

    errors = NodeDefinitionRule().validate(diagram, DiagramType.CALL_GRAPH)

    assert len(errors) == 1
    assert errors[0].message == "Nodes referenced but not defined: c, d"


def test_participant_reference_rule_reports_participants_never_declared():
    diagram = "sequenceDiagram\n    participant A\n    A->>B: call\n    B-->>A: return"

    errors = ParticipantReferenceRule().validate(diagram, DiagramType.SEQUENCE)

    assert len(errors) == 1
    assert "B" in errors[0].message


@pytest.mark.parametrize(
    "line",
    [
        LONG_NAME,
        f"a --> {LONG_NAME}",
        f"{LONG_NAME} -.- b",
    ],
    ids=["name alone", "name after an edge", "name before another link"],
)
def test_node_definition_rule_checks_a_long_name_quickly(line):
    started = time.perf_counter()
    NodeDefinitionRule().validate(f"graph TD\n    {line}", DiagramType.CALL_GRAPH)

    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize(
    "line",
    [LONG_NAME, f"{LONG_NAME} : note"],
    ids=["name alone", "name before a note"],
)
def test_participant_reference_rule_checks_a_long_name_quickly(line):
    started = time.perf_counter()
    ParticipantReferenceRule().validate(
        f"sequenceDiagram\n    {line}", DiagramType.SEQUENCE
    )

    assert time.perf_counter() - started < 0.5
