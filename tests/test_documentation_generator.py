"""Unit tests for the CodeDocumentationGenerator class.

This module contains comprehensive tests for the documentation generator,
including initialization, code analysis, and diagram generation.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import DocumentationError, ApiKeyError
from langchain_anthropic import ChatAnthropic
from docgen.models.file_analysis import FileAnalysis
from docgen.models.code_entity import CodeEntity
import os
import pytest

class TestCodeDocumentationGenerator:
    """Test cases for CodeDocumentationGenerator class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.anthropic_key = "test-anthropic-key"
        self.openai_key = "test-openai-key"
        
        # Create sample test data
        self.sample_entity = CodeEntity(
            name="TestClass",
            type="class",
            docstring="Test class docstring",
            methods=["test_method"],
            start_line=1,
            end_line=2,
            source="class TestClass:\n    pass"
        )
        
        self.sample_analysis = FileAnalysis(
            file_path="test.py",
            entities=[self.sample_entity],
            imports=["import os"],
            content="class TestClass:\n    pass",
            error=None,
            _skip_validation=True
        )

        # Setup mocks
        self.mock_llm = MagicMock()
        self.mock_llm.run = MagicMock(return_value="Generated content")
        
        self.mock_analyzer = MagicMock()
        self.mock_embeddings = MagicMock()
        self.mock_diagram_generator = MagicMock()
        
        # Set up mock return values
        self.mock_analyzer.analyze_directory.return_value = [self.sample_analysis]
        self.mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
        
        # Set up mock diagram generator returns
        self.mock_diagram_generator.generate_architecture_diagram.return_value = "graph TD\n    A-->B"
        self.mock_diagram_generator.generate_class_diagram.return_value = "classDiagram\n    class Test"
        self.mock_diagram_generator.generate_sequence_diagram.return_value = "sequenceDiagram\n    A->>B: call"
        self.mock_diagram_generator.generate_dependency_diagram.return_value = "graph TD\n    pkg1-->pkg2"
        self.mock_diagram_generator.generate_call_graph_diagram.return_value = "graph TD\n    func1-->func2"

        # Create generator instance with patches
        with patch('docgen.core.generator.ChatAnthropic', return_value=self.mock_llm), \
             patch('docgen.core.generator.OpenAIEmbeddings', return_value=self.mock_embeddings), \
             patch('docgen.core.generator.CodeAnalyzer', return_value=self.mock_analyzer), \
             patch('docgen.core.generator.DiagramGenerator', return_value=self.mock_diagram_generator):

            self.generator = CodeDocumentationGenerator(
                anthropic_api_key=self.anthropic_key,
                openai_api_key=self.openai_key
            )
            self.generator.llm = self.mock_llm
            self.generator.embeddings = self.mock_embeddings
            self.generator.analyzer = self.mock_analyzer
            self.generator.diagram_generator = self.mock_diagram_generator

    def test_init_with_api_key(self):
        """Test initialization with API keys."""
        assert isinstance(self.generator, CodeDocumentationGenerator)
        assert self.generator.llm is not None
        assert self.generator.embeddings is not None
        assert self.generator.analyzer is not None
        assert self.generator.diagram_generator is not None

    def test_init_no_api_key(self):
        """Test initialization without API keys."""
        with pytest.raises(ApiKeyError, match="Both Anthropic and OpenAI API keys are required"):
            CodeDocumentationGenerator(anthropic_api_key=None, openai_api_key=None)

    def test_generate_documentation_no_files(self, tmp_path):
        """Test documentation generation with no Python files."""
        source_dir = tmp_path / "empty"
        source_dir.mkdir()
        output_dir = tmp_path / "docs"
        
        # Mock analyzer to return empty list
        self.mock_analyzer.analyze_directory.return_value = []
        
        with pytest.raises(DocumentationError, match="No Python files found in directory"):
            self.generator.generate_documentation(str(source_dir), str(output_dir))

    def test_generate_documentation_invalid_dir(self, tmp_path):
        """Test documentation generation with invalid directory."""
        source_dir = tmp_path / "nonexistent"
        output_dir = tmp_path / "docs"

        with pytest.raises(ValueError, match="Invalid source directory"):
            self.generator.generate_documentation(str(source_dir), str(output_dir))

    def test_generate_documentation(self, tmp_path):
        """Test successful documentation generation."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        output_dir = tmp_path / "docs"
        output_dir.mkdir()

        # Create a test Python file
        test_file = source_dir / "test.py"
        test_file.write_text("class TestClass:\n    def test_method(self):\n        pass")

        # Mock QA chain
        mock_qa_chain = MagicMock()
        mock_qa_chain.run.return_value = "Generated content"

        with patch("docgen.core.generator.Chroma") as mock_chroma, \
             patch("docgen.core.generator.RetrievalQA") as mock_qa, \
             patch("docgen.core.generator.get_documentation_template") as mock_template:

            mock_vector_store = MagicMock()
            mock_vector_store.as_retriever.return_value = MagicMock()
            mock_chroma.from_documents.return_value = mock_vector_store
            mock_qa.from_chain_type.return_value = mock_qa_chain
            mock_template.return_value.render.return_value = "<html>Test</html>"

            with patch("builtins.open", mock_open()) as mock_file:
                self.generator.generate_documentation(str(source_dir), str(output_dir))
                mock_file.assert_called_with(os.path.join(str(output_dir), "documentation.html"), "w", encoding="utf-8")

    def test_parse_python_file(self, tmp_path):
        """Test parsing a Python file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("class TestClass:\n    def test_method(self):\n        pass")

        self.mock_analyzer.analyze_file.return_value = self.sample_analysis
        result = self.mock_analyzer.analyze_file(str(test_file))
        
        assert isinstance(result, FileAnalysis)
        assert len(result.entities) > 0
        assert result.entities[0].name == "TestClass"

    def test_parse_python_file_io_error(self, tmp_path):
        """Test parsing a non-existent Python file."""
        test_file = tmp_path / "nonexistent.py"
        
        self.mock_analyzer.analyze_file.side_effect = IOError("File not found")
        with pytest.raises(IOError):
            self.mock_analyzer.analyze_file(str(test_file))

    def test_analyze_function_calls(self):
        """Test analyzing function calls."""
        mock_call_graph = {"func1": {"func2"}}
        self.mock_analyzer.analyze_function_calls.return_value = mock_call_graph
        result = self.mock_analyzer.analyze_function_calls([self.sample_analysis])
        assert isinstance(result, dict)
        assert result == mock_call_graph

    def test_analyze_package_dependencies(self):
        """Test analyzing package dependencies."""
        mock_deps = {"pkg1": {"dep1", "dep2"}}
        self.mock_analyzer.analyze_package_dependencies.return_value = mock_deps
        result = self.mock_analyzer.analyze_package_dependencies()
        assert isinstance(result, dict)
        assert result == mock_deps

    def test_generate_class_diagram(self):
        """Test generating class diagram."""
        result = self.mock_diagram_generator.generate_class_diagram([self.sample_analysis])
        assert isinstance(result, str)
        assert "classDiagram" in result

    def test_generate_sequence_diagram(self):
        """Test generating sequence diagram."""
        result = self.mock_diagram_generator.generate_sequence_diagram([self.sample_analysis])
        assert isinstance(result, str)
        assert "sequenceDiagram" in result

    def test_generate_architecture_diagram(self):
        """Test generating architecture diagram."""
        result = self.mock_diagram_generator.generate_architecture_diagram([self.sample_analysis])
        assert isinstance(result, str)
        assert "graph TD" in result

if __name__ == '__main__':
    unittest.main()
