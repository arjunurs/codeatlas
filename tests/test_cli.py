"""Unit tests for the CLI functionality.

This module contains comprehensive tests for the command-line interface,
including argument parsing, API key handling, and main function execution.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from docgen import (
    parse_args,
    get_api_key,
    setup_logging,
    main,
    CodeDocumentationGenerator
)

class TestCLI(unittest.TestCase):
    """Test cases for the CLI functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_api_key = "test-api-key"
        self.test_source = "src"
        self.test_output = "docs"

    def test_parse_args_minimal(self):
        """Test parsing minimal required arguments."""
        test_args = ["docgen", "--source", self.test_source]
        
        with patch.object(sys, 'argv', test_args):
            args = parse_args()
            
            self.assertEqual(args.source, self.test_source)
            self.assertEqual(args.output, "docs")  # Default value
            self.assertIsNone(args.api_key)
            self.assertIsNone(args.api_key_env)
            self.assertEqual(args.temperature, 0.1)
            self.assertFalse(args.verbose)

    def test_parse_args_full(self):
        """Test parsing all possible arguments."""
        test_args = [
            "docgen",
            "--source", self.test_source,
            "--output", self.test_output,
            "--api-key", self.test_api_key,
            "--temperature", "0.5",
            "--verbose"
        ]
        
        with patch.object(sys, 'argv', test_args):
            args = parse_args()
            
            self.assertEqual(args.source, self.test_source)
            self.assertEqual(args.output, self.test_output)
            self.assertEqual(args.api_key, self.test_api_key)
            self.assertEqual(args.temperature, 0.5)
            self.assertTrue(args.verbose)

    def test_parse_args_custom_env(self):
        """Test parsing with custom API key environment variable."""
        test_args = [
            "docgen",
            "--source", self.test_source,
            "--api-key-env", "CUSTOM_API_KEY"
        ]
        
        with patch.object(sys, 'argv', test_args):
            args = parse_args()
            
            self.assertEqual(args.api_key_env, "CUSTOM_API_KEY")
            self.assertIsNone(args.api_key)

    def test_parse_args_mutually_exclusive(self):
        """Test that api-key and api-key-env are mutually exclusive."""
        test_args = [
            "docgen",
            "--source", self.test_source,
            "--api-key", self.test_api_key,
            "--api-key-env", "CUSTOM_API_KEY"
        ]
        
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit):
                parse_args()

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-api-key'})
    def test_get_api_key_from_env(self):
        """Test getting API key from environment variable."""
        api_key = get_api_key(None, None)
        self.assertEqual(api_key, 'env-api-key')

    @patch.dict('os.environ', {'CUSTOM_API_KEY': 'custom-env-key'})
    def test_get_api_key_from_custom_env(self):
        """Test getting API key from custom environment variable."""
        api_key = get_api_key(None, 'CUSTOM_API_KEY')
        self.assertEqual(api_key, 'custom-env-key')

    @patch.dict('os.environ', clear=True)
    @patch('docgen.find_dotenv')
    def test_get_api_key_from_dotenv(self, mock_find_dotenv):
        """Test getting API key from .env file."""
        mock_find_dotenv.return_value = ".env"
        
        with patch('docgen.load_dotenv') as mock_load_dotenv:
            mock_load_dotenv.side_effect = lambda _: os.environ.update({'ANTHROPIC_API_KEY': 'dotenv-key'})
            api_key = get_api_key(None, None)
            self.assertEqual(api_key, 'dotenv-key')

    @patch.dict('os.environ', clear=True)
    @patch('docgen.find_dotenv', return_value=None)
    @patch('docgen.logger')
    def test_get_api_key_from_param(self, mock_logger, mock_find_dotenv):
        """Test getting API key from direct parameter."""
        api_key = get_api_key(self.test_api_key, None)
        self.assertEqual(api_key, self.test_api_key)
        mock_logger.debug.assert_called_once_with("Using API key from command line parameter")

    @patch.dict('os.environ', clear=True)
    @patch('docgen.find_dotenv')
    def test_get_api_key_missing(self, mock_find_dotenv):
        """Test error when API key is missing."""
        mock_find_dotenv.return_value = None
        
        with self.assertRaises(ValueError):
            get_api_key(None, None)

    def test_setup_logging_default(self):
        """Test setting up logging with default settings."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging()
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            self.assertEqual(kwargs['level'], 20)  # INFO level

    def test_setup_logging_verbose(self):
        """Test setting up logging with verbose flag."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging(verbose=True)
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            self.assertEqual(kwargs['level'], 10)  # DEBUG level

    @patch('docgen.parse_args')
    @patch('docgen.setup_logging')
    @patch('docgen.get_api_key')
    @patch('docgen.CodeDocumentationGenerator')
    def test_main_success(self, mock_generator_class, mock_get_key, mock_setup_logging, mock_parse_args):
        """Test successful execution of main function."""
        # Setup mocks
        mock_args = MagicMock(
            source=self.test_source,
            output=self.test_output,
            api_key=self.test_api_key,
            api_key_env=None,
            temperature=0.1,
            verbose=False
        )
        mock_parse_args.return_value = mock_args
        mock_get_key.return_value = self.test_api_key
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator

        # Run main
        main()

        # Verify calls
        mock_setup_logging.assert_called_once_with(False)
        mock_get_key.assert_called_once_with(self.test_api_key, None)
        mock_generator_class.assert_called_once_with(
            api_key=self.test_api_key,
            temperature=0.1
        )
        mock_generator.generate_documentation.assert_called_once_with(
            directory_path=self.test_source,
            output_dir=self.test_output
        )

    @patch('docgen.parse_args')
    @patch('docgen.setup_logging')
    @patch('docgen.logger')
    def test_main_error(self, mock_logger, mock_setup_logging, mock_parse_args):
        """Test main function with error."""
        test_error = Exception("Test error")
        mock_parse_args.side_effect = test_error

        with patch('sys.exit') as mock_exit:
            main()
            mock_logger.error.assert_called_once_with(f"Documentation generation failed: {str(test_error)}")
            mock_exit.assert_called_once_with(1)

if __name__ == '__main__':
    unittest.main()
