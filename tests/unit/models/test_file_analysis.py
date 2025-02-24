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
        lineno=1,
        type="class",
        file_path="/path/to/file.py"
    )

def test_file_analysis_creation(sample_code_entity, tmp_path):
    """Test creating a valid FileAnalysis instance."""
    # Create a temporary file
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")
    
    analysis = FileAnalysis(
        file_path=str(test_file),
        entities=[sample_code_entity],
        imports=["os", "sys"],
        content="print('hello')"
    )
    
    assert analysis.file_path == str(test_file)
    assert len(analysis.entities) == 1
    assert analysis.entities[0].name == "TestClass"
    assert analysis.imports == ["os", "sys"]
    assert analysis.content == "print('hello')"
    assert analysis.error is None

def test_file_analysis_nonexistent_file(sample_code_entity):
    """Test validation of nonexistent file path."""
    with pytest.raises(ValueError, match="File does not exist"):
        FileAnalysis(
            file_path="/nonexistent/file.py",
            entities=[sample_code_entity],
            imports=[],
            content="test"
        )

def test_file_analysis_empty_content(tmp_path):
    """Test validation of empty file content."""
    # Create a temporary file
    test_file = tmp_path / "test.py"
    test_file.write_text("")
    
    with pytest.raises(ValueError, match="File content cannot be empty"):
        FileAnalysis(
            file_path=str(test_file),
            entities=[],
            imports=[],
            content=""
        )

def test_file_analysis_empty_init_file(tmp_path):
    """Test that empty __init__.py files are allowed."""
    # Create a temporary __init__.py file
    init_file = tmp_path / "__init__.py"
    init_file.write_text("")
    
    # This should not raise an error
    analysis = FileAnalysis(
        file_path=str(init_file),
        entities=[],
        imports=[],
        content=""
    )
    
    assert analysis.file_path == str(init_file)
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