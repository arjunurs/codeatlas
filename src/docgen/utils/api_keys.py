"""API key management utilities.

This module provides functions for managing API keys used by the documentation
generator, including loading from environment variables and .env files.
"""

import os
from typing import Optional, Tuple
import logging
from dotenv import load_dotenv, find_dotenv

from ..exceptions.errors import ApiKeyError

logger = logging.getLogger(__name__)

def get_api_keys(
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    api_key_env: Optional[str] = None
) -> Tuple[str, str]:
    """Get Anthropic and OpenAI API keys with fallback priority:
    1. Environment variables (ANTHROPIC_API_KEY/OPENAI_API_KEY or custom)
    2. .env file
    3. Command line parameter

    Args:
        anthropic_api_key: Direct Anthropic API key from command line
        openai_api_key: Direct OpenAI API key from command line
        api_key_env: Environment variable name containing the API key

    Returns:
        Tuple of (Anthropic API key string, OpenAI API key string)

    Raises:
        ApiKeyError: If API keys cannot be found in any location

    Example:
        >>> anthropic_key, openai_key = get_api_keys()
        >>> anthropic_key, openai_key = get_api_keys(api_key_env='CUSTOM_API_KEY')
    """
    # Try environment variables first
    if api_key_env:
        env_key = os.getenv(api_key_env)
        if env_key:
            logger.debug(f"Using API key from environment variable {api_key_env}")
            return env_key, env_key

    # Try default environment variables
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Try loading from .env file
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
        # Check environment variables again after loading .env
        if not anthropic_key:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not openai_key:
            openai_key = os.getenv("OPENAI_API_KEY")

    # Finally, try command line parameters
    if anthropic_api_key:
        anthropic_key = anthropic_api_key
    if openai_api_key:
        openai_key = openai_api_key

    if not anthropic_key:
        raise ApiKeyError(
            "Anthropic API key not found. Please provide it through one of:\n"
            "1. ANTHROPIC_API_KEY environment variable\n"
            "2. .env file with ANTHROPIC_API_KEY=your-key\n"
            "3. --anthropic-api-key command line parameter"
        )

    if not openai_key:
        raise ApiKeyError(
            "OpenAI API key not found. Please provide it through one of:\n"
            "1. OPENAI_API_KEY environment variable\n"
            "2. .env file with OPENAI_API_KEY=your-key\n"
            "3. --openai-api-key command line parameter"
        )

    return anthropic_key, openai_key 