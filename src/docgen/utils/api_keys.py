"""API key management module.

This module provides functionality for retrieving API keys from various sources:
1. Direct parameters
2. Custom environment variables
3. Default environment variables
4. .env file
"""

import logging
import os
from typing import Optional, Tuple


from ..exceptions.errors import ApiKeyError
from .path_validation import validate_env_file_path, PathValidationError

logger = logging.getLogger(__name__)

def get_api_keys(
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    custom_env_file: Optional[str] = None
) -> Tuple[str, str]:
    """Get API keys from parameters, environment variables, or .env file.

    Args:
        anthropic_api_key: Optional Anthropic API key
        openai_api_key: Optional OpenAI API key
        custom_env_file: Optional path to custom .env file

    Returns:
        Tuple of (Anthropic API key, OpenAI API key)

    Raises:
        ApiKeyError: If either API key is missing
    """
    # Try to get keys from parameters first
    final_anthropic_key = anthropic_api_key
    final_openai_key = openai_api_key

    # If not provided, try environment variables
    if not final_anthropic_key:
        final_anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        if final_anthropic_key:
            logger.debug("Using Anthropic API key from environment")

    if not final_openai_key:
        final_openai_key = os.environ.get('OPENAI_API_KEY')
        if final_openai_key:
            logger.debug("Using OpenAI API key from environment")

    # If custom env file provided, read it (failure is an error, not a warning)
    if custom_env_file:
        try:
            # Validate the path before reading to prevent path traversal
            validated_path = validate_env_file_path(custom_env_file)

            with open(validated_path) as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        if key == 'ANTHROPIC_API_KEY' and not final_anthropic_key:
                            final_anthropic_key = value
                            logger.debug("Using Anthropic API key from custom env file")
                        elif key == 'OPENAI_API_KEY' and not final_openai_key:
                            final_openai_key = value
                            logger.debug("Using OpenAI API key from custom env file")
        except PathValidationError as e:
            raise ApiKeyError(f"Invalid env file path '{custom_env_file}': {e}") from e
        except FileNotFoundError:
            raise ApiKeyError(f"Custom env file not found: {custom_env_file}")
        except PermissionError:
            raise ApiKeyError(f"Permission denied reading custom env file: {custom_env_file}")
        except UnicodeDecodeError as e:
            raise ApiKeyError(f"Encoding error reading custom env file '{custom_env_file}': {e}") from e
        except (IOError, OSError) as e:
            raise ApiKeyError(f"Failed to read custom env file '{custom_env_file}': {e}") from e

    # Validate we have both keys
    if not final_anthropic_key:
        raise ApiKeyError("Anthropic API key not found")
    if not final_openai_key:
        raise ApiKeyError("OpenAI API key not found")

    return final_anthropic_key, final_openai_key 