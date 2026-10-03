"""File change detection for intelligent caching.

This module detects which files have changed since the last documentation
run, from each file's modification time and size, and its content hash.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .metadata import CacheMetadata, FileMetadata

logger = logging.getLogger(__name__)


class ChangeDetectionStrategy(Enum):
    """Strategy for detecting file changes."""

    FILESYSTEM = "filesystem"  # Use mtime + content hash
    HASH_ONLY = "hash_only"  # Always check content hash


@dataclass
class ChangeDetectionResult:
    """Result of change detection.

    Attributes:
        changed_files: Set of relative paths that changed
        new_files: Set of relative paths for new files
        deleted_files: Set of relative paths for deleted files
        unchanged_files: Set of relative paths that are unchanged
        strategy_used: Detection strategy that was used
    """

    changed_files: set[str]
    new_files: set[str]
    deleted_files: set[str]
    unchanged_files: set[str]
    strategy_used: ChangeDetectionStrategy

    @property
    def total_changed(self) -> int:
        """Total number of files that need processing."""
        return len(self.changed_files) + len(self.new_files)

    @property
    def has_changes(self) -> bool:
        """Whether any changes were detected."""
        return self.total_changed > 0 or len(self.deleted_files) > 0


class FileChangeDetector:
    """Detects which files have changed since last run.

    A file whose modification time and size are unchanged, and old enough to
    trust, is unchanged; otherwise its content hash decides. Working-tree
    edits count, in or out of a git repository.
    """

    def __init__(
        self,
        source_dir: Path,
        cache_metadata: CacheMetadata | None = None,
        strategy: ChangeDetectionStrategy | None = None,
    ):
        """Initialize change detector.

        Args:
            source_dir: Source directory to analyze
            cache_metadata: Previous cache metadata, if available
            strategy: Force specific detection strategy
        """
        self.source_dir = source_dir.resolve()
        self.cache_metadata = cache_metadata
        self.strategy = strategy or ChangeDetectionStrategy.FILESYSTEM

    def detect_changes(self, current_files: list[Path]) -> ChangeDetectionResult:
        """Detect which files have changed.

        Args:
            current_files: List of current Python files

        Returns:
            ChangeDetectionResult with changed/new/deleted files
        """
        # First run - everything is new
        metadata = self.cache_metadata
        if metadata is None:
            return ChangeDetectionResult(
                changed_files=set(),
                new_files={
                    f.relative_to(self.source_dir).as_posix() for f in current_files
                },
                deleted_files=set(),
                unchanged_files=set(),
                strategy_used=ChangeDetectionStrategy.FILESYSTEM,
            )

        logger.debug(f"Using change detection strategy: {self.strategy.value}")
        return self._detect_via_filesystem(
            current_files,
            metadata,
            hash_only=self.strategy is ChangeDetectionStrategy.HASH_ONLY,
        )

    def _detect_via_filesystem(
        self,
        current_files: list[Path],
        metadata: CacheMetadata,
        hash_only: bool = False,
    ) -> ChangeDetectionResult:
        """Detect changes using filesystem metadata.

        Args:
            current_files: List of current Python files
            metadata: The previous run's cache metadata
            hash_only: If True, always compute hash (skip mtime check)

        Returns:
            ChangeDetectionResult
        """
        changed_files = set()

        for file_path in current_files:
            relative_path = file_path.relative_to(self.source_dir).as_posix()

            # Check if we have cached metadata
            cached_meta = metadata.file_metadata.get(relative_path)

            if cached_meta is None:
                # New file
                continue

            # Check if changed
            if hash_only:
                # Always compute hash
                current_hash = FileMetadata._compute_file_hash(file_path)
                if current_hash != cached_meta.content_hash:
                    changed_files.add(relative_path)
            else:
                # Use has_changed (checks mtime first, then hash)
                if cached_meta.has_changed(file_path):
                    changed_files.add(relative_path)

        strategy = (
            ChangeDetectionStrategy.HASH_ONLY
            if hash_only
            else ChangeDetectionStrategy.FILESYSTEM
        )
        return self._categorize_files(current_files, metadata, changed_files, strategy)

    def _categorize_files(
        self,
        current_files: list[Path],
        metadata: CacheMetadata,
        changed_files: set[str],
        strategy: ChangeDetectionStrategy,
    ) -> ChangeDetectionResult:
        """Categorize files into changed/new/deleted/unchanged.

        Args:
            current_files: List of current files
            metadata: The previous run's cache metadata
            changed_files: Set of relative paths that changed
            strategy: Strategy used for detection

        Returns:
            ChangeDetectionResult
        """
        # Get all current relative paths
        current_relative = {
            f.relative_to(self.source_dir).as_posix() for f in current_files
        }

        # Get all cached relative paths
        cached_relative = set(metadata.file_metadata.keys())

        # Categorize
        new_files = current_relative - cached_relative
        deleted_files = cached_relative - current_relative
        unchanged_files = current_relative - changed_files - new_files

        logger.debug(
            f"Change detection: {len(changed_files)} changed, "
            f"{len(new_files)} new, {len(deleted_files)} deleted, "
            f"{len(unchanged_files)} unchanged"
        )

        return ChangeDetectionResult(
            changed_files=changed_files,
            new_files=new_files,
            deleted_files=deleted_files,
            unchanged_files=unchanged_files,
            strategy_used=strategy,
        )
