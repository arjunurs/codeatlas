"""Unit tests for section selection."""

import pytest

from docgen.prompts.sections import SECTION_ORDER, select_sections

ALL_SECTIONS = [
    "Overview",
    "Dependencies",
    "Key Classes and Functions",
    "Data Flow",
    "Integration Points",
    "Migration Guidance",
    "Code Quality Insights",
    "Cross-Reference Documentation",
]


@pytest.mark.parametrize("selection", [None, [], [""], ["", " "]])
def test_no_selection_returns_core_sections(selection):
    """Without a selection, only the core sections are generated."""
    assert select_sections(selection) == SECTION_ORDER


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (["overview"], ["Overview"]),
        (["Overview"], ["Overview"]),
        (["Data Flow"], ["Data Flow"]),
        (["dataflow"], ["Data Flow"]),
        (["classes"], ["Key Classes and Functions"]),
        (["code_quality"], ["Code Quality Insights"]),
        (["cross-reference"], ["Cross-Reference Documentation"]),
        (["overview", ""], ["Overview"]),
        ([" overview "], ["Overview"]),
    ],
)
def test_selection_matches_loosely(selection, expected):
    """Selections match case-insensitively, ignoring spaces, "_" and "-"."""
    assert select_sections(selection) == expected


def test_documented_full_selection_returns_all_sections_in_order():
    """The README's all-sections example selects every section, in order."""
    selection = (
        "overview,dependencies,classes,dataflow,integration,"
        "migration_guidance,code_quality,cross_reference"
    ).split(",")

    assert select_sections(list(reversed(selection))) == ALL_SECTIONS


def test_unknown_section_raises_with_available_names():
    """A name that matches no section is rejected, listing the valid names."""
    with pytest.raises(ValueError, match="Unknown section") as excinfo:
        select_sections(["overview", "overveiw"])

    message = str(excinfo.value)
    assert "overveiw" in message
    assert "Key Classes and Functions" in message
    assert "Cross-Reference Documentation" in message
