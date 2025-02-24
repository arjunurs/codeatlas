"""Integration tests for the documentation generator.

This module contains end-to-end tests that verify the complete documentation
generation process works correctly with all components integrated.
"""

import os
import pytest
from pathlib import Path
import tempfile
import shutil
from bs4 import BeautifulSoup

from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import DocumentationError

@pytest.fixture
def sample_project():
    """Create a temporary Python project for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # Create a simple Python package structure
        src_dir = project_dir / "src" / "mypackage"
        src_dir.mkdir(parents=True)
        
        # Create __init__.py
        with open(src_dir / "__init__.py", "w") as f:
            f.write('"""Test package."""\n\n__version__ = "0.1.0"\n')
        
        # Create main module
        with open(src_dir / "main.py", "w") as f:
            f.write('''"""Main module for test package."""

from typing import List, Optional
from .utils import helper

class MainClass:
    """Main class implementation."""
    
    def __init__(self, name: str):
        """Initialize the class.
        
        Args:
            name: Instance name
        """
        self.name = name
        self._helper = helper.Helper()
    
    def process_data(self, data: List[str]) -> Optional[dict]:
        """Process input data.
        
        Args:
            data: List of strings to process
            
        Returns:
            Processed data as dictionary or None if processing fails
        """
        try:
            return self._helper.transform(data)
        except Exception as e:
            print(f"Error processing data: {e}")
            return None
''')
        
        # Create utils module
        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        with open(utils_dir / "__init__.py", "w") as f:
            f.write("")
        
        # Create helper module
        with open(utils_dir / "helper.py", "w") as f:
            f.write('''"""Helper utilities."""

from typing import List
from .validator import validate_input

class Helper:
    """Helper class for data transformation."""
    
    def transform(self, data: List[str]) -> dict:
        """Transform input data.
        
        Args:
            data: List of strings to transform
            
        Returns:
            Transformed data as dictionary
            
        Raises:
            ValueError: If input data is invalid
        """
        if not validate_input(data):
            raise ValueError("Invalid input data")
            
        result = {}
        for item in data:
            key, value = item.split(":")
            result[key.strip()] = value.strip()
        return result
''')
        
        # Create validator module
        with open(utils_dir / "validator.py", "w") as f:
            f.write('''"""Input validation utilities."""

from typing import List

def validate_input(data: List[str]) -> bool:
    """Validate input data format.
    
    Args:
        data: List of strings to validate
        
    Returns:
        True if data is valid, False otherwise
    """
    if not data:
        return False
        
    return all(":" in item for item in data)
''')
        
        # Create requirements.txt
        with open(project_dir / "requirements.txt", "w") as f:
            f.write("""
typing-extensions>=4.5.0
pytest>=7.0.0
black>=22.0.0
""")
        
        yield project_dir

def test_end_to_end_documentation_generation(sample_project):
    """Test the complete documentation generation process."""
    # Create output directory
    output_dir = sample_project / "docs"
    output_dir.mkdir()
    
    # Initialize generator with test API keys
    generator = CodeDocumentationGenerator(
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key"
    )
    
    # Generate documentation
    generator.generate_documentation(
        str(sample_project / "src" / "mypackage"),
        str(output_dir)
    )
    
    # Verify documentation file was created
    doc_file = output_dir / "documentation.html"
    assert doc_file.exists()
    
    # Parse and verify HTML content
    with open(doc_file) as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        
        # Check basic structure
        assert soup.title
        assert soup.find_all('section')
        
        # Check for main content sections
        sections = soup.find_all('section')
        section_titles = {s.find('h2').text.strip() for s in sections if s.find('h2')}
        expected_titles = {
            'Overview',
            'Dependencies',
            'Key Classes and Functions',
            'Data Flow',
            'Integration Points'
        }
        assert expected_titles.issubset(section_titles)
        
        # Check for diagrams
        diagrams = soup.find_all('div', class_='mermaid')
        assert len(diagrams) >= 3  # Should have at least architecture, class, and sequence diagrams
        
        # Verify diagram content
        diagram_types = {
            'graph TD',  # Architecture/dependency diagrams
            'classDiagram',  # Class diagram
            'sequenceDiagram'  # Sequence diagram
        }
        diagram_contents = {d.text.strip().split('\n')[0] for d in diagrams}
        assert any(t in diagram_contents for t in diagram_types)
        
        # Check for code analysis content
        assert 'MainClass' in soup.text
        assert 'Helper' in soup.text
        assert 'validate_input' in soup.text
        
        # Check for docstring content
        assert 'Main class implementation' in soup.text
        assert 'Helper class for data transformation' in soup.text
        assert 'Validate input data format' in soup.text

def test_end_to_end_error_handling(sample_project):
    """Test error handling in the end-to-end process."""
    generator = CodeDocumentationGenerator(
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key"
    )
    
    # Test with invalid source directory
    with pytest.raises(ValueError):
        generator.generate_documentation(
            "/nonexistent/dir",
            str(sample_project / "docs")
        )
    
    # Test with invalid Python files
    invalid_dir = sample_project / "invalid"
    invalid_dir.mkdir()
    with open(invalid_dir / "invalid.py", "w") as f:
        f.write("def invalid_syntax(:")
    
    with pytest.raises(DocumentationError):
        generator.generate_documentation(
            str(invalid_dir),
            str(sample_project / "docs")
        )
    
    # Test with empty directory
    empty_dir = sample_project / "empty"
    empty_dir.mkdir()
    
    with pytest.raises(DocumentationError):
        generator.generate_documentation(
            str(empty_dir),
            str(sample_project / "docs")
        )

def test_end_to_end_large_project_handling(sample_project):
    """Test handling of a larger project structure."""
    # Create additional modules and packages
    src_dir = sample_project / "src" / "mypackage"
    
    # Add more modules
    for i in range(5):
        module_dir = src_dir / f"module{i}"
        module_dir.mkdir()
        with open(module_dir / "__init__.py", "w") as f:
            f.write(f'"""Module {i} package."""\n')
        
        # Add several Python files to each module
        for j in range(3):
            with open(module_dir / f"file{j}.py", "w") as f:
                f.write(f'''"""Test file {j} in module {i}."""

class TestClass{i}{j}:
    """Test class."""
    
    def method1(self):
        """Test method 1."""
        pass
        
    def method2(self):
        """Test method 2."""
        pass
''')
    
    # Generate documentation
    output_dir = sample_project / "docs"
    output_dir.mkdir()
    
    generator = CodeDocumentationGenerator(
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key"
    )
    
    generator.generate_documentation(str(src_dir), str(output_dir))
    
    # Verify documentation was generated
    doc_file = output_dir / "documentation.html"
    assert doc_file.exists()
    
    # Check content handling
    with open(doc_file) as f:
        content = f.read()
        
        # Verify all modules are included
        for i in range(5):
            assert f"module{i}" in content
            for j in range(3):
                assert f"TestClass{i}{j}" in content
        
        # Verify diagram generation didn't fail
        assert "graph TD" in content  # Architecture diagram
        assert "classDiagram" in content  # Class diagram
        assert "sequenceDiagram" in content  # Sequence diagram 