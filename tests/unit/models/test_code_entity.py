"""Unit tests for the CodeEntity model."""

import pytest

from docgen.models.code_entity import CodeEntity, EntityType


def test_code_entity_creation():
    """Test successful creation of code entities."""
    # Test function entity
    func_entity = CodeEntity(
        name="test_func",
        type=EntityType.FUNCTION,
        docstring="Test function",
        start_line=1,
        end_line=2,
        source="def test_func():\n    pass",
    )
    assert func_entity.name == "test_func"
    assert func_entity.type == EntityType.FUNCTION
    assert func_entity.docstring == "Test function"
    assert func_entity.methods is None
    assert func_entity.start_line == 1
    assert func_entity.end_line == 2
    assert func_entity.source == "def test_func():\n    pass"

    # Test class entity
    class_entity = CodeEntity(
        name="TestClass",
        type=EntityType.CLASS,
        docstring="Test class",
        methods=["method1", "method2"],
        start_line=1,
        end_line=5,
        source="class TestClass:\n    def method1(self):\n        pass\n    def method2(self):\n        pass",
        parent_class="BaseClass",
    )
    assert class_entity.name == "TestClass"
    assert class_entity.type == EntityType.CLASS
    assert class_entity.docstring == "Test class"
    assert class_entity.methods == ["method1", "method2"]
    assert class_entity.start_line == 1
    assert class_entity.end_line == 5
    assert class_entity.parent_class == "BaseClass"


def test_code_entity_validation():
    """Test validation of code entity attributes."""
    # Test empty name
    with pytest.raises(ValueError, match="Entity name cannot be empty"):
        CodeEntity(
            name="",
            type=EntityType.FUNCTION,
            docstring="Test function",
            start_line=1,
            end_line=2,
            source="def test_func():\n    pass",
        )

    # Test function with methods
    with pytest.raises(ValueError, match="Function entities cannot have methods"):
        CodeEntity(
            name="test_func",
            type=EntityType.FUNCTION,
            docstring="Test function",
            methods=["method1"],
            start_line=1,
            end_line=2,
            source="def test_func():\n    pass",
        )

    # Test invalid line numbers
    with pytest.raises(
        ValueError, match="Start line number must be a positive integer"
    ):
        CodeEntity(
            name="test_func",
            type=EntityType.FUNCTION,
            docstring="Test function",
            start_line=0,
            end_line=2,
            source="def test_func():\n    pass",
        )

    with pytest.raises(ValueError, match="End line cannot be before start line"):
        CodeEntity(
            name="test_func",
            type=EntityType.FUNCTION,
            docstring="Test function",
            start_line=2,
            end_line=1,
            source="def test_func():\n    pass",
        )


def test_code_entity_function():
    """Test creating a function entity."""
    entity = CodeEntity(
        name="test_function",
        type=EntityType.FUNCTION,
        docstring="A test function",
        start_line=5,
        end_line=6,
        source="def test_function():\n    pass",
    )

    assert entity.name == "test_function"
    assert entity.type == EntityType.FUNCTION
    assert not entity.methods  # Should be None for functions
    assert entity.parent_class is None
    assert entity.start_line == 5
    assert entity.end_line == 6
    assert entity.source == "def test_function():\n    pass"
