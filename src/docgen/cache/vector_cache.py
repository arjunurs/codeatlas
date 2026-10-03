"""Vector store caching for persistent embeddings.

This module provides caching for Chroma vector stores to avoid
regenerating embeddings on every run.
"""

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..exceptions.errors import CacheError
from ..models.file_analysis import FileAnalysis
from ..utils.git_client import GitClient
from .change_detector import ChangeDetectionResult, FileChangeDetector
from .metadata import CacheMetadata

logger = logging.getLogger(__name__)

# Documents added per call during incremental updates. Chroma rejects a single
# add above its max batch size (5461 for the default SQLite backend).
ADD_BATCH_SIZE = 1000


def _chroma_settings() -> Settings:
    """Settings for every Chroma client codeatlas opens.

    Chroma sends anonymized usage telemetry unless it is turned off, and it
    refuses a second client on the same directory with different settings,
    so every client gets the same values. Each call returns a new object:
    Chroma writes the directory into the settings a persistent client is
    given, so a shared object would carry one store's directory into the next
    client.

    Returns:
        Settings with telemetry off
    """
    return Settings(anonymized_telemetry=False)


def persistent_chroma_client(path: Path) -> ClientAPI:
    """Open the on-disk Chroma database in a directory, with telemetry off.

    codeatlas creates its Chroma clients itself and hands them to
    langchain-chroma, because older langchain-chroma releases treat any
    client settings as a request to persist.

    Args:
        path: Directory that holds the database

    Returns:
        A Chroma client for that directory
    """
    return chromadb.PersistentClient(path=str(path), settings=_chroma_settings())


def in_memory_chroma_client() -> ClientAPI:
    """Open Chroma's in-memory database, with telemetry off.

    Returns:
        A Chroma client that writes nothing to disk
    """
    return chromadb.EphemeralClient(settings=_chroma_settings())


