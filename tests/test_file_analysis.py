"""Unit tests for the FileAnalysis class.

This module contains comprehensive tests for the FileAnalysis class, including
validation, edge cases, and error conditions.
"""

import os
import unittest
from unittest.mock import patch, mock_open
from docgen import FileAnalysis, CodeEntity

class TestFileAnalysis(unittest.TestCase):
    """Test cases for the FileAnalysis class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_file = "test.py"
        self.test_content = "print('Hello, World!')"
        self.test_entities = [
            CodeEntity(
                name="TestClass",
                docstring="Test class",
                lineno=1,
                type="class",
                file_path=self.test_file
            )
        ]
        self.test_imports = ["os", "sys"]

    def test_valid_file_analysis(self):
        """Test creating a valid FileAnalysis instance."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=self.test_entities,
            imports=self.test_imports,
            content=self.test_content,
            _skip_validation=True
        )

        self.assertEqual(analysis.file_path, self.test_file)
        self.assertEqual(analysis.entities, self.test_entities)
        self.assertEqual(analysis.imports, self.test_imports)
        self.assertEqual(analysis.content, self.test_content)
        self.assertIsNone(analysis.error)

    def test_nonexistent_file(self):
        """Test that nonexistent file raises ValueError."""
        with self.assertRaises(ValueError) as context:
            FileAnalysis(
                file_path="nonexistent.py",
                entities=[],
                imports=[],
                content=""
            )
        
        self.assertEqual(
            str(context.exception),
            "File does not exist: nonexistent.py"
        )

    def test_empty_content(self):
        """Test that empty content raises ValueError."""
        with self.assertRaises(ValueError) as context:
            FileAnalysis(
                file_path=self.test_file,
                entities=[],
                imports=[],
                content="",
                _skip_validation=True
            )
        
        self.assertEqual(
            str(context.exception),
            "File content cannot be empty"
        )

    def test_with_error(self):
        """Test FileAnalysis with error message."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[],
            imports=[],
            content=self.test_content,
            error="Test error message",
            _skip_validation=True
        )

        self.assertEqual(analysis.error, "Test error message")

    def test_empty_entities(self):
        """Test FileAnalysis with empty entities list."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[],
            imports=self.test_imports,
            content=self.test_content,
            _skip_validation=True
        )

        self.assertEqual(analysis.entities, [])

    def test_empty_imports(self):
        """Test FileAnalysis with empty imports list."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=self.test_entities,
            imports=[],
            content=self.test_content,
            _skip_validation=True
        )

        self.assertEqual(analysis.imports, [])

    def test_multiple_entities(self):
        """Test FileAnalysis with multiple entities."""
        entities = [
            CodeEntity(
                name="TestClass1",
                docstring="Test class 1",
                lineno=1,
                type="class",
                file_path=self.test_file
            ),
            CodeEntity(
                name="test_function",
                docstring="Test function",
                lineno=10,
                type="function",
                file_path=self.test_file
            )
        ]

        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=entities,
            imports=self.test_imports,
            content=self.test_content,
            _skip_validation=True
        )

        self.assertEqual(len(analysis.entities), 2)
        self.assertEqual(analysis.entities[0].name, "TestClass1")
        self.assertEqual(analysis.entities[1].name, "test_function")

    def test_multiple_imports(self):
        """Test FileAnalysis with multiple imports."""
        imports = ["os", "sys", "json", "typing"]
        
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=self.test_entities,
            imports=imports,
            content=self.test_content,
            _skip_validation=True
        )

        self.assertEqual(len(analysis.imports), 4)
        self.assertIn("os", analysis.imports)
        self.assertIn("sys", analysis.imports)
        self.assertIn("json", analysis.imports)
        self.assertIn("typing", analysis.imports)

if __name__ == '__main__':
    unittest.main()
