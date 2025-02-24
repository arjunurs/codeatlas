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

def test_get_api_keys_from_params():
    """Test getting API keys from parameters."""
    keys = get_api_keys(anthropic_api_key="test-anthropic", openai_api_key="test-openai")
    assert keys == ("test-anthropic", "test-openai")

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

def test_get_api_keys_priority(clean_env):
    """Test API key priority (parameters over environment)."""
    os.environ['ANTHROPIC_API_KEY'] = "env-anthropic"
    os.environ['OPENAI_API_KEY'] = "env-openai"
    keys = get_api_keys(anthropic_api_key="param-anthropic", openai_api_key="param-openai")
    assert keys == ("param-anthropic", "param-openai")

def test_get_api_keys_direct_params():
    """Test getting API keys from direct parameters."""
    keys = get_api_keys("direct-anthropic", "direct-openai")
    assert keys == ("direct-anthropic", "direct-openai") 