"""Tests for cross-reference analysis."""

import pytest

from docgen.core.cross_reference import (
    ComponentReference,
    CrossReferenceAnalyzer,
    cross_reference_preprocessor,
)
from docgen.models.code_entity import CodeEntity, EntityType
from docgen.models.file_analysis import FileAnalysis


def test_cross_reference_analyzer_basic():
    """Test basic cross-reference analysis."""
    # Create test analyses
    analyses = [
        FileAnalysis(
            file_path="src/main.py",
            entities=[
                CodeEntity(
                    name="MainClass",
                    type=EntityType.CLASS,
                    docstring="Main class",
                    start_line=1,
                    end_line=10,
                    source="class MainClass: pass",
                    parent_class=None,
                )
            ],
            imports=["helper.HelperClass"],
            content="class MainClass: pass",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="src/helper.py",
            entities=[
                CodeEntity(
                    name="HelperClass",
                    type=EntityType.CLASS,
                    docstring="Helper class",
                    start_line=1,
                    end_line=5,
                    source="class HelperClass: pass",
                    parent_class=None,
                )
            ],
            imports=[],
            content="class HelperClass: pass",
            _skip_validation=True,
        ),
    ]

    analyzer = CrossReferenceAnalyzer(analyses)

    # Test component registration
    assert "MainClass" in analyzer._components
    assert "HelperClass" in analyzer._components

    # Test import tracking
    helper_ref = analyzer.get_component_references("HelperClass")
    assert helper_ref is not None
    assert "src/main.py" in helper_ref.imported_by
    assert helper_ref.import_count == 1


def test_cross_reference_top_components():
    """Test getting top components by usage."""
    analyses = [
        FileAnalysis(
            file_path="src/main.py",
            entities=[
                CodeEntity(
                    name="MainClass",
                    type=EntityType.CLASS,
                    docstring="Main class",
                    start_line=1,
                    end_line=10,
                    source="class MainClass: pass",
                    parent_class=None,
                )
            ],
            imports=["utils.UtilityClass"],
            content="class MainClass: pass",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="src/utils.py",
            entities=[
                CodeEntity(
                    name="UtilityClass",
                    type=EntityType.CLASS,
                    docstring="Utility class",
                    start_line=1,
                    end_line=5,
                    source="class UtilityClass: pass",
                    parent_class=None,
                )
            ],
            imports=[],
            content="class UtilityClass: pass",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="src/other.py",
            entities=[],
            imports=["utils.UtilityClass"],
            content="",
            _skip_validation=True,
        ),
    ]

    analyzer = CrossReferenceAnalyzer(analyses)
    top = analyzer.get_top_components(limit=5)

    # UtilityClass should be top (imported by 2 files)
    assert len(top) > 0
    # Check that UtilityClass is in the top results
    utility_in_top = any(comp.name == "UtilityClass" for comp in top)
    assert utility_in_top


def test_cross_reference_by_type():
    """Test filtering components by type."""
    analyses = [
        FileAnalysis(
            file_path="src/code.py",
            entities=[
                CodeEntity(
                    name="MyClass",
                    type=EntityType.CLASS,
                    docstring="A class",
                    start_line=1,
                    end_line=5,
                    source="class MyClass: pass",
                    parent_class=None,
                ),
                CodeEntity(
                    name="my_function",
                    type=EntityType.FUNCTION,
                    docstring="A function",
                    start_line=7,
                    end_line=10,
                    source="def my_function(): pass",
                    parent_class=None,
                ),
            ],
            imports=[],
            content="class MyClass: pass\ndef my_function(): pass",
            _skip_validation=True,
        ),
    ]

    analyzer = CrossReferenceAnalyzer(analyses)

    classes = analyzer.get_components_by_type("class")
    functions = analyzer.get_components_by_type("function")

    assert len(classes) >= 1
    assert len(functions) >= 1
    assert any(c.name == "MyClass" for c in classes)
    assert any(f.name == "my_function" for f in functions)


def test_cross_reference_report_generation():
    """Test report generation."""
    analyses = [
        FileAnalysis(
            file_path="src/main.py",
            entities=[
                CodeEntity(
                    name="MainClass",
                    type=EntityType.CLASS,
                    docstring="Main class",
                    start_line=1,
                    end_line=10,
                    source="class MainClass: pass",
                    parent_class=None,
                )
            ],
            imports=[],
            content="class MainClass: pass",
            _skip_validation=True,
        ),
    ]

    analyzer = CrossReferenceAnalyzer(analyses)
    report = analyzer.generate_reference_report(limit=10)

    assert isinstance(report, str)
    assert "MainClass" in report or "No cross-references" in report


def test_component_reference_properties():
    """Test ComponentReference properties."""
    ref = ComponentReference(
        name="TestClass",
        type="class",
        defined_in="src/test.py",
        line_number=10,
        imported_by={"file1.py", "file2.py", "file3.py"},
        used_in={"file1.py", "file2.py"},
    )

    assert ref.import_count == 3
    assert ref.usage_count == 2
    assert ref.name == "TestClass"
    assert ref.line_number == 10


def test_import_graph_generation():
    """Test import dependency graph generation."""
    analyses = [
        FileAnalysis(
            file_path="src/main.py",
            entities=[],
            imports=["helper.HelperClass"],
            content="",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="src/helper.py",
            entities=[
                CodeEntity(
                    name="HelperClass",
                    type=EntityType.CLASS,
                    docstring="Helper",
                    start_line=1,
                    end_line=5,
                    source="class HelperClass: pass",
                    parent_class=None,
                )
            ],
            imports=[],
            content="class HelperClass: pass",
            _skip_validation=True,
        ),
    ]

    analyzer = CrossReferenceAnalyzer(analyses)
    graph = analyzer.get_import_graph()

    assert isinstance(graph, dict)
    # main.py imports from helper.py
    if "src/main.py" in graph:
        assert "src/helper.py" in graph["src/main.py"]


HELPER_AND_MAIN = [
    FileAnalysis(
        file_path="helper.py",
        entities=[
            CodeEntity(name="HelperClass", type=EntityType.CLASS, docstring="A helper")
        ],
        imports=[],
        content="class HelperClass: pass",
        _skip_validation=True,
    ),
    FileAnalysis(
        file_path="main.py",
        entities=[],
        imports=["helper.HelperClass"],
        content="from helper import HelperClass",
        _skip_validation=True,
    ),
]


def test_preprocessor_adds_the_reference_report_to_cross_reference_prompts():
    """A cross-reference prompt gets the pre-analyzed report appended."""
    prompt = "Document the cross-references."

    result = cross_reference_preprocessor(prompt, HELPER_AND_MAIN)

    assert result.startswith(prompt)
    assert "## Pre-analyzed Cross-Reference Data" in result
    assert "### `HelperClass`" in result


@pytest.mark.parametrize(
    ("prompt", "analyses"),
    [
        ("Describe the data flow.", HELPER_AND_MAIN),
        ("Document the cross-references.", None),
    ],
)
def test_preprocessor_leaves_other_prompts_alone(prompt, analyses):
    """Other sections, or a run with no analyses, keep the prompt as it is."""
    assert cross_reference_preprocessor(prompt, analyses) == prompt
