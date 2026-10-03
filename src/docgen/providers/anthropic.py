"""Anthropic LLM provider implementation.

This module provides the Anthropic/Claude implementation of the LLMProvider
interface.
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic

from ..exceptions.errors import LLMError
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider.

    This provider wraps the Anthropic Claude API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "claude-sonnet-5"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name to use (defaults to claude-sonnet-5)
            temperature: Temperature for generation (0.0 to 1.0), or None to
                use the model's default. Claude Sonnet 5 and newer reject
                non-default temperature values.
            max_tokens: Maximum output tokens per call, or None for the
                langchain-anthropic default (4096)
        """
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _create_llm(self) -> ChatAnthropic:
        """Create the Anthropic LLM instance.

        Returns:
            ChatAnthropic instance

        Raises:
            LLMError: If the settings are invalid
        """
        try:
            kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "model": self._model,
            }
            if self._temperature is not None:
                kwargs["temperature"] = self._temperature
            if self._max_tokens is not None:
                kwargs["max_tokens"] = self._max_tokens
            return ChatAnthropic(**kwargs)
        except ValueError as e:
            # Configuration errors (invalid parameters)
            raise LLMError(f"Invalid Anthropic configuration: {e}") from e
        except TypeError as e:
            # API changes or incorrect argument types
            raise LLMError(f"Anthropic API incompatibility: {e}") from e
