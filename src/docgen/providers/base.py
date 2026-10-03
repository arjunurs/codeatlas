"""Provider interfaces for the chat and embedding models.

The documentation pipeline is built on LangChain: the RAG chain, the Chroma
vector store, and usage tracking all take LangChain models. A provider's job
is to configure and create those models, so the protocols ask for exactly
that.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel


@runtime_checkable
class LLMProvider(Protocol):
    """Supplies the LangChain chat model the RAG chain runs on."""

    @property
    def model_name(self) -> str:
        """Get the name of the model, used for pricing and cache keys."""
        ...

    def get_langchain_llm(self) -> BaseChatModel:
        """Get the LangChain chat model."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Supplies the LangChain embeddings model the vector store uses."""

    @property
    def model_name(self) -> str:
        """Get the name of the embedding model, used for pricing."""
        ...

    def get_langchain_embeddings(self) -> Embeddings:
        """Get the LangChain embeddings model."""
        ...


class BaseLLMProvider(ABC):
    """Base class for LLM providers: validates settings, creates the model once.

    Subclasses implement ``_create_llm``; the result satisfies LLMProvider.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Initialize the LLM provider.

        Args:
            api_key: API key for the provider
            model: Model name/identifier to use
            temperature: Temperature for generation (0.0 to 1.0), or None to
                use the model's default sampling
            max_tokens: Maximum output tokens per call, or None for the
                library default
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        if temperature is not None and not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._llm: BaseChatModel | None = None

    @property
    def model_name(self) -> str:
        """Get the name of the model being used."""
        return self._model

    @property
    def temperature(self) -> float | None:
        """Get the temperature setting (None = model default)."""
        return self._temperature

    @abstractmethod
    def _create_llm(self) -> BaseChatModel:
        """Create the underlying LLM instance.

        Returns:
            The LangChain BaseChatModel instance
        """
        pass

    def get_langchain_llm(self) -> BaseChatModel:
        """Get the underlying LangChain LLM instance.

        Returns:
            A LangChain BaseChatModel instance
        """
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers: validates settings, creates the model once.

    Subclasses implement ``_create_embeddings``; the result satisfies
    EmbeddingProvider.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
    ) -> None:
        """Initialize the embedding provider.

        Args:
            api_key: API key for the provider
            model: Model name/identifier to use
        """
        if not api_key:
            raise ValueError("API key cannot be empty")

        self._api_key = api_key
        self._model = model
        self._embeddings: Embeddings | None = None

    @property
    def model_name(self) -> str:
        """Get the name of the embedding model being used."""
        return self._model

    @abstractmethod
    def _create_embeddings(self) -> Embeddings:
        """Create the underlying embeddings instance.

        Returns:
            The LangChain Embeddings instance
        """
        pass

    def get_langchain_embeddings(self) -> Embeddings:
        """Get the underlying LangChain embeddings instance.

        Returns:
            A LangChain Embeddings instance
        """
        if self._embeddings is None:
            self._embeddings = self._create_embeddings()
        return self._embeddings
