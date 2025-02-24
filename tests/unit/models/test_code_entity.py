"""Unit tests for the CodeEntity model."""

import pytest
from docgen.models.code_entity import CodeEntity

def test_code_entity_creation():
    """Test creating a valid CodeEntity instance."""
    entity = CodeEntity(
        name="TestClass",
        docstring="A test class",
        lineno=10,
        type="class",
        file_path="/path/to/file.py",
        methods=["method1", "method2"],
        parent_class="BaseClass"
    )
    
    assert entity.name == "TestClass"
    assert entity.docstring == "A test class"
    assert entity.lineno == 10
    assert entity.type == "class"
    assert entity.file_path == "/path/to/file.py"
    assert entity.methods == ["method1", "method2"]
    assert entity.parent_class == "BaseClass"

def test_code_entity_validation():
    """Test validation of CodeEntity attributes."""
    # Test invalid type
    with pytest.raises(ValueError, match="Entity type must be 'class' or 'function'"):
        CodeEntity(
            name="Test",
            docstring="",
            lineno=1,
            type="invalid",
            file_path="/path/to/file.py"
        )
    
    # Test invalid line number
    with pytest.raises(ValueError, match="Line number must be positive"):
        CodeEntity(
            name="Test",
            docstring="",
            lineno=0,
            type="class",
            file_path="/path/to/file.py"
        )

def test_code_entity_function():
    """Test creating a function entity."""
    entity = CodeEntity(
        name="test_function",
        docstring="A test function",
        lineno=5,
        type="function",
        file_path="/path/to/file.py"
    )
    
    assert entity.name == "test_function"
    assert entity.type == "function"
    assert not entity.methods  # Should be empty list
    assert entity.parent_class is None 