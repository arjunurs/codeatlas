"""Unit tests for logging utilities."""

import logging

import pytest

from docgen.utils.logging import DETAILED_FORMAT, ConsoleFormatter, setup_logging


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
    """Test default logging setup: docgen at INFO, third-party at WARNING."""
    setup_logging()

    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger("docgen")

    assert root_logger.level == logging.WARNING
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
    logging.getLogger("docgen").info(test_message)

    with open(log_file) as f:
        log_content = f.read()
        assert test_message in log_content


def test_setup_logging_formatter(clean_logging):
    """Test logging formatter configuration: short by default, detailed with -v."""
    setup_logging()
    assert isinstance(logging.getLogger().handlers[0].formatter, ConsoleFormatter)

    setup_logging(verbose=True)
    formatter = logging.getLogger().handlers[0].formatter
    assert formatter is not None
    assert formatter._fmt == DETAILED_FORMAT


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


def test_default_console_prints_bare_info_messages(clean_logging, capsys):
    """Default console output is the message alone, without timestamp or module."""
    setup_logging()

    logging.getLogger("docgen.core.generator").info("Analyzed 3 Python files")

    assert capsys.readouterr().err == "Analyzed 3 Python files\n"


def test_default_console_prefixes_warnings_with_level(clean_logging, capsys):
    """Warnings and errors keep a level prefix so they stand out."""
    setup_logging()

    logging.getLogger("docgen.core.generator").warning("1 diagram failed")

    assert capsys.readouterr().err == "WARNING: 1 diagram failed\n"


def test_default_hides_third_party_info(clean_logging, capsys):
    """Third-party INFO logs, such as httpx request lines, are hidden by default."""
    setup_logging()

    logging.getLogger("httpx").info("HTTP Request: POST https://api.example.com")
    logging.getLogger("httpx").warning("retrying request")

    assert capsys.readouterr().err == "WARNING: retrying request\n"


def test_verbose_console_uses_detailed_format(clean_logging, capsys):
    """Verbose output keeps the timestamp, module, and level."""
    setup_logging(verbose=True)

    logging.getLogger("docgen.core.generator").debug("chunk count 12")

    assert (
        " - docgen.core.generator - DEBUG - chunk count 12" in capsys.readouterr().err
    )


def test_log_file_uses_detailed_format(clean_logging, tmp_path):
    """The log file keeps the detailed format even when the console is short."""
    log_file = tmp_path / "test.log"
    setup_logging(log_file=str(log_file))

    logging.getLogger("docgen.cli").info("starting run")

    assert " - docgen.cli - INFO - starting run" in log_file.read_text()
