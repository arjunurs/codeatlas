"""Unit tests for the FileAnalysis model."""

import os
import pytest
from docgen.models.file_analysis import FileAnalysis
from docgen.models.code_entity import CodeEntity

@pytest.fixture
def sample_code_entity():
    """Create a sample CodeEntity for testing."""
    return CodeEntity(
        name="TestClass",
        docstring="A test class",
        type="class",
        methods=["test_method"],
        start_line=1,
        end_line=3,
        source="class TestClass:\n    def test_method(self):\n        pass"
    )

def test_file_analysis_creation(sample_code_entity):
    """Test creating a valid FileAnalysis instance.

    Note: FileAnalysis no longer requires the file to exist on disk.
    This is a pure data container and filesystem checks are the caller's responsibility.
    """
    analysis = FileAnalysis(
        file_path="/path/to/test.py",
        entities=[sample_code_entity],
        imports=["os", "sys"],
        content="print('hello')"
    )

    assert analysis.file_path == "/path/to/test.py"
    assert len(analysis.entities) == 1
    assert analysis.entities[0].name == "TestClass"
    assert analysis.imports == ["os", "sys"]
    assert analysis.content == "print('hello')"
    assert analysis.error is None

def test_file_analysis_nonexistent_file(sample_code_entity):
    """Test validation of nonexistent file path."""
    with pytest.raises(ValueError, match="File path cannot be empty"):
        FileAnalysis(
            file_path="",
            entities=[],
            imports=[],
            content="test content"
        )

def test_file_analysis_empty_content():
    """Test validation of empty file content."""
    with pytest.raises(ValueError, match="Content cannot be empty except for __init__.py files"):
        FileAnalysis(
            file_path="/path/to/test.py",
            entities=[],
            imports=[],
            content=""
        )

def test_file_analysis_empty_init_file():
    """Test that empty __init__.py files are allowed."""
    # Empty __init__.py files should pass validation without _skip_validation
    analysis = FileAnalysis(
        file_path="/path/to/__init__.py",
        entities=[],
        imports=[],
        content=""
    )

    assert analysis.file_path == "/path/to/__init__.py"
    assert not analysis.entities
    assert not analysis.imports
    assert not analysis.content

def test_file_analysis_skip_validation(sample_code_entity):
    """Test skipping file validation for testing purposes."""
    # This should not raise an error despite the file not existing
    analysis = FileAnalysis(
        file_path="/nonexistent/file.py",
        entities=[sample_code_entity],
        imports=[],
        content="test",
        _skip_validation=True
    )
    
    assert analysis.file_path == "/nonexistent/file.py"
    assert len(analysis.entities) == 1 