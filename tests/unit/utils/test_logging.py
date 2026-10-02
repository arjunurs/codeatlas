"""Unit tests for logging utilities."""

import logging

import pytest

from docgen.utils.logging import setup_logging


@pytest.fixture
def clean_logging():
    """Reset logging configuration before each test."""
    # Store original logging configuration
    docgen_logger = logging.getLogger("docgen")
    original_handlers = logging.root.handlers.copy()
    original_level = logging.root.level
    original_docgen_handlers = docgen_logger.handlers.copy()
    original_docgen_level = docgen_logger.level

    yield

    # Restore original logging configuration
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)
    docgen_logger.handlers = original_docgen_handlers
    docgen_logger.setLevel(original_docgen_level)


def test_setup_logging_default(clean_logging):
    """Test default logging setup."""
    setup_logging()

    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger("docgen")

    assert root_logger.level == logging.INFO
    assert docgen_logger.level == logging.INFO
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


def test_setup_logging_verbose(clean_logging):
    """Test verbose logging setup."""
    setup_logging(verbose=True)

    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger("docgen")

    assert root_logger.level == logging.DEBUG
    assert docgen_logger.level == logging.DEBUG


def test_setup_logging_quiet(clean_logging):
    """Test quiet logging setup (errors only)."""
    setup_logging(quiet=True)

    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger("docgen")

    assert root_logger.level == logging.ERROR
    assert docgen_logger.level == logging.ERROR


def test_setup_logging_quiet_overrides_verbose(clean_logging):
    """Test that quiet mode takes precedence over verbose."""
    setup_logging(verbose=True, quiet=True)

    root_logger = logging.getLogger()

    # Quiet should take precedence
    assert root_logger.level == logging.ERROR


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

    with open(log_file) as f:
        log_content = f.read()
        assert test_message in log_content


def test_setup_logging_formatter(clean_logging):
    """Test logging formatter configuration."""
    setup_logging()

    root_logger = logging.getLogger()
    handler = root_logger.handlers[0]
    formatter = handler.formatter

    # Test formatter format string
    expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    assert formatter._fmt == expected_format


def test_docgen_message_printed_once(clean_logging, capsys):
    """A message from a docgen module logger reaches the console exactly once."""
    setup_logging()

    logging.getLogger("docgen.core.generator").info("analyzing files")

    assert capsys.readouterr().err.count("analyzing files") == 1


def test_docgen_message_written_to_file_once(clean_logging, tmp_path):
    """A message from a docgen module logger reaches the log file exactly once."""
    log_file = tmp_path / "test.log"
    setup_logging(log_file=str(log_file))

    logging.getLogger("docgen.core.generator").info("analyzing files")

    assert log_file.read_text().count("analyzing files") == 1


def test_setup_logging_twice_does_not_duplicate_output(clean_logging, capsys):
    """Calling setup_logging again does not add another console handler."""
    setup_logging()
    setup_logging()

    logging.getLogger("docgen.cli").info("starting run")

    assert capsys.readouterr().err.count("starting run") == 1
