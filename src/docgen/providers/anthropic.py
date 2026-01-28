"""Anthropic LLM provider implementation.

This module provides the Anthropic/Claude implementation of the LLMProvider
interface.
"""

import logging
from typing import Optional

from langchain_anthropic import ChatAnthropic

from .base import BaseLLMProvider, LLMResponse
from ..exceptions.errors import LLMError, ApiKeyError

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider.

    This provider wraps the Anthropic Claude API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name to use (defaults to claude-sonnet-4-20250514)
            temperature: Temperature for generation (0.0 to 1.0)
        """
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            temperature=temperature,
        )

    def _create_llm(self) -> ChatAnthropic:
        """Create the Anthropic LLM instance.

        Returns:
            ChatAnthropic instance

        Raises:
            LLMError: If creation fails
            ApiKeyError: If API key is invalid
        """
        try:
            return ChatAnthropic(
                api_key=self._api_key,
                model=self._model,
                temperature=self._temperature,
            )
        except ValueError as e:
            # Configuration errors (invalid parameters)
            raise LLMError(f"Invalid Anthropic configuration: {str(e)}") from e
        except TypeError as e:
            # API changes or incorrect argument types
            raise LLMError(f"Anthropic API incompatibility: {str(e)}") from e
        except Exception as e:
            error_str = str(e).lower()
            if "api_key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
                raise ApiKeyError(f"Invalid Anthropic API key: {str(e)}") from e
            raise LLMError(f"Failed to create Anthropic LLM: {str(e)}") from e

    def invoke(self, prompt: str) -> LLMResponse:
        """Invoke Claude with a prompt.

        Args:
            prompt: The prompt to send to Claude

        Returns:
            The Claude response (BaseMessage)

        Raises:
            LLMError: If invocation fails
            ApiKeyError: If API key is invalid or expired
        """
        try:
            llm = self.get_langchain_llm()
            return llm.invoke(prompt)
        except LLMError:
            # Re-raise our own errors
            raise
        except Exception as e:
            error_str = str(e).lower()
            # Check for specific error types
            if "rate" in error_str and "limit" in error_str:
                raise LLMError(f"Anthropic rate limit exceeded. Please wait and retry: {str(e)}") from e
            if "api_key" in error_str or "authentication" in error_str or "401" in error_str:
                raise ApiKeyError(f"Invalid or expired Anthropic API key: {str(e)}") from e
            if "timeout" in error_str or "timed out" in error_str:
                raise LLMError(f"Anthropic request timed out. Please retry: {str(e)}") from e
            if "connection" in error_str:
                raise LLMError(f"Connection error to Anthropic API: {str(e)}") from e
            raise LLMError(f"Failed to invoke Anthropic LLM: {str(e)}") from e
