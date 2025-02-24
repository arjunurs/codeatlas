"""Logging configuration utilities.

This module provides functions for configuring logging settings used throughout
the documentation generator.
"""

import logging
from typing import Optional

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Configure logging settings.

    Args:
        verbose: If True, set logging level to DEBUG
        log_file: Optional path to a log file. If provided, logs will be written
            to this file in addition to console output.

    Example:
        >>> setup_logging(verbose=True, log_file='docgen.log')
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format
    )

    # Add file handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)

    # Create logger for this package
    logger = logging.getLogger('docgen')
    logger.setLevel(log_level) 