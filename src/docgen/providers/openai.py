"""OpenAI provider implementations.

This module provides OpenAI implementations of the LLMProvider and
EmbeddingProvider interfaces.
"""

import logging
from typing import List, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .base import BaseLLMProvider, BaseEmbeddingProvider, LLMResponse
from ..exceptions.errors import LLMError, EmbeddingError, ApiKeyError

logger = logging.getLogger(__name__)


def _classify_openai_error(e: Exception, operation: str) -> Exception:
    """Classify an OpenAI error into the appropriate exception type.

    Args:
        e: The original exception
        operation: Description of the operation that failed

    Returns:
        Appropriately typed exception
    """
    error_str = str(e).lower()

    if "rate" in error_str and "limit" in error_str:
        return LLMError(f"OpenAI rate limit exceeded during {operation}. Please wait and retry: {str(e)}")
    if "api_key" in error_str or "authentication" in error_str or "401" in error_str or "invalid" in error_str and "key" in error_str:
        return ApiKeyError(f"Invalid or expired OpenAI API key: {str(e)}")
    if "timeout" in error_str or "timed out" in error_str:
        return LLMError(f"OpenAI request timed out during {operation}. Please retry: {str(e)}")
    if "connection" in error_str:
        return LLMError(f"Connection error to OpenAI API during {operation}: {str(e)}")
    if "quota" in error_str or "billing" in error_str:
        return ApiKeyError(f"OpenAI quota exceeded or billing issue: {str(e)}")
    if "context" in error_str and "length" in error_str:
        return LLMError(f"Input too long for OpenAI model during {operation}: {str(e)}")

    return None  # No specific classification


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT LLM provider.

    This provider wraps the OpenAI API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
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
            raise LLMError(f"Invalid OpenAI configuration: {str(e)}") from e
        except TypeError as e:
            raise LLMError(f"OpenAI API incompatibility: {str(e)}") from e
        except Exception as e:
            classified = _classify_openai_error(e, "LLM creation")
            if classified:
                raise classified from e
            raise LLMError(f"Failed to create OpenAI LLM: {str(e)}") from e

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
            classified = _classify_openai_error(e, "LLM invocation")
            if classified:
                raise classified from e
            raise LLMError(f"Failed to invoke OpenAI LLM: {str(e)}") from e


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider.

    This provider wraps the OpenAI Embeddings API through LangChain,
    providing a consistent interface for the documentation generator.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
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
            raise EmbeddingError(f"Invalid OpenAI embeddings configuration: {str(e)}") from e
        except TypeError as e:
            raise EmbeddingError(f"OpenAI embeddings API incompatibility: {str(e)}") from e
        except Exception as e:
            classified = _classify_openai_error(e, "embeddings creation")
            if classified:
                raise classified from e
            raise EmbeddingError(f"Failed to create OpenAI embeddings: {str(e)}") from e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
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
            classified = _classify_openai_error(e, "document embedding")
            if classified:
                raise classified from e
            raise EmbeddingError(f"Failed to embed documents: {str(e)}") from e

    def embed_query(self, text: str) -> List[float]:
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
            classified = _classify_openai_error(e, "query embedding")
            if classified:
                raise classified from e
            raise EmbeddingError(f"Failed to embed query: {str(e)}") from e
