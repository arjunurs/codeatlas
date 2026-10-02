"""API key management module.

This module provides functionality for retrieving API keys from various sources:
1. Environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY)
2. Custom .env file

Note: Direct CLI parameters for API keys have been removed for security reasons.
Passing secrets on command line exposes them in shell history, `ps` output, and logs.
"""

import logging
import os

from dotenv import dotenv_values

from ..exceptions.errors import ApiKeyError
from .path_validation import PathValidationError, validate_env_file_path

logger = logging.getLogger(__name__)


def get_api_keys(custom_env_file: str | None = None) -> tuple[str, str]:
    """Get API keys from environment variables or .env file.

    API keys are retrieved in the following priority order:
    1. Environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY)
    2. Custom .env file (if provided)

    Args:
        custom_env_file: Optional path to custom .env file

    Returns:
        Tuple of (Anthropic API key, OpenAI API key)

    Raises:
        ApiKeyError: If either API key is missing
    """
    # Try environment variables first
    final_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if final_anthropic_key:
        logger.debug("Using Anthropic API key from environment")

    final_openai_key = os.environ.get("OPENAI_API_KEY")
    if final_openai_key:
        logger.debug("Using OpenAI API key from environment")

    # If custom env file provided, read it (failure is an error, not a warning)
    if custom_env_file:
        try:
            # Validate the path before reading to prevent path traversal
            validated_path = validate_env_file_path(custom_env_file)

            # Open the file ourselves: given a path, dotenv_values returns an
            # empty dict for a missing file instead of raising
            with open(validated_path, encoding="utf-8") as f:
                file_values = dotenv_values(stream=f, interpolate=False)

            if not final_anthropic_key and file_values.get("ANTHROPIC_API_KEY"):
                final_anthropic_key = file_values["ANTHROPIC_API_KEY"]
                logger.debug("Using Anthropic API key from custom env file")
            if not final_openai_key and file_values.get("OPENAI_API_KEY"):
                final_openai_key = file_values["OPENAI_API_KEY"]
                logger.debug("Using OpenAI API key from custom env file")
        except PathValidationError as e:
            raise ApiKeyError(f"Invalid env file path '{custom_env_file}': {e}") from e
        except FileNotFoundError:
            raise ApiKeyError(f"Custom env file not found: {custom_env_file}")
        except PermissionError:
            raise ApiKeyError(
                f"Permission denied reading custom env file: {custom_env_file}"
            )
        except UnicodeDecodeError as e:
            raise ApiKeyError(
                f"Encoding error reading custom env file '{custom_env_file}': {e}"
            ) from e
        except OSError as e:
            raise ApiKeyError(
                f"Failed to read custom env file '{custom_env_file}': {e}"
            ) from e

    # Validate we have both keys
    if not final_anthropic_key:
        raise ApiKeyError("Anthropic API key not found")
    if not final_openai_key:
        raise ApiKeyError("OpenAI API key not found")

    return final_anthropic_key, final_openai_key
