"""Unit tests for the CodeEntity class.

This module contains comprehensive tests for the CodeEntity class, including
validation, edge cases, and error conditions.
"""

import unittest
from docgen import CodeEntity

class TestCodeEntity(unittest.TestCase):
    """Test cases for the CodeEntity class."""

    def test_valid_class_entity(self):
        """Test creating a valid class entity."""
        entity = CodeEntity(
            name="TestClass",
            docstring="Test class docstring",
            lineno=10,
            type="class",
            file_path="test.py",
            methods=["method1", "method2"],
            parent_class="BaseClass"
        )

        self.assertEqual(entity.name, "TestClass")
        self.assertEqual(entity.docstring, "Test class docstring")
        self.assertEqual(entity.lineno, 10)
        self.assertEqual(entity.type, "class")
        self.assertEqual(entity.file_path, "test.py")
        self.assertEqual(entity.methods, ["method1", "method2"])
        self.assertEqual(entity.parent_class, "BaseClass")

    def test_valid_function_entity(self):
        """Test creating a valid function entity."""
        entity = CodeEntity(
            name="test_function",
            docstring="Test function docstring",
            lineno=20,
            type="function",
            file_path="test.py"
        )

        self.assertEqual(entity.name, "test_function")
        self.assertEqual(entity.docstring, "Test function docstring")
        self.assertEqual(entity.lineno, 20)
        self.assertEqual(entity.type, "function")
        self.assertEqual(entity.file_path, "test.py")
        self.assertEqual(entity.methods, [])
        self.assertIsNone(entity.parent_class)

    def test_invalid_entity_type(self):
        """Test that invalid entity type raises ValueError."""
        with self.assertRaises(ValueError) as context:
            CodeEntity(
                name="test",
                docstring="test",
                lineno=1,
                type="invalid",
                file_path="test.py"
            )
        
        self.assertEqual(
            str(context.exception),
            "Entity type must be 'class' or 'function'"
        )

    def test_invalid_line_number(self):
        """Test that invalid line number raises ValueError."""
        with self.assertRaises(ValueError) as context:
            CodeEntity(
                name="test",
                docstring="test",
                lineno=0,
                type="class",
                file_path="test.py"
            )
        
        self.assertEqual(
            str(context.exception),
            "Line number must be positive"
        )

    def test_empty_name(self):
        """Test entity with empty name."""
        entity = CodeEntity(
            name="",
            docstring="test",
            lineno=1,
            type="function",
            file_path="test.py"
        )
        self.assertEqual(entity.name, "")

    def test_empty_docstring(self):
        """Test entity with empty docstring."""
        entity = CodeEntity(
            name="test",
            docstring="",
            lineno=1,
            type="function",
            file_path="test.py"
        )
        self.assertEqual(entity.docstring, "")

    def test_empty_methods_list(self):
        """Test class entity with empty methods list."""
        entity = CodeEntity(
            name="TestClass",
            docstring="test",
            lineno=1,
            type="class",
            file_path="test.py",
            methods=[]
        )
        self.assertEqual(entity.methods, [])

    def test_no_parent_class(self):
        """Test class entity with no parent class."""
        entity = CodeEntity(
            name="TestClass",
            docstring="test",
            lineno=1,
            type="class",
            file_path="test.py"
        )
        self.assertIsNone(entity.parent_class)

if __name__ == '__main__':
    unittest.main()
