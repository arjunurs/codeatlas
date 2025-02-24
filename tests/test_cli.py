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
    get_api_keys,
    setup_logging,
    main,
    CodeDocumentationGenerator
)
from docgen.exceptions.errors import ApiKeyError
import logging

@pytest.fixture
def cli_setup():
    """Setup test data for CLI tests."""
    return {
        'test_source': 'src',
        'test_output': 'docs',
        'test_anthropic_key': 'test-anthropic-key',
        'test_openai_key': 'test-openai-key'
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
        '--anthropic-api-key', cli_setup['test_anthropic_key']
    ]

    with patch('sys.argv', ['docgen'] + test_args), \
         patch('docgen.setup_logging') as mock_setup_logging, \
         patch('docgen.get_api_keys', return_value=(cli_setup['test_anthropic_key'], cli_setup['test_openai_key'])) as mock_get_keys, \
         patch('docgen.CodeDocumentationGenerator') as mock_generator_class:

        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator

        main()

        # Verify function calls
        mock_setup_logging.assert_called_once()
        mock_get_keys.assert_called_once()
        mock_generator_class.assert_called_once()
        mock_generator.generate_documentation.assert_called_once_with(
            cli_setup['test_source'],
            cli_setup['test_output']
        )

def test_main_error(cli_setup):
    """Test main function with error."""
    test_args = [
        '--source', cli_setup['test_source']
    ]

    with patch('sys.argv', ['docgen'] + test_args), \
         patch('docgen.setup_logging') as mock_setup_logging, \
         patch('docgen.get_api_keys', side_effect=ApiKeyError("API key not found")):

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

    with patch('docgen.utils.api_keys.find_dotenv', return_value=str(env_file)):
        anthropic_key, openai_key = get_api_keys(None, None)
        assert anthropic_key == "dotenv-anthropic-key"
        assert openai_key == "dotenv-openai-key"

if __name__ == '__main__':
    unittest.main()
