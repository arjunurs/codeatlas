"""Unit tests for the CodeDocumentationGenerator class.

This module contains comprehensive tests for the documentation generator,
including initialization, code analysis, and diagram generation.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from docgen import (
    CodeDocumentationGenerator,
    ApiKeyError,
    CodeEntity,
    FileAnalysis,
    CodeParseError
)

class TestCodeDocumentationGenerator(unittest.TestCase):
    """Test cases for the CodeDocumentationGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.test_content = "def test_function():\n    pass"
        self.test_file = "test.py"

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    def test_init_with_api_key(self, mock_chat_anthropic, mock_anthropic):
        """Test initialization with direct API key."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat

        generator = CodeDocumentationGenerator(api_key=self.api_key)

        self.assertEqual(generator.temperature, 0.1)
        mock_anthropic.assert_called_once_with(api_key=self.api_key)
        mock_chat_anthropic.assert_called_once()

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-api-key'})
    def test_init_with_env_api_key(self, mock_chat_anthropic, mock_anthropic):
        """Test initialization with API key from environment."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat

        generator = CodeDocumentationGenerator()

        mock_anthropic.assert_called_once_with(api_key='env-api-key')
        mock_chat_anthropic.assert_called_once()

    def test_init_no_api_key(self):
        """Test initialization with no API key."""
        with patch.dict('os.environ', clear=True):
            with patch('docgen.find_dotenv', return_value=None):
                with self.assertRaises(ApiKeyError):
                    CodeDocumentationGenerator()

    def test_init_invalid_temperature(self):
        """Test initialization with invalid temperature."""
        with self.assertRaises(ValueError):
            CodeDocumentationGenerator(api_key=self.api_key, temperature=2.0)

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('docgen.ast.parse')
    @patch('builtins.open', new_callable=mock_open)
    def test_parse_python_file(self, mock_file, mock_ast_parse, mock_chat_anthropic, mock_anthropic):
        """Test parsing a Python file."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat
        mock_file.return_value.read.return_value = self.test_content
        mock_ast_parse.return_value = MagicMock(body=[])

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        analysis = generator.parse_python_file(self.test_file)

        self.assertIsInstance(analysis, FileAnalysis)
        self.assertEqual(analysis.file_path, self.test_file)
        self.assertEqual(analysis.content, self.test_content)
        self.assertEqual(analysis.entities, [])
        self.assertEqual(analysis.imports, [])

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('docgen.ast.parse')
    @patch('builtins.open')
    def test_parse_python_file_io_error(self, mock_open, mock_ast_parse, mock_chat_anthropic, mock_anthropic):
        """Test parsing a Python file with IO error."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat
        mock_open.side_effect = IOError("Test IO Error")

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        with self.assertRaises(CodeParseError) as context:
            generator.parse_python_file(self.test_file)
        self.assertEqual(str(context.exception), "Failed to parse test.py: Test IO Error")

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    def test_generate_architecture_diagram(self, mock_chat_anthropic, mock_anthropic):
        """Test generating architecture diagram."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        files = [
            FileAnalysis(
                file_path=self.test_file,
                entities=[],
                imports=[],
                content=self.test_content,
                _skip_validation=True
            )
        ]
        diagram = generator.generate_architecture_diagram(files)
        self.assertIsInstance(diagram, str)

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    def test_generate_class_diagram(self, mock_chat_anthropic, mock_anthropic):
        """Test generating class diagram."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        files = [
            FileAnalysis(
                file_path=self.test_file,
                entities=[
                    CodeEntity(
                        name="TestClass",
                        docstring="Test class",
                        lineno=1,
                        type="class",
                        file_path=self.test_file
                    )
                ],
                imports=[],
                content=self.test_content,
                _skip_validation=True
            )
        ]
        diagram = generator.generate_class_diagram(files)
        self.assertIsInstance(diagram, str)

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('docgen.RetrievalQA')
    def test_generate_sequence_diagram(self, mock_qa, mock_chat_anthropic, mock_anthropic):
        """Test generating sequence diagram."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat
        mock_qa_instance = MagicMock()
        mock_qa_instance.run.return_value = "Test workflow info"
        mock_qa.return_value = mock_qa_instance

        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.content = "sequenceDiagram\n    User->>System: Test"
        mock_chat.return_value = mock_response

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        diagram = generator.generate_sequence_diagram(mock_qa_instance)
        self.assertIsInstance(diagram, str)
        self.assertTrue(diagram.startswith("sequenceDiagram"))

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('os.path.exists')
    def test_analyze_package_dependencies(self, mock_exists, mock_chat_anthropic, mock_anthropic):
        """Test analyzing package dependencies."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat
        mock_exists.return_value = True

        with patch('builtins.open', mock_open(read_data="requests>=2.0.0\npandas>=1.0.0")):
            generator = CodeDocumentationGenerator(api_key=self.api_key)
            deps = generator.analyze_package_dependencies()
            self.assertIsInstance(deps, dict)

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    def test_analyze_function_calls(self, mock_chat_anthropic, mock_anthropic):
        """Test analyzing function calls."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        files = [
            FileAnalysis(
                file_path=self.test_file,
                entities=[],
                imports=[],
                content=self.test_content,
                _skip_validation=True
            )
        ]
        calls = generator.analyze_function_calls(files)
        self.assertIsInstance(calls, dict)

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('os.path.isdir')
    @patch('os.makedirs')
    @patch('glob.glob')
    @patch('os.path.exists')
    @patch('docgen.OpenAIEmbeddings')
    @patch('docgen.Chroma')
    @patch('docgen.RetrievalQA')
    def test_generate_documentation(self, mock_retrieval_qa, mock_chroma, mock_embeddings, mock_exists, mock_glob, mock_makedirs, mock_isdir, mock_chat_anthropic, mock_anthropic):
        """Test generating documentation."""
        # Mock Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Mock ChatAnthropic
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content="Test content")
        mock_chat_anthropic.return_value = mock_chat
        
        # Mock directory checks
        mock_isdir.return_value = True
        mock_exists.return_value = True
        mock_glob.return_value = ["test.py"]

        # Mock embeddings and vector store
        mock_embeddings_instance = MagicMock()
        mock_embeddings.return_value = mock_embeddings_instance
        mock_vector_store = MagicMock()
        mock_chroma.from_documents.return_value = mock_vector_store
        mock_vector_store.as_retriever.return_value = MagicMock()

        # Mock RetrievalQA
        mock_qa = MagicMock()
        mock_qa.run.return_value = "Test content"
        mock_retrieval_qa.from_chain_type.return_value = mock_qa

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        
        # Mock package dependencies analysis
        with patch.object(generator, 'analyze_package_dependencies', return_value={"test": "1.0.0"}), \
             patch.object(generator, '_generate_dependency_diagram', return_value="test diagram"), \
             patch.object(generator, '_generate_call_graph_diagram', return_value="test diagram"), \
             patch('builtins.open', mock_open(read_data=self.test_content)):
            generator.generate_documentation("src", "docs")

    @patch('docgen.anthropic.Anthropic')
    @patch('docgen.ChatAnthropic')
    @patch('os.path.isdir')
    def test_generate_documentation_invalid_dir(self, mock_isdir, mock_chat_anthropic, mock_anthropic):
        """Test generating documentation with invalid directory."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_chat = MagicMock()
        mock_chat_anthropic.return_value = mock_chat
        mock_isdir.return_value = False

        generator = CodeDocumentationGenerator(api_key=self.api_key)
        with self.assertRaises(ValueError):
            generator.generate_documentation("invalid", "docs")

if __name__ == '__main__':
    unittest.main()
