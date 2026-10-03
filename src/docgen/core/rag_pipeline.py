"""RAG pipeline factory for documentation generation.

This module handles creating vector stores and RAG chains from code analyses,
encapsulating all LangChain/ChromaDB-specific logic.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..cache.vector_cache import VectorStoreCache
from ..config import GeneratorConfig
from ..exceptions.errors import DocumentationError, VectorStoreError
from ..models.code_entity import EntityType
from ..models.file_analysis import FileAnalysis
from ..prompts.rag_prompt import RAG_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


def _format_docs(docs: list[Document]) -> str:
    """Format retrieved documents into a single string."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def format_entity_document(entity) -> str:
    """Format a code entity as a document string.

    Args:
        entity: CodeEntity to format

    Returns:
        Formatted document string
    """
    lines = [f"Type: {entity.type.value}", f"Name: {entity.name}"]

    if entity.docstring:
        lines.append(f"Description: {entity.docstring}")

    if entity.type == EntityType.CLASS:
        methods = ", ".join(entity.methods) if entity.methods else "None"
        lines.append(f"Methods: {methods}")
        if entity.parent_class:
            lines.append(f"Inherits from: {entity.parent_class}")

    return "\n".join(lines) + "\n"


def create_documents(analyses: Sequence[FileAnalysis]) -> list[Document]:
    """Create LangChain documents from file analyses.

    Args:
        analyses: List of file analysis results

    Returns:
        List of LangChain documents for vector store
    """
    documents: list[Document] = []

    for analysis in analyses:
        documents.append(
            Document(
                page_content=analysis.content,
                metadata={"source": analysis.file_path},
            )
        )

        for entity in analysis.entities:
            doc = format_entity_document(entity)
            documents.append(
                Document(page_content=doc, metadata={"source": analysis.file_path})
            )

    return documents


class RAGPipelineFactory:
    """Creates vector stores and RAG chains from code analyses.

    Encapsulates all LangChain/ChromaDB-specific logic for building
    the retrieval-augmented generation pipeline.
    """

    def __init__(
        self,
        llm,
        embeddings,
        config: GeneratorConfig,
        text_splitter: RecursiveCharacterTextSplitter,
        *,
        cache_enabled: bool = False,
        cache_dir: Path | None = None,
        force_refresh: bool = False,
    ) -> None:
        self.llm = llm
        self.embeddings = embeddings
        self.config = config
        self.text_splitter = text_splitter
        self.cache_enabled = cache_enabled
        self.cache_dir = cache_dir
        self.force_refresh = force_refresh
        self._vector_store: Chroma | None = None

    @property
    def vector_store(self) -> Chroma | None:
        """Get the underlying vector store (for cleanup)."""
        return self._vector_store

    def cleanup(self, *, preserve_cache: bool = False) -> None:
        """Clean up the vector store.

        Args:
            preserve_cache: If True, keep the on-disk store intact.
        """
        if self._vector_store is not None:
            try:
                if not preserve_cache:
                    self._vector_store.delete_collection()
            except Exception as e:
                logger.warning(f"Error cleaning up vector store: {str(e)}")
            finally:
                self._vector_store = None

    def create_rag_chain(
        self,
        analyses: Sequence[FileAnalysis],
        source_dir: Path | None = None,
    ) -> Runnable:
        """Create vector store and RAG chain from analyses using LCEL.

        Args:
            analyses: List of file analysis results
            source_dir: Source directory path (for caching)

        Returns:
            LCEL RAG chain for documentation generation

        Raises:
            VectorStoreError: If vector store creation fails
        """
        try:
            logger.info("Creating vector store...")
            documents = create_documents(analyses)

            if not documents:
                logger.error("No documentation content could be generated")
                raise DocumentationError("No documentation content could be generated")

            texts = self.text_splitter.split_documents(documents)

            if self.cache_enabled and self.cache_dir and source_dir:
                logger.debug("Cache enabled: using persistent vector store")
                current_files = [
                    Path(source_dir) / analysis.file_path for analysis in analyses
                ]

                cache = VectorStoreCache(
                    cache_dir=Path(self.cache_dir),
                    source_dir=Path(source_dir),
                    embeddings=self.embeddings,
                    force_refresh=self.force_refresh,
                )

                self._vector_store = cache.get_or_create_vector_store(
                    analyses=analyses,
                    documents=texts,
                    current_files=current_files,
                )
            else:
                logger.debug("Cache disabled: creating ephemeral vector store")
                # Chroma has one in-memory client per process, so each store
                # needs its own collection or it sees chunks from earlier runs
                self._vector_store = Chroma.from_documents(
                    texts,
                    self.embeddings,
                    collection_name=f"codeatlas-{uuid.uuid4().hex}",
                )

            retriever = self._create_retriever()

            rag_prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

            rag_chain = (
                {"context": retriever | _format_docs, "question": RunnablePassthrough()}
                | rag_prompt
                | self.llm
                | StrOutputParser()
            )

            return rag_chain
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise VectorStoreError(f"Failed to create vector store: {str(e)}")

    def _create_retriever(self):
        """Create a retriever with configurable search parameters."""
        if self.config.RETRIEVER_SEARCH_TYPE == "mmr":
            retriever = self._vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": self.config.RETRIEVER_K,
                    "fetch_k": self.config.RETRIEVER_FETCH_K,
                    "lambda_mult": self.config.RETRIEVER_LAMBDA_MULT,
                },
            )
            logger.debug(
                f"Using MMR retriever: k={self.config.RETRIEVER_K}, "
                f"fetch_k={self.config.RETRIEVER_FETCH_K}, "
                f"lambda_mult={self.config.RETRIEVER_LAMBDA_MULT}"
            )
        elif self.config.RETRIEVER_SCORE_THRESHOLD:
            retriever = self._vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "score_threshold": self.config.RETRIEVER_SCORE_THRESHOLD,
                    "k": self.config.RETRIEVER_K,
                },
            )
            logger.debug(
                f"Using similarity threshold retriever: k={self.config.RETRIEVER_K}, "
                f"threshold={self.config.RETRIEVER_SCORE_THRESHOLD}"
            )
        else:
            retriever = self._vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": self.config.RETRIEVER_K},
            )
            logger.debug(f"Using similarity retriever: k={self.config.RETRIEVER_K}")
        return retriever
