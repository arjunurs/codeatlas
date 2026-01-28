"""Abstract base classes for LLM and embedding providers.

This module defines the interfaces that all providers must implement,
enabling provider-agnostic code in the documentation generator.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol, Union, runtime_checkable

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


# Type alias for LLM responses - can be a message or string
LLMResponse = Union[BaseMessage, str]


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.

    Any class implementing this protocol can be used as an LLM provider
    in the documentation generator.
    """

    @property
    def model_name(self) -> str:
        """Get the name of the model being used."""
        ...

    def invoke(self, prompt: str) -> LLMResponse:
        """Invoke the LLM with a prompt.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM response (BaseMessage or string)
        """
        ...

    def get_langchain_llm(self) -> BaseChatModel:
        """Get the underlying LangChain LLM instance.

        Returns:
            A LangChain BaseChatModel instance
        """
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.

    Any class implementing this protocol can be used as an embedding provider
    in the documentation generator.
    """

    @property
    def model_name(self) -> str:
        """Get the name of the embedding model being used."""
        ...

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors
        """
        ...

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query.

        Args:
            text: The query text to embed

        Returns:
            Embedding vector for the query
        """
        ...

    def get_langchain_embeddings(self) -> Embeddings:
        """Get the underlying LangChain embeddings instance.

        Returns:
            A LangChain Embeddings instance
        """
        ...


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    This provides a common implementation structure for LLM providers
    while enforcing the LLMProvider protocol.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.2,
    ) -> None:
        """Initialize the LLM provider.

        Args:
            api_key: API key for the provider
            model: Model name/identifier to use
            temperature: Temperature for generation (0.0 to 1.0)
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        if not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._llm: Optional[BaseChatModel] = None

    @property
    def model_name(self) -> str:
        """Get the name of the model being used."""
        return self._model

    @property
    def temperature(self) -> float:
        """Get the temperature setting."""
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

    @abstractmethod
    def invoke(self, prompt: str) -> LLMResponse:
        """Invoke the LLM with a prompt.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM response (BaseMessage or string)
        """
        pass


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    This provides a common implementation structure for embedding providers
    while enforcing the EmbeddingProvider protocol.
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
        self._embeddings: Optional[Embeddings] = None

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

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query.

        Args:
            text: The query text to embed

        Returns:
            Embedding vector for the query
        """
        pass
