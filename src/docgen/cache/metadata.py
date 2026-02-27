"""Metadata tracking for cache management.

This module provides data structures for tracking file metadata,
cache state, and change detection across documentation runs.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FileMetadata:
    """Metadata for a single file in the cache.

    Attributes:
        path: Relative path from source directory
        content_hash: SHA-256 hash of file content
        mtime: Last modification timestamp
        size: File size in bytes
        last_analyzed: Timestamp when file was last analyzed
    """

    path: str
    content_hash: str
    mtime: float
    size: int
    last_analyzed: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["last_analyzed"] = self.last_analyzed.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "FileMetadata":
        """Create from dictionary (JSON deserialization)."""
        data = data.copy()
        data["last_analyzed"] = datetime.fromisoformat(data["last_analyzed"])
        return cls(**data)

    @classmethod
    def from_file(cls, file_path: Path, source_dir: Path) -> "FileMetadata":
        """Create metadata from a file.

        Args:
            file_path: Absolute path to the file
            source_dir: Source directory for relative path calculation

        Returns:
            FileMetadata instance
        """
        stat = file_path.stat()
        content_hash = cls._compute_file_hash(file_path)
        relative_path = file_path.relative_to(source_dir).as_posix()

        return cls(
            path=relative_path,
            content_hash=content_hash,
            mtime=stat.st_mtime,
            size=stat.st_size,
        )

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            Hex string of file hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def has_changed(self, file_path: Path) -> bool:
        """Check if file has changed since last analysis.

        Args:
            file_path: Path to file to check

        Returns:
            True if file has changed, False otherwise
        """
        try:
            stat = file_path.stat()
            # Quick check: if mtime and size match, likely unchanged
            if stat.st_mtime == self.mtime and stat.st_size == self.size:
                return False

            # Content hash check for definitive answer
            current_hash = self._compute_file_hash(file_path)
            return current_hash != self.content_hash
        except OSError:
            # File doesn't exist or can't be read
            return True


@dataclass
class CacheMetadata:
    """Metadata for the entire cache.

    Attributes:
        project_path: Absolute path to the source directory
        project_hash: Hash of the project path
        created_at: Timestamp when cache was created
        last_updated: Timestamp of last cache update
        file_metadata: Dictionary of file path -> FileMetadata
        git_commit: Optional git commit hash at last run
        cache_version: Cache format version for migrations
    """

    project_path: str
    project_hash: str
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    file_metadata: dict[str, FileMetadata] = field(default_factory=dict)
    git_commit: str | None = None
    cache_version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_path": self.project_path,
            "project_hash": self.project_hash,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "file_metadata": {
                path: meta.to_dict() for path, meta in self.file_metadata.items()
            },
            "git_commit": self.git_commit,
            "cache_version": self.cache_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheMetadata":
        """Create from dictionary (JSON deserialization)."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        data["file_metadata"] = {
            path: FileMetadata.from_dict(meta)
            for path, meta in data["file_metadata"].items()
        }
        return cls(**data)

    @classmethod
    def create_for_project(cls, project_path: Path) -> "CacheMetadata":
        """Create new cache metadata for a project.

        Args:
            project_path: Path to project source directory

        Returns:
            New CacheMetadata instance
        """
        project_str = str(project_path.resolve())
        project_hash = hashlib.sha256(project_str.encode()).hexdigest()[:16]

        return cls(
            project_path=project_str,
            project_hash=project_hash,
        )

    def save(self, cache_dir: Path) -> None:
        """Save metadata to cache directory (convenience, delegates to CacheMetadataStore)."""
        CacheMetadataStore.save(self, cache_dir)

    @classmethod
    def load(cls, cache_dir: Path) -> Optional["CacheMetadata"]:
        """Load metadata from cache directory (convenience, delegates to CacheMetadataStore)."""
        return CacheMetadataStore.load(cache_dir)

    def update_file(self, file_path: Path, source_dir: Path) -> None:
        """Update metadata for a single file.

        Args:
            file_path: Absolute path to file
            source_dir: Source directory for relative path
        """
        metadata = FileMetadata.from_file(file_path, source_dir)
        self.file_metadata[metadata.path] = metadata
        self.last_updated = datetime.now()

    def remove_file(self, relative_path: str) -> None:
        """Remove file from metadata (e.g., deleted files).

        Args:
            relative_path: Relative path from source directory
        """
        self.file_metadata.pop(relative_path, None)
        self.last_updated = datetime.now()


class CacheMetadataStore:
    """Handles persistence (save/load) for CacheMetadata.

    Separates I/O concerns from the data class.
    """

    METADATA_FILENAME = "file_metadata.json"

    @staticmethod
    def save(metadata: CacheMetadata, cache_dir: Path) -> None:
        """Save metadata to cache directory.

        Args:
            metadata: CacheMetadata to save
            cache_dir: Cache directory for this project
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = cache_dir / CacheMetadataStore.METADATA_FILENAME

        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    @staticmethod
    def load(cache_dir: Path) -> CacheMetadata | None:
        """Load metadata from cache directory.

        Args:
            cache_dir: Cache directory for this project

        Returns:
            CacheMetadata instance if exists, None otherwise
        """
        metadata_file = cache_dir / CacheMetadataStore.METADATA_FILENAME

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file) as f:
                data = json.load(f)
            return CacheMetadata.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache corruption - return None to trigger rebuild
            return None
