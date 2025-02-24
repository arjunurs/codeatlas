"""Unit tests for the CodeAnalyzer class.

This module contains comprehensive tests for code analysis functionality,
including file parsing, entity extraction, and dependency analysis.
"""

import os
import ast
import pytest
from unittest.mock import patch, mock_open
from docgen.core.analyzer import CodeAnalyzer
from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis
from docgen.exceptions.errors import CodeParseError

@pytest.fixture
def analyzer():
    """Create a CodeAnalyzer instance for testing."""
    return CodeAnalyzer(skip_validation=True)

@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return '''"""Module docstring."""

import os
from typing import List

class TestClass:
    """Test class docstring."""
    
    def __init__(self):
        """Initialize the class."""
        pass
    
    def test_method(self, param: str) -> None:
        """Test method docstring."""
        print(param)

def test_function(x: int) -> int:
    """Test function docstring."""
    return x * 2
'''

def test_analyze_file_success(analyzer, tmp_path, sample_python_code):
    """Test successful file analysis."""
    # Create a temporary Python file
    test_file = tmp_path / "test.py"
    test_file.write_text(sample_python_code)
    
    # Analyze the file
    analysis = analyzer.analyze_file(str(test_file))
    
    # Verify basic properties
    assert isinstance(analysis, FileAnalysis)
    assert analysis.file_path == str(test_file)
    assert analysis.content == sample_python_code
    
    # Verify imports
    assert len(analysis.imports) == 2
    assert "os" in analysis.imports
    assert "typing.List" in analysis.imports
    
    # Verify entities
    assert len(analysis.entities) == 2  # TestClass and test_function
    
    # Find class entity
    class_entity = next(e for e in analysis.entities if e.type == "class")
    assert class_entity.name == "TestClass"
    assert "Test class docstring" in class_entity.docstring
    assert len(class_entity.methods) == 2  # __init__ and test_method
    
    # Find function entity
    func_entity = next(e for e in analysis.entities if e.type == "function")
    assert func_entity.name == "test_function"
    assert "Test function docstring" in func_entity.docstring

def test_analyze_empty_init_file(analyzer, tmp_path):
    """Test analyzing an empty __init__.py file."""
    init_file = tmp_path / "__init__.py"
    init_file.write_text("")
    
    analysis = analyzer.analyze_file(str(init_file))
    assert isinstance(analysis, FileAnalysis)
    assert analysis.file_path == str(init_file)
    assert not analysis.content
    assert not analysis.entities
    assert not analysis.imports

def test_analyze_file_syntax_error(analyzer, tmp_path):
    """Test analyzing a file with syntax errors."""
    test_file = tmp_path / "invalid.py"
    test_file.write_text("def invalid_syntax(:")
    
    with pytest.raises(CodeParseError) as exc_info:
        analyzer.analyze_file(str(test_file))
    assert "Failed to parse" in str(exc_info.value)

def test_analyze_file_not_found(analyzer):
    """Test analyzing a nonexistent file."""
    with pytest.raises(CodeParseError) as exc_info:
        analyzer.analyze_file("/nonexistent/file.py")
    assert "File does not exist" in str(exc_info.value)

def test_analyze_directory_success(analyzer, tmp_path, sample_python_code):
    """Test successful directory analysis."""
    # Create test files
    (tmp_path / "module1.py").write_text(sample_python_code)
    (tmp_path / "module2.py").write_text(sample_python_code)
    os.makedirs(tmp_path / "subdir")
    (tmp_path / "subdir" / "module3.py").write_text(sample_python_code)
    
    analyses = analyzer.analyze_directory(str(tmp_path))
    
    assert len(analyses) == 3
    assert all(isinstance(a, FileAnalysis) for a in analyses)
    assert len({a.file_path for a in analyses}) == 3  # All paths should be unique

def test_analyze_directory_no_python_files(analyzer, tmp_path):
    """Test analyzing a directory with no Python files."""
    with pytest.raises(CodeParseError) as exc_info:
        analyzer.analyze_directory(str(tmp_path))
    assert "No Python files found" in str(exc_info.value)

def test_analyze_directory_not_found(analyzer):
    """Test analyzing a nonexistent directory."""
    with pytest.raises(CodeParseError) as exc_info:
        analyzer.analyze_directory("/nonexistent/dir")
    assert "Directory does not exist" in str(exc_info.value)

def test_analyze_dependencies_success(analyzer):
    """Test successful dependency analysis."""
    requirements_content = """
requests>=2.25.1
pandas>=1.2.0
numpy>=1.19.2
"""
    with patch("builtins.open", mock_open(read_data=requirements_content)):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pkg_resources.working_set.by_key") as mock_pkg:
                # Mock package dependencies
                mock_pkg.__getitem__.return_value.requires.return_value = []
                
                deps = analyzer.analyze_dependencies()
                
                assert isinstance(deps, dict)
                assert "requests" in deps
                assert "pandas" in deps
                assert "numpy" in deps

def test_analyze_dependencies_no_requirements(analyzer):
    """Test dependency analysis with no requirements.txt."""
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_dependencies()

def test_analyze_dependencies_empty_requirements(analyzer):
    """Test dependency analysis with empty requirements.txt."""
    with patch("builtins.open", mock_open(read_data="")):
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            with pytest.raises(ValueError) as exc_info:
                analyzer.analyze_dependencies()
            assert "requirements.txt is empty" in str(exc_info.value)

def test_analyze_function_calls(analyzer, sample_python_code):
    """Test function call analysis."""
    analysis = FileAnalysis(
        file_path="test.py",
        entities=[],
        imports=[],
        content=sample_python_code,
        _skip_validation=True
    )
    
    call_graph = analyzer.analyze_function_calls([analysis])
    
    assert isinstance(call_graph, dict)
    assert "test_method" in call_graph
    assert "print" in call_graph["test_method"]

def test_extract_entities(analyzer):
    """Test entity extraction from AST."""
    code = '''
class TestClass:
    """Test class."""
    def method1(self):
        """Method 1."""
        pass

def test_func():
    """Test function."""
    pass
'''
    tree = ast.parse(code)
    entities = analyzer._extract_entities(tree, "test.py")
    
    assert len(entities) == 2
    assert any(e.name == "TestClass" and e.type == "class" for e in entities)
    assert any(e.name == "test_func" and e.type == "function" for e in entities)

def test_extract_imports(analyzer):
    """Test import statement extraction from AST."""
    code = '''
import os
import sys as system
from typing import List, Optional
from .utils import helper
'''
    tree = ast.parse(code)
    imports = analyzer._extract_imports(tree)
    
    assert len(imports) == 4
    assert "os" in imports
    assert "sys" in imports
    assert "typing.List" in imports
    assert "typing.Optional" in imports 