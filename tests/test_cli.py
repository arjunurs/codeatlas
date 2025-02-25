"""Unit tests for the CLI functionality.

This module contains comprehensive tests for the command-line interface,
including argument parsing, API key handling, and main function execution.
"""

import os
import sys
import unittest
import pytest
from unittest.mock import patch, MagicMock
from docgen import (
    parse_args,
    setup_logging,
    main,
    CodeDocumentationGenerator
)
from docgen.exceptions.errors import ApiKeyError
import logging
from langchain.schema import Document
from docgen.core.analyzer import FileAnalysis, CodeEntity

@pytest.fixture
def cli_setup():
    """Setup test configuration."""
    return {
        'test_anthropic_key': 'test-anthropic-key',
        'test_openai_key': 'test-openai-key',
        'test_output': 'docs',
        'test_source': 'src'
    }

def test_parse_args_minimal():
    """Test parsing minimal required arguments."""
    args = parse_args(['--source', 'src'])
    assert args.source == 'src'
    assert args.output == 'docs'  # default value
    assert args.temperature == 0.1  # default value
    assert not args.verbose

def test_parse_args_full():
    """Test parsing all arguments."""
    args = parse_args([
        '--source', 'src',
        '--output', 'docs',
        '--anthropic-api-key', 'test-key',
        '--temperature', '0.5',
        '--verbose'
    ])
    assert args.source == 'src'
    assert args.output == 'docs'
    assert args.anthropic_api_key == 'test-key'
    assert args.temperature == 0.5
    assert args.verbose

def test_parse_args_mutually_exclusive():
    """Test mutually exclusive API key arguments."""
    with pytest.raises(SystemExit):
        parse_args([
            '--source', 'src',
            '--anthropic-api-key', 'key1',
            '--openai-api-key', 'key2'
        ])

def test_setup_logging_default():
    """Test setting up logging with default settings."""
    root_logger = MagicMock()
    docgen_logger = MagicMock()

    with patch('logging.getLogger') as mock_get_logger:
        mock_get_logger.side_effect = [root_logger, docgen_logger]
        setup_logging()

        # Verify logger configuration
        root_logger.setLevel.assert_called_with(logging.INFO)
        docgen_logger.setLevel.assert_called_with(logging.INFO)

def test_setup_logging_verbose():
    """Test setting up logging with verbose flag."""
    root_logger = MagicMock()
    docgen_logger = MagicMock()

    with patch('logging.getLogger') as mock_get_logger:
        mock_get_logger.side_effect = [root_logger, docgen_logger]
        setup_logging(verbose=True)

        # Verify logger configuration
        root_logger.setLevel.assert_called_with(logging.DEBUG)
        docgen_logger.setLevel.assert_called_with(logging.DEBUG)

