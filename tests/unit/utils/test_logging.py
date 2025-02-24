"""Unit tests for logging utilities."""

import os
import logging
import pytest
from docgen.utils.logging import setup_logging

@pytest.fixture
def clean_logging():
    """Reset logging configuration before each test."""
    # Store original logging configuration
    original_handlers = logging.root.handlers.copy()
    original_level = logging.root.level
    
    yield
    
    # Restore original logging configuration
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)

def test_setup_logging_default(clean_logging):
    """Test default logging setup."""
    setup_logging()
    
    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger('docgen')
    
    assert root_logger.level == logging.INFO
    assert docgen_logger.level == logging.INFO
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0], logging.StreamHandler)

def test_setup_logging_verbose(clean_logging):
    """Test verbose logging setup."""
    setup_logging(verbose=True)
    
    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger('docgen')
    
    assert root_logger.level == logging.DEBUG
    assert docgen_logger.level == logging.DEBUG

def test_setup_logging_with_file(clean_logging, tmp_path):
    """Test logging setup with file output."""
    log_file = tmp_path / "test.log"
    setup_logging(log_file=str(log_file))
    
    root_logger = logging.getLogger()
    
    # Should have both stream and file handlers
    assert len(root_logger.handlers) == 2
    assert any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    
    # Test logging to file
    test_message = "Test log message"
    logging.info(test_message)
    
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert test_message in log_content

def test_setup_logging_formatter(clean_logging):
    """Test logging formatter configuration."""
    setup_logging()
    
    root_logger = logging.getLogger()
    handler = root_logger.handlers[0]
    formatter = handler.formatter
    
    # Test formatter format string
    expected_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    assert formatter._fmt == expected_format 