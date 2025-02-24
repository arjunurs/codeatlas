"""Logging configuration module.

This module provides functions for setting up logging with consistent formatting
and output handling.
"""

import logging
from typing import Optional

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Set up logging configuration.

    Args:
        verbose: Whether to enable debug logging
        log_file: Optional path to log file
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Set up docgen logger
    docgen_logger = logging.getLogger('docgen')
    docgen_logger.setLevel(level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    for handler in docgen_logger.handlers[:]:
        docgen_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    docgen_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        docgen_logger.addHandler(file_handler) 