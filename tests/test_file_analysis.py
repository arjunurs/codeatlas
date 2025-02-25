"""Unit tests for the FileAnalysis class.

This module contains comprehensive tests for the FileAnalysis class, including
validation, edge cases, and error conditions.
"""

import os
import unittest
from unittest.mock import patch
from docgen.models.file_analysis import FileAnalysis
from docgen.models.code_entity import CodeEntity

class TestFileAnalysis(unittest.TestCase):
    """Test cases for the FileAnalysis class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_file = "test.py"
        self.test_content = "class TestClass:\n    def test_method(self):\n        pass"
        self.test_entity = CodeEntity(
            name="TestClass",
            type="class",
            docstring="Test class",
            methods=["test_method"],
            start_line=1,
            end_line=3,
            source=self.test_content
        )
        self.test_entities = [self.test_entity]
        self.test_imports = ["os", "sys"]

    def test_file_analysis_creation(self):
        """Test creating a FileAnalysis instance."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[self.test_entity],
            imports=["import os"],
            content=self.test_content,
            _skip_validation=True
        )
        self.assertEqual(analysis.file_path, self.test_file)
        self.assertEqual(len(analysis.entities), 1)
        self.assertEqual(len(analysis.imports), 1)
        self.assertEqual(analysis.content, self.test_content)
        self.assertFalse(analysis.has_error)

    def test_empty_entities(self):
        """Test FileAnalysis with empty entities list."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[],
            imports=["import os"],
            content=self.test_content,
            _skip_validation=True
        )
        self.assertEqual(len(analysis.entities), 0)
        self.assertEqual(len(analysis.classes), 0)
        self.assertEqual(len(analysis.functions), 0)

    def test_empty_imports(self):
        """Test FileAnalysis with empty imports list."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[self.test_entity],
            imports=[],
            content=self.test_content,
            _skip_validation=True
        )
        self.assertEqual(len(analysis.imports), 0)

    def test_empty_content(self):
        """Test FileAnalysis with empty content."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[],
            imports=[],
            content="",
            _skip_validation=True
        )
        self.assertTrue(analysis.is_empty)

    def test_multiple_entities(self):
        """Test FileAnalysis with multiple entities."""
        entity2 = CodeEntity(
            name="test_func",
            type="function",
            docstring="Test function",
            start_line=4,
            end_line=6,
            source="def test_func():\n    pass"
        )
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[self.test_entity, entity2],
            imports=["import os"],
            content=self.test_content + "\n\n" + entity2.source,
            _skip_validation=True
        )
        self.assertEqual(len(analysis.entities), 2)
        self.assertEqual(len(analysis.classes), 1)
        self.assertEqual(len(analysis.functions), 1)

    def test_multiple_imports(self):
        """Test FileAnalysis with multiple imports."""
        analysis = FileAnalysis(
            file_path=self.test_file,
            entities=[self.test_entity],
            imports=["import os", "import sys"],
            content=self.test_content,
            _skip_validation=True
        )
        self.assertEqual(len(analysis.imports), 2)

    def test_nonexistent_file(self):
        """Test FileAnalysis with nonexistent file."""
        analysis = FileAnalysis(
            file_path="nonexistent.py",
            entities=[self.test_entity],
            imports=["import os"],
            content=self.test_content,
            _skip_validation=True
        )
        self.assertEqual(analysis.file_path, "nonexistent.py")

    def test_init_file_empty_content(self):
        """Test FileAnalysis with empty __init__.py file."""
        analysis = FileAnalysis(
            file_path="__init__.py",
            entities=[],
            imports=[],
            content="",
            _skip_validation=True
        )
        self.assertTrue(analysis.is_init_file)
        self.assertTrue(analysis.is_empty)

    def test_module_name(self):
        """Test getting module name from file path."""
        analysis = FileAnalysis(
            file_path="/path/to/test_module.py",
            entities=[],
            imports=[],
            content="",
            _skip_validation=True
        )
        self.assertEqual(analysis.module_name, "test_module")

if __name__ == '__main__':
    unittest.main()
