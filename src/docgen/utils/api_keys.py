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

from dotenv import find_dotenv, load_dotenv

from ..exceptions.errors import ApiKeyError

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

    # If still not found and custom env file provided, try that
    if custom_env_file and (not final_anthropic_key or not final_openai_key):
        try:
            with open(custom_env_file) as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        if key == 'ANTHROPIC_API_KEY' and not final_anthropic_key:
                            final_anthropic_key = value
                            logger.debug("Using Anthropic API key from custom env file")
                        elif key == 'OPENAI_API_KEY' and not final_openai_key:
                            final_openai_key = value
                            logger.debug("Using OpenAI API key from custom env file")
        except Exception as e:
            logger.warning(f"Error reading custom env file: {str(e)}")

    # Validate we have both keys
    if not final_anthropic_key:
        raise ApiKeyError("Anthropic API key not found")
    if not final_openai_key:
        raise ApiKeyError("OpenAI API key not found")

    return final_anthropic_key, final_openai_key 