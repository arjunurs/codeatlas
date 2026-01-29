"""OpenAI provider implementations.

This module provides OpenAI implementations of the LLMProvider and
EmbeddingProvider interfaces.
"""

import logging

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..exceptions.errors import ApiKeyError, EmbeddingError, LLMError
from .base import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    LLMResponse,
    classify_api_error,
)

logger = logging.getLogger(__name__)


def _raise_openai_error(
    e: Exception, operation: str, error_class: type = LLMError
) -> None:
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
        temperature: float = 0.2,
    ) -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name to use (defaults to gpt-4o)
            temperature: Temperature for generation (0.0 to 1.0)
        """
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            temperature=temperature,
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
            return ChatOpenAI(
                api_key=self._api_key,
                model=self._model,
                temperature=self._temperature,
            )
        except ValueError as e:
            raise LLMError(f"Invalid OpenAI configuration: {e}") from e
        except TypeError as e:
            raise LLMError(f"OpenAI API incompatibility: {e}") from e
        except Exception as e:
            _raise_openai_error(e, "create OpenAI LLM")

    def invoke(self, prompt: str) -> LLMResponse:
        """Invoke GPT with a prompt.

        Args:
            prompt: The prompt to send to GPT

        Returns:
            The GPT response (BaseMessage)

        Raises:
            LLMError: If invocation fails
            ApiKeyError: If API key is invalid or expired
        """
        try:
            llm = self.get_langchain_llm()
            return llm.invoke(prompt)
        except (LLMError, ApiKeyError):
            raise
        except Exception as e:
            _raise_openai_error(e, "invoke OpenAI LLM")


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

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents using OpenAI.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If embedding fails
            ApiKeyError: If API key is invalid
        """
        if not texts:
            return []

        try:
            embeddings = self.get_langchain_embeddings()
            return embeddings.embed_documents(texts)
        except (EmbeddingError, ApiKeyError):
            raise
        except Exception as e:
            _raise_openai_error(e, "embed documents", EmbeddingError)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query using OpenAI.

        Args:
            text: The query text to embed

        Returns:
            Embedding vector for the query

        Raises:
            EmbeddingError: If embedding fails
            ApiKeyError: If API key is invalid
        """
        if not text:
            raise EmbeddingError("Cannot embed empty query text")

        try:
            embeddings = self.get_langchain_embeddings()
            return embeddings.embed_query(text)
        except (EmbeddingError, ApiKeyError):
            raise
        except Exception as e:
            _raise_openai_error(e, "embed query", EmbeddingError)
