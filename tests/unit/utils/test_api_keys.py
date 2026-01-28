"""Unit tests for API key management utilities."""

import os
import pytest
from docgen.exceptions.errors import ApiKeyError
from docgen.utils.api_keys import get_api_keys
from unittest.mock import patch, mock_open


@pytest.fixture
def clean_env():
    """Remove API key environment variables before each test."""
    old_env = dict(os.environ)
    os.environ.pop('ANTHROPIC_API_KEY', None)
    os.environ.pop('OPENAI_API_KEY', None)
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_get_api_keys_from_env(clean_env):
    """Test getting API keys from environment variables."""
    os.environ['ANTHROPIC_API_KEY'] = "test-anthropic"
    os.environ['OPENAI_API_KEY'] = "test-openai"
    keys = get_api_keys()
    assert keys == ("test-anthropic", "test-openai")


def test_get_api_keys_from_custom_env(clean_env):
    """Test getting API keys from custom environment file."""
    env_content = """
    ANTHROPIC_API_KEY=custom-anthropic-key
    OPENAI_API_KEY=custom-openai-key
    """
    with patch('builtins.open', mock_open(read_data=env_content)):
        keys = get_api_keys(custom_env_file=".env.custom")
        assert keys == ("custom-anthropic-key", "custom-openai-key")


def test_get_api_keys_missing_anthropic(clean_env):
    """Test error when Anthropic API key is missing."""
    os.environ['OPENAI_API_KEY'] = "test-openai"
    with pytest.raises(ApiKeyError) as exc_info:
        get_api_keys()
    assert "Anthropic API key not found" in str(exc_info.value)


def test_get_api_keys_missing_openai(clean_env):
    """Test error when OpenAI API key is missing."""
    os.environ['ANTHROPIC_API_KEY'] = "test-anthropic"
    with pytest.raises(ApiKeyError) as exc_info:
        get_api_keys()
    assert "OpenAI API key not found" in str(exc_info.value)


def test_get_api_keys_env_over_file(clean_env):
    """Test that environment variables take priority over .env file."""
    os.environ['ANTHROPIC_API_KEY'] = "env-anthropic"
    os.environ['OPENAI_API_KEY'] = "env-openai"
    env_content = """
    ANTHROPIC_API_KEY=file-anthropic
    OPENAI_API_KEY=file-openai
    """
    with patch('builtins.open', mock_open(read_data=env_content)):
        keys = get_api_keys(custom_env_file=".env.custom")
        # Environment variables should take precedence
        assert keys == ("env-anthropic", "env-openai")


def test_get_api_keys_partial_from_env(clean_env):
    """Test getting one key from env, one from file."""
    os.environ['ANTHROPIC_API_KEY'] = "env-anthropic"
    env_content = """
    OPENAI_API_KEY=file-openai
    """
    with patch('builtins.open', mock_open(read_data=env_content)):
        keys = get_api_keys(custom_env_file=".env.custom")
        assert keys == ("env-anthropic", "file-openai")


def test_get_api_keys_missing_both(clean_env):
    """Test error when both API keys are missing."""
    with pytest.raises(ApiKeyError) as exc_info:
        get_api_keys()
    # Should raise error for missing Anthropic key first
    assert "Anthropic API key not found" in str(exc_info.value)


def test_get_api_keys_custom_env_file_not_found(clean_env):
    """Test error when custom env file does not exist."""
    with pytest.raises(ApiKeyError) as exc_info:
        get_api_keys(custom_env_file="/nonexistent/.env")
    assert "not found" in str(exc_info.value).lower() or "Invalid env file path" in str(exc_info.value)
