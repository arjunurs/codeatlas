"""Logging configuration module.

This module provides functions for setting up logging with consistent formatting
and output handling.
"""

import logging

DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ConsoleFormatter(logging.Formatter):
    """Short console format: bare INFO messages, level prefix for the rest."""

    def __init__(self) -> None:
        """Initialize with a message-only format."""
        super().__init__("%(message)s")

    def format(self, record: logging.LogRecord) -> str:
        """Format a record, prefixing warnings and errors with their level."""
        message = super().format(record)
        if record.levelno >= logging.WARNING:
            return f"{record.levelname}: {message}"
        return message


def setup_logging(
    verbose: bool = False, quiet: bool = False, log_file: str | None = None
) -> None:
    """Set up logging configuration.

    By default the console shows short progress messages from docgen and only
    warnings and errors from third-party libraries. Verbose mode shows debug
    output from everything, with timestamps and module names.

    Args:
        verbose: Whether to enable debug logging (ignored if quiet=True)
        quiet: Whether to enable quiet mode (errors only)
        log_file: Optional path to log file
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    root_logger = logging.getLogger()
    docgen_logger = logging.getLogger("docgen")

    # Third-party libraries stay at WARNING by default: httpx alone logs a
    # line for every HTTP request at INFO
    root_logger.setLevel(logging.WARNING if level == logging.INFO else level)
    docgen_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates if called multiple times.
    # Handlers live only on the root logger; docgen records propagate to it.
    root_logger.handlers.clear()
    docgen_logger.handlers.clear()

    detailed_formatter = logging.Formatter(DETAILED_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(
        detailed_formatter if verbose and not quiet else ConsoleFormatter()
    )
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
