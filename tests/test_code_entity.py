"""Unit tests for the CodeEntity class.

This module contains comprehensive tests for the CodeEntity class, including
validation, edge cases, and error conditions.
"""

import unittest
from docgen.models.code_entity import CodeEntity

class TestCodeEntity(unittest.TestCase):
    """Test cases for the CodeEntity class."""

    def test_valid_class_entity(self):
        """Test creating a valid class entity."""
        entity = CodeEntity(
            name="TestClass",
            type="class",
            docstring="Test class docstring",
            methods=["test_method"],
            start_line=1,
            end_line=10,
            source="class TestClass:\n    def test_method(self):\n        pass"
        )
        self.assertEqual(entity.name, "TestClass")
        self.assertEqual(entity.type, "class")
        self.assertEqual(entity.docstring, "Test class docstring")
        self.assertEqual(entity.methods, ["test_method"])
        self.assertEqual(entity.start_line, 1)
        self.assertEqual(entity.end_line, 10)
        self.assertIsNotNone(entity.source)

    def test_valid_function_entity(self):
        """Test creating a valid function entity."""
        entity = CodeEntity(
            name="test_func",
            type="function",
            docstring="Test function docstring",
            start_line=1,
            end_line=5,
            source="def test_func():\n    pass"
        )
        self.assertEqual(entity.name, "test_func")
        self.assertEqual(entity.type, "function")
        self.assertEqual(entity.docstring, "Test function docstring")
        self.assertIsNone(entity.methods)
        self.assertEqual(entity.start_line, 1)
        self.assertEqual(entity.end_line, 5)
        self.assertIsNotNone(entity.source)

    def test_empty_name(self):
        """Test error when name is empty."""
        with self.assertRaises(ValueError):
            CodeEntity(
                name="",
                type="class",
                docstring="Test",
                methods=["test_method"],
                start_line=1,
                end_line=10,
                source="class TestClass:\n    pass"
            )

    def test_invalid_entity_type(self):
        """Test error when entity type is invalid."""
        with self.assertRaises(ValueError):
            CodeEntity(
                name="Test",
                type="invalid",
                docstring="Test",
                start_line=1,
                end_line=10,
                source="def test():\n    pass"
            )

    def test_invalid_line_number(self):
        """Test error when line number is invalid."""
        with self.assertRaises(ValueError):
            CodeEntity(
                name="Test",
                type="class",
                docstring="Test",
                methods=["test_method"],
                start_line=-1,
                end_line=10,
                source="class Test:\n    pass"
            )

    def test_no_parent_class(self):
        """Test creating a class entity without parent class."""
        entity = CodeEntity(
            name="TestClass",
            type="class",
            docstring="Test class",
            methods=["test_method"],
            start_line=1,
            end_line=10,
            source="class TestClass:\n    pass"
        )
        self.assertEqual(entity.name, "TestClass")
        self.assertEqual(entity.type, "class")
        self.assertEqual(entity.methods, ["test_method"])

if __name__ == '__main__':
    unittest.main()
