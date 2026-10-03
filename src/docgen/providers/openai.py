"""OpenAI provider implementations.

This module provides OpenAI implementations of the LLMProvider and
EmbeddingProvider interfaces.
"""

import logging
from typing import Any, NoReturn

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..exceptions.errors import ApiKeyError, EmbeddingError, LLMError
from ..utils.error_classification import classify_api_error
from .base import BaseEmbeddingProvider, BaseLLMProvider

logger = logging.getLogger(__name__)


def _raise_openai_error(
    e: Exception, operation: str, error_class: type = LLMError
) -> NoReturn:
    """Raise appropriate exception for OpenAI errors.

    Args:
        e: The original exception
        operation: Description of the operation that failed
        error_class: Default error class to use (LLMError or EmbeddingError)

    Raises:
        ApiKeyError: For authentication or quota issues
        LLMError/EmbeddingError: For other errors
    """
    error_type = classify_api_error(e)
    messages = {
        "rate_limit": f"OpenAI rate limit exceeded during {operation}. Please wait and retry",
        "auth": "Invalid or expired OpenAI API key",
        "timeout": f"OpenAI request timed out during {operation}. Please retry",
        "connection": f"Connection error to OpenAI API during {operation}",
        "quota": "OpenAI quota exceeded or billing issue",
        "context_length": f"Input too long for OpenAI model during {operation}",
    }

    if error_type in ("auth", "quota"):
        raise ApiKeyError(f"{messages[error_type]}: {e}") from e
    if error_type in messages:
        raise error_class(f"{messages[error_type]}: {e}") from e
    raise error_class(f"Failed to {operation}: {e}") from e


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT LLM provider.

    This provider wraps the OpenAI API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name to use (defaults to gpt-4o)
            temperature: Temperature for generation (0.0 to 1.0), or None to
                use the model's default
            max_tokens: Maximum output tokens per call, or None for the
                model's default
        """
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _create_llm(self) -> ChatOpenAI:
        """Create the OpenAI LLM instance.

        Returns:
            ChatOpenAI instance

        Raises:
            LLMError: If creation fails
            ApiKeyError: If API key is invalid
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
            return ChatOpenAI(**kwargs)
        except ValueError as e:
            raise LLMError(f"Invalid OpenAI configuration: {e}") from e
        except TypeError as e:
            raise LLMError(f"OpenAI API incompatibility: {e}") from e
        except Exception as e:
            _raise_openai_error(e, "create OpenAI LLM")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider.

    This provider wraps the OpenAI Embeddings API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
    ) -> None:
        """Initialize the OpenAI embedding provider.

        Args:
            api_key: OpenAI API key
            model: Model name to use (defaults to text-embedding-3-small)
        """
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
        )

    def _create_embeddings(self) -> OpenAIEmbeddings:
        """Create the OpenAI embeddings instance.

        Returns:
            OpenAIEmbeddings instance

        Raises:
            EmbeddingError: If creation fails
            ApiKeyError: If API key is invalid
        """
        try:
            return OpenAIEmbeddings(
                api_key=self._api_key,
                model=self._model,
            )
        except ValueError as e:
            raise EmbeddingError(f"Invalid OpenAI embeddings configuration: {e}") from e
        except TypeError as e:
            raise EmbeddingError(f"OpenAI embeddings API incompatibility: {e}") from e
        except Exception as e:
            _raise_openai_error(e, "create OpenAI embeddings", EmbeddingError)