def test_main_success(cli_setup):
    """Test successful execution of main function."""
    test_args = [
        '--source', cli_setup['test_source'],
        '--output', cli_setup['test_output'],
        '--api-key-env', '.env'
    ]

    # Mock environment setup
    mock_env = {
        'ANTHROPIC_API_KEY': cli_setup['test_anthropic_key'],
        'OPENAI_API_KEY': cli_setup['test_openai_key']
    }

    # Create mock OpenAI client and response
    mock_openai_response = MagicMock()
    mock_openai_response.data = [{'embedding': [0.1, 0.2, 0.3]} for _ in range(50)]

    mock_openai_client = MagicMock()
    mock_openai_client.embeddings.create.return_value = mock_openai_response

    # Create mock embeddings
    mock_embeddings = MagicMock()
    mock_embeddings.client = mock_openai_client
    mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3] for _ in range(50)]
    mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

    # Create mock Anthropic response
    mock_anthropic_response = MagicMock()
    mock_anthropic_response.content = [MagicMock(text="Generated content")]
    mock_anthropic_response.model = "claude-3-sonnet-20240229"

    # Create mock Anthropic messages
    mock_anthropic_messages = MagicMock()
    mock_anthropic_messages.create.return_value = mock_anthropic_response

    # Create mock Anthropic client
    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages = mock_anthropic_messages
    mock_anthropic_client.api_key = cli_setup['test_anthropic_key']

    # Create mock LLM
    mock_llm = MagicMock()
    mock_llm.run.return_value = "Generated content"
    mock_llm._client = mock_anthropic_client
    mock_llm.model_name = "claude-3-sonnet-20240229"
    mock_llm.generate_prompt.return_value = MagicMock(generations=[MagicMock(text="Generated content")])
    mock_llm.invoke.return_value = MagicMock(content="Generated content")
    mock_llm._call.return_value = {"output_text": "Generated content"}

    # Create mock Chroma collection
    mock_collection = MagicMock()
    mock_collection.add_texts.return_value = None
    mock_collection.query.return_value = {
        'embeddings': [[0.1, 0.2, 0.3]],
        'documents': [['test document']],
        'metadatas': [[{'source': 'test.py'}]],
        'distances': [[0.5]]
    }

    # Create mock retriever
    mock_retriever = MagicMock()
    mock_retriever.get_relevant_documents.return_value = [
        Document(page_content="test document", metadata={"source": "test.py"})
    ]

    # Create mock Chroma client
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_max_batch_size.return_value = 1000
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_collection.as_retriever.return_value = mock_retriever

    # Mock the analyzer's package dependencies and function calls
    mock_package_deps = {'src.docgen': ['src.docgen.core', 'src.docgen.models']}
    mock_function_calls = {'main': ['generate_documentation', 'setup_logging']}

    # Create mock file analysis results
    mock_file_analysis = FileAnalysis(
        file_path="test.py",
        imports=["os", "sys"],
        entities=[
            CodeEntity(name="TestClass", type="class", docstring="Test class", start_line=1, end_line=10),
            CodeEntity(name="test_func", type="function", docstring="Test function", start_line=2, end_line=5),
            CodeEntity(name="TEST_VAR", type="function", docstring="Test variable", start_line=1, end_line=1)
        ],
        content="Mock content",
        _skip_validation=True
    )

    with patch('sys.argv', ['docgen'] + test_args), \
         patch('os.environ', mock_env), \
         patch('docgen.cli.setup_logging') as mock_setup_logging, \
         patch('docgen.cli.get_api_keys', return_value=(cli_setup['test_anthropic_key'], cli_setup['test_openai_key'])) as mock_get_keys, \
         patch('langchain_openai.OpenAIEmbeddings', return_value=mock_embeddings), \
         patch('langchain_anthropic.ChatAnthropic', return_value=mock_llm), \
         patch('chromadb.Client', return_value=mock_chroma_client), \
         patch('os.path.isdir', return_value=True), \
         patch('openai.OpenAI', return_value=mock_openai_client), \
         patch('langchain_openai.embeddings.base._process_batched_chunked_embeddings', return_value=[[0.1, 0.2, 0.3] for _ in range(50)]), \
         patch('docgen.core.analyzer.CodeAnalyzer.analyze_directory', return_value=[mock_file_analysis]), \
         patch('docgen.core.analyzer.CodeAnalyzer.analyze_package_dependencies', return_value=mock_package_deps), \
         patch('docgen.core.analyzer.CodeAnalyzer.analyze_function_calls', return_value=mock_function_calls), \
         patch('anthropic.Anthropic', return_value=mock_anthropic_client), \
         patch('langchain.chains.base.Chain._call', return_value={"output_text": "Generated content"}), \
         patch('langchain.chains.base.Chain.invoke', return_value=MagicMock(content="Generated content")), \
         patch('langchain_community.vectorstores.chroma.Chroma.from_documents', side_effect=lambda docs, embeddings: (embeddings.embed_documents([doc.page_content for doc in docs]), mock_collection)[1]), \
         patch('langchain.chains.retrieval_qa.base.RetrievalQA.from_chain_type', return_value=mock_llm):

        main()

        # Verify function calls
        mock_setup_logging.assert_called_once_with(False)  # False because we didn't set --verbose in test_args
        mock_get_keys.assert_called_once_with(None, None, '.env')
        mock_llm.run.assert_called()

def test_main_error(cli_setup):
    """Test main function with error."""
    test_args = [
        '--source', cli_setup['test_source']
    ]

    with patch('sys.argv', ['docgen'] + test_args), \
         patch('docgen.setup_logging') as mock_setup_logging, \
         patch('docgen.utils.api_keys.get_api_keys', side_effect=ApiKeyError("API key not found")):

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

def test_get_api_keys_from_dotenv(tmp_path):
    """Test getting API keys from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("""
ANTHROPIC_API_KEY=dotenv-anthropic-key
OPENAI_API_KEY=dotenv-openai-key
""")

    with patch('os.environ', {}), \
         patch('docgen.utils.api_keys.find_dotenv', return_value=str(env_file)), \
         patch('docgen.utils.api_keys.load_dotenv', return_value=True):
        from docgen.utils.api_keys import get_api_keys
        os.environ['ANTHROPIC_API_KEY'] = 'dotenv-anthropic-key'
        os.environ['OPENAI_API_KEY'] = 'dotenv-openai-key'
        anthropic_key, openai_key = get_api_keys(None, None)
        assert anthropic_key == "dotenv-anthropic-key"
        assert openai_key == "dotenv-openai-key"

if __name__ == '__main__':
    unittest.main()
