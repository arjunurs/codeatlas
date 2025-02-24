"""Unit tests for API key management utilities."""

import os
import pytest
from docgen.utils.api_keys import get_api_keys
from docgen.exceptions.errors import ApiKeyError

@pytest.fixture
def clean_env():
    """Remove API key environment variables before each test."""
    # Save existing values
    old_anthropic = os.environ.get('ANTHROPIC_API_KEY')
    old_openai = os.environ.get('OPENAI_API_KEY')
    
    # Remove variables
    if 'ANTHROPIC_API_KEY' in os.environ:
        del os.environ['ANTHROPIC_API_KEY']
    if 'OPENAI_API_KEY' in os.environ:
        del os.environ['OPENAI_API_KEY']
    
    yield
    
    # Restore old values
    if old_anthropic:
        os.environ['ANTHROPIC_API_KEY'] = old_anthropic
    if old_openai:
        os.environ['OPENAI_API_KEY'] = old_openai

def test_get_api_keys_from_params():
    """Test getting API keys from direct parameters."""
    anthropic_key, openai_key = get_api_keys(
        anthropic_api_key="test-anthropic",
        openai_api_key="test-openai"
    )
    
    assert anthropic_key == "test-anthropic"
    assert openai_key == "test-openai"

def test_get_api_keys_from_env(clean_env):
    """Test getting API keys from environment variables."""
    os.environ['ANTHROPIC_API_KEY'] = "env-anthropic"
    os.environ['OPENAI_API_KEY'] = "env-openai"
    
    anthropic_key, openai_key = get_api_keys()
    
    assert anthropic_key == "env-anthropic"
    assert openai_key == "env-openai"

def test_get_api_keys_from_custom_env(clean_env):
    """Test getting API keys from a custom environment variable."""
    os.environ['CUSTOM_API_KEY'] = "custom-key"
    
    anthropic_key, openai_key = get_api_keys(api_key_env='CUSTOM_API_KEY')
    
    assert anthropic_key == "custom-key"
    assert openai_key == "custom-key"

def test_get_api_keys_missing_anthropic(clean_env):
    """Test error when Anthropic API key is missing."""
    os.environ['OPENAI_API_KEY'] = "test-openai"
    
    with pytest.raises(ApiKeyError, match="Anthropic API key not found"):
        get_api_keys()

def test_get_api_keys_missing_openai(clean_env):
    """Test error when OpenAI API key is missing."""
    os.environ['ANTHROPIC_API_KEY'] = "test-anthropic"
    
    with pytest.raises(ApiKeyError, match="OpenAI API key not found"):
        get_api_keys()

def test_get_api_keys_priority(clean_env):
    """Test API key priority (params > env)."""
    os.environ['ANTHROPIC_API_KEY'] = "env-anthropic"
    os.environ['OPENAI_API_KEY'] = "env-openai"
    
    anthropic_key, openai_key = get_api_keys(
        anthropic_api_key="param-anthropic",
        openai_api_key="param-openai"
    )
    
    assert anthropic_key == "param-anthropic"
    assert openai_key == "param-openai" 