"""Anthropic LLM provider implementation.

This module provides the Anthropic/Claude implementation of the LLMProvider
interface.
"""

import logging

from langchain_anthropic import ChatAnthropic

from ..exceptions.errors import ApiKeyError, LLMError
from .base import BaseLLMProvider, LLMResponse, classify_api_error

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
        model: str | None = None,
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
            if (
                "api_key" in error_str
                or "authentication" in error_str
                or "unauthorized" in error_str
            ):
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
            raise
        except Exception as e:
            error_type = classify_api_error(e)
            error_messages = {
                "rate_limit": "Anthropic rate limit exceeded. Please wait and retry",
                "auth": "Invalid or expired Anthropic API key",
                "timeout": "Anthropic request timed out. Please retry",
                "connection": "Connection error to Anthropic API",
            }
            if error_type == "auth":
                raise ApiKeyError(f"{error_messages[error_type]}: {e}") from e
            if error_type in error_messages:
                raise LLMError(f"{error_messages[error_type]}: {e}") from e
            raise LLMError(f"Failed to invoke Anthropic LLM: {e}") from e