class VectorStoreCache:
    """Manages persistent vector store caching.

    This class handles:
    - Loading existing vector stores from disk
    - Detecting file changes since last run
    - Incrementally updating vector stores
    - Creating new vector stores when needed
    """

    def __init__(
        self,
        cache_dir: Path,
        source_dir: Path,
        embeddings: Embeddings,
        force_refresh: bool = False,
    ):
        """Initialize vector store cache.

        Args:
            cache_dir: Directory for cache storage
            source_dir: Source code directory
            embeddings: Embeddings instance for vector store
            force_refresh: If True, ignore cache and rebuild
        """
        self.cache_dir = cache_dir
        self.source_dir = source_dir.resolve()
        self.embeddings = embeddings
        self.force_refresh = force_refresh

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.vector_dir = self.cache_dir / "chromadb"

        # Load or create cache metadata
        self.metadata = CacheMetadata.load(self.cache_dir)
        if self.metadata is None or force_refresh:
            logger.debug("Creating new cache metadata")
            self.metadata = CacheMetadata.create_for_project(self.source_dir)

    def get_or_create_vector_store(
        self,
        analyses: Sequence[FileAnalysis],
        documents: list[Document],
        current_files: list[Path],
    ) -> Chroma:
        """Get existing vector store or create new one.

        Args:
            analyses: File analysis results
            documents: Documents for vector store
            current_files: List of current Python files

        Returns:
            Chroma vector store instance

        Raises:
            CacheError: If cache operations fail
        """
        try:
            # If force refresh, treat as new vector store creation
            if self.force_refresh:
                logger.debug("Force refresh: recreating vector store from scratch")
                if self._vector_store_exists():
                    self._drop_vector_store()
                self.vector_dir.mkdir(parents=True, exist_ok=True)
                return self._create_new_vector_store(analyses, documents, current_files)

            # Check if vector store exists
            if self._vector_store_exists():
                logger.debug("Found existing vector store")
                return self._load_and_update_vector_store(
                    analyses, documents, current_files
                )
            else:
                logger.debug("No existing vector store, creating new one")
                return self._create_new_vector_store(analyses, documents, current_files)

        except Exception as e:
            logger.error(f"Cache error: {str(e)}")
            raise CacheError(f"Failed to manage vector store cache: {str(e)}")

    def _vector_store_exists(self) -> bool:
        """Check if vector store exists on disk.

        Returns:
            True if vector store exists, False otherwise
        """
        # Check for Chroma's SQLite database
        chroma_db = self.vector_dir / "chroma.sqlite3"
        return chroma_db.exists()

    def _create_new_vector_store(
        self,
        analyses: Sequence[FileAnalysis],
        documents: list[Document],
        current_files: list[Path],
    ) -> Chroma:
        """Create a new vector store from scratch.

        Args:
            analyses: File analysis results
            documents: Documents for vector store
            current_files: List of current Python files

        Returns:
            New Chroma vector store
        """
        logger.debug(f"Creating vector store with {len(documents)} documents")

        # Create vector store with persistence
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            client=persistent_chroma_client(self.vector_dir),
        )

        # Update metadata for all files
        for file_path in current_files:
            self.metadata.update_file(file_path, self.source_dir)

        # Update git commit if available
        self.metadata.git_commit = self._get_git_commit()

        # Save metadata
        self.metadata.save(self.cache_dir)

        logger.debug("Vector store created and cached")
        return vector_store

    def _load_and_update_vector_store(
        self,
        analyses: Sequence[FileAnalysis],
        documents: list[Document],
        current_files: list[Path],
    ) -> Chroma:
        """Load existing vector store and update if needed.

        Args:
            analyses: File analysis results
            documents: Documents for vector store
            current_files: List of current Python files

        Returns:
            Updated Chroma vector store
        """
        # Detect changes
        detector = FileChangeDetector(self.source_dir, self.metadata)
        changes = detector.detect_changes(current_files)

        logger.debug(
            f"Change detection: {changes.total_changed} changed, "
            f"{len(changes.deleted_files)} deleted, "
            f"{len(changes.unchanged_files)} unchanged"
        )

        # Load existing vector store
        vector_store = Chroma(
            client=persistent_chroma_client(self.vector_dir),
            embedding_function=self.embeddings,
        )

        # If no changes, return as-is
        if not changes.has_changes:
            logger.debug("No changes detected, using cached vector store")
            return vector_store

        # Update vector store incrementally
        self._update_vector_store(
            vector_store, analyses, documents, changes, current_files
        )

        return vector_store

    def _update_vector_store(
        self,
        vector_store: Chroma,
        analyses: Sequence[FileAnalysis],
        documents: list[Document],
        changes: ChangeDetectionResult,
        current_files: list[Path],
    ) -> None:
        """Update vector store with changed files.

        Args:
            vector_store: Existing vector store
            analyses: File analysis results
            documents: All documents
            changes: Change detection result
            current_files: List of current files
        """
        changed_and_new = changes.changed_files | changes.new_files

        # Remove every stored chunk that does not belong to an unchanged file:
        # chunks of changed, new, and deleted files, plus any orphans
        stored = vector_store.get(include=["metadatas"])
        stale_ids = [
            doc_id
            for doc_id, meta in zip(stored["ids"], stored["metadatas"])
            if self._relative_source(meta) not in changes.unchanged_files
        ]
        if stale_ids:
            logger.debug(f"Removing {len(stale_ids)} stale documents from vector store")
            vector_store.delete(ids=stale_ids)

        docs_to_add = [
            doc
            for doc in documents
            if self._relative_source(doc.metadata) in changed_and_new
        ]
        if docs_to_add:
            logger.debug(
                f"Adding {len(docs_to_add)} documents from {len(changed_and_new)} files"
            )
            for start in range(0, len(docs_to_add), ADD_BATCH_SIZE):
                vector_store.add_documents(docs_to_add[start : start + ADD_BATCH_SIZE])

        # Record the new file state, including files that produced no
        # documents, so they are not reported as changed again
        for deleted_file in changes.deleted_files:
            self.metadata.remove_file(deleted_file)
        for file_path in current_files:
            if file_path.relative_to(self.source_dir).as_posix() in changed_and_new:
                self.metadata.update_file(file_path, self.source_dir)

        # Update git commit
        self.metadata.git_commit = self._get_git_commit()

        # Save updated metadata
        self.metadata.save(self.cache_dir)

        logger.debug("Vector store updated successfully")

    def _relative_source(self, metadata: dict | None) -> str:
        """Get a document's file path relative to the source directory.

        Documents carry the analyzed file's path under the "source" metadata
        key, as an absolute path (see rag_pipeline.create_documents). Change
        detection and cache metadata key files by relative POSIX path.

        Args:
            metadata: Document metadata

        Returns:
            Relative POSIX path of the document's source file, or the source
            unchanged if it is outside the source directory
        """
        source = (metadata or {}).get("source", "")
        try:
            return (self.source_dir / source).relative_to(self.source_dir).as_posix()
        except ValueError:
            return source

    def _drop_vector_store(self) -> None:
        """Delete the persisted vector store so it can be rebuilt.

        Drops the collection through Chroma rather than deleting the
        directory. Chroma keeps an open handle per persist directory for the
        life of the process, and removing the files underneath it leaves that
        handle read-only. If the store cannot be opened at all (for example a
        corrupt database), the directory is deleted instead and Chroma's
        process-wide client cache is cleared so the rebuild gets a fresh
        handle. Clearing that cache invalidates any other Chroma client open
        in this process.
        """
        try:
            Chroma(
                client=persistent_chroma_client(self.vector_dir),
                embedding_function=self.embeddings,
            ).delete_collection()
        except Exception as e:
            logger.warning(
                f"Could not open existing vector store ({e}), deleting {self.vector_dir}"
            )
            shutil.rmtree(self.vector_dir)
            SharedSystemClient.clear_system_cache()

    def _get_git_commit(self) -> str | None:
        """Get current git commit hash.

        Returns:
            Commit hash or None
        """
        return GitClient(self.source_dir).get_current_commit()

    def cleanup(self, preserve_cache: bool = True) -> None:
        """Clean up vector store resources.

        Args:
            preserve_cache: If True, keep cache on disk (default)
        """
        if not preserve_cache and self.vector_dir.exists():
            logger.debug("Cleaning up vector store cache")
            shutil.rmtree(self.vector_dir)
