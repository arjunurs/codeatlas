"""Vector store caching for persistent embeddings.

This module provides caching for Chroma vector stores to avoid
regenerating embeddings on every run.
"""

import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..exceptions.errors import CacheError
from ..models.file_analysis import FileAnalysis
from .change_detector import ChangeDetectionResult, FileChangeDetector
from .metadata import CacheMetadata

logger = logging.getLogger(__name__)


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
            logger.info("Creating new cache metadata")
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
                logger.info("Force refresh: recreating vector store from scratch")
                if self.vector_dir.exists():
                    import shutil

                    shutil.rmtree(self.vector_dir)
                self.vector_dir.mkdir(parents=True, exist_ok=True)
                return self._create_new_vector_store(analyses, documents, current_files)

            # Check if vector store exists
            if self._vector_store_exists():
                logger.info("Found existing vector store")
                return self._load_and_update_vector_store(
                    analyses, documents, current_files
                )
            else:
                logger.info("No existing vector store, creating new one")
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
        logger.info(f"Creating vector store with {len(documents)} documents")

        # Create vector store with persistence
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=str(self.vector_dir),
        )

        # Update metadata for all files
        for file_path in current_files:
            self.metadata.update_file(file_path, self.source_dir)

        # Update git commit if available
        self.metadata.git_commit = self._get_git_commit()

        # Save metadata
        self.metadata.save(self.cache_dir)

        logger.info("Vector store created and cached")
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

        logger.info(
            f"Change detection: {changes.total_changed} changed, "
            f"{len(changes.deleted_files)} deleted, "
            f"{len(changes.unchanged_files)} unchanged"
        )

        # Load existing vector store
        vector_store = Chroma(
            persist_directory=str(self.vector_dir),
            embedding_function=self.embeddings,
        )

        # If no changes, return as-is
        if not changes.has_changes:
            logger.info("No changes detected, using cached vector store")
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
        # Build map of file path -> documents
        doc_map = {}
        for doc in documents:
            file_path = doc.metadata.get("file_path", "")
            if file_path not in doc_map:
                doc_map[file_path] = []
            doc_map[file_path].append(doc)

        # Remove deleted files from vector store
        for deleted_file in changes.deleted_files:
            logger.info(f"Removing deleted file from vector store: {deleted_file}")
            try:
                # Delete documents with this file path
                vector_store.delete(where={"file_path": deleted_file})
                self.metadata.remove_file(deleted_file)
            except Exception as e:
                logger.warning(f"Failed to remove {deleted_file}: {e}")

        # Add/update changed and new files
        changed_and_new = changes.changed_files | changes.new_files

        if changed_and_new:
            # Collect documents for changed/new files
            docs_to_add = []
            for file_path in changed_and_new:
                if file_path in doc_map:
                    docs_to_add.extend(doc_map[file_path])

            if docs_to_add:
                logger.info(
                    f"Updating vector store with {len(docs_to_add)} documents from {len(changed_and_new)} files"
                )

                # Remove old versions first
                for file_path in changed_and_new:
                    try:
                        vector_store.delete(where={"file_path": file_path})
                    except Exception as e:
                        logger.debug(f"No existing docs to delete for {file_path}: {e}")

                # Add new versions
                vector_store.add_documents(docs_to_add)

                # Update metadata for changed/new files
                for file_path in current_files:
                    relative_path = file_path.relative_to(self.source_dir).as_posix()
                    if relative_path in changed_and_new:
                        self.metadata.update_file(file_path, self.source_dir)

        # Update git commit
        self.metadata.git_commit = self._get_git_commit()

        # Save updated metadata
        self.metadata.save(self.cache_dir)

        logger.info("Vector store updated successfully")

    def _get_git_commit(self) -> str | None:
        """Get current git commit hash.

        Returns:
            Commit hash or None
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.source_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def cleanup(self, preserve_cache: bool = True) -> None:
        """Clean up vector store resources.

        Args:
            preserve_cache: If True, keep cache on disk (default)
        """
        if not preserve_cache and self.vector_dir.exists():
            import shutil

            logger.info("Cleaning up vector store cache")
            shutil.rmtree(self.vector_dir)
