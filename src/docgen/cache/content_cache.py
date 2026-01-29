"""Section content caching for documentation generation.

This module provides caching for generated documentation section content
to avoid regenerating sections when their dependencies haven't changed.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..models.file_analysis import FileAnalysis

logger = logging.getLogger(__name__)


@dataclass
class SectionCacheEntry:
    """Cache entry for a single documentation section.

    Attributes:
        section_name: Name of the section
        content_hash: Hash of the code dependencies
        content: Generated section content
        cached_at: When this entry was cached
        dependency_files: Set of file paths this section depends on
    """

    section_name: str
    content_hash: str
    content: str
    cached_at: datetime = field(default_factory=datetime.now)
    dependency_files: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "section_name": self.section_name,
            "content_hash": self.content_hash,
            "content": self.content,
            "cached_at": self.cached_at.isoformat(),
            "dependency_files": list(self.dependency_files),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SectionCacheEntry":
        """Create from dictionary (JSON deserialization)."""
        data = data.copy()
        data["cached_at"] = datetime.fromisoformat(data["cached_at"])
        data["dependency_files"] = set(data["dependency_files"])
        return cls(**data)


def _normalize_section_name(name: str) -> str:
    """Normalize section name for dependency lookup.

    Converts "Key Classes and Functions" -> "key_classes_functions"
    """
    return name.lower().replace(" ", "_").replace("_and_", "_")


class SectionContentCache:
    """Manages caching of generated documentation section content.

    Each section's content is cached with a hash of its code dependencies.
    When files change, only sections that depend on those files are regenerated.
    """

    # Define which files each section type depends on (use normalized names)
    SECTION_DEPENDENCIES = {
        "overview": "all",
        "dependencies": "imports",
        "key_classes_functions": "entities",
        "data_flow": "entities",
        "integration_points": "imports",
        # Optional sections
        "migration_guidance": "all",
        "code_quality_insights": "all",
        "cross_reference_documentation": "entities",
    }

    def __init__(self, cache_dir: Path):
        """Initialize section content cache.

        Args:
            cache_dir: Directory for cache storage
        """
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "section_cache.json"
        self.cache: dict[str, SectionCacheEntry] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    data = json.load(f)
                self.cache = {
                    name: SectionCacheEntry.from_dict(entry)
                    for name, entry in data.items()
                }
                logger.info(f"Loaded section cache with {len(self.cache)} entries")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load section cache: {e}")
                self.cache = {}

    def save_cache(self) -> None:
        """Save cache to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w") as f:
            data = {name: entry.to_dict() for name, entry in self.cache.items()}
            json.dump(data, f, indent=2)
        logger.info(f"Saved section cache with {len(self.cache)} entries")

    def get_section_hash(
        self,
        section_name: str,
        analyses: list[FileAnalysis],
    ) -> tuple[str, set[str]]:
        """Compute hash for a section based on its dependencies.

        Args:
            section_name: Name of the section
            analyses: List of file analyses

        Returns:
            Tuple of (content hash, set of dependency file paths)
        """
        normalized_name = _normalize_section_name(section_name)
        dependency_type = self.SECTION_DEPENDENCIES.get(normalized_name, "all")
        hasher = hashlib.sha256()
        dependency_files = set()

        sorted_analyses = sorted(analyses, key=lambda a: a.file_path)

        for analysis in sorted_analyses:
            hasher.update(analysis.file_path.encode())
            dependency_files.add(analysis.file_path)

            if dependency_type == "all":
                hasher.update(analysis.content.encode())
            elif dependency_type == "imports":
                for imp in sorted(analysis.imports):
                    hasher.update(imp.encode())
            elif dependency_type == "entities":
                for entity in sorted(analysis.entities, key=lambda e: e.name):
                    hasher.update(entity.name.encode())
                    hasher.update(entity.type.encode())
                    if entity.docstring:
                        hasher.update(entity.docstring.encode())

        return hasher.hexdigest(), dependency_files

    def get_cached_section(
        self,
        section_name: str,
        analyses: list[FileAnalysis],
    ) -> str | None:
        """Get cached content for a section if valid.

        Args:
            section_name: Name of the section
            analyses: Current file analyses

        Returns:
            Cached content if valid, None otherwise
        """
        if section_name not in self.cache:
            logger.debug(f"No cache entry for section: {section_name}")
            return None

        # Compute current hash
        current_hash, _ = self.get_section_hash(section_name, analyses)

        # Check if cached hash matches
        cached_entry = self.cache[section_name]
        if cached_entry.content_hash == current_hash:
            logger.info(f"Cache hit for section: {section_name}")
            return cached_entry.content
        else:
            logger.info(f"Cache miss for section: {section_name} (hash mismatch)")
            return None

    def cache_section(
        self,
        section_name: str,
        content: str,
        analyses: list[FileAnalysis],
    ) -> None:
        """Cache generated section content.

        Args:
            section_name: Name of the section
            content: Generated content
            analyses: File analyses used to generate content
        """
        content_hash, dependency_files = self.get_section_hash(section_name, analyses)

        entry = SectionCacheEntry(
            section_name=section_name,
            content_hash=content_hash,
            content=content,
            dependency_files=dependency_files,
        )

        self.cache[section_name] = entry
        logger.info(f"Cached section: {section_name}")

    def invalidate_sections(self, changed_files: set[str]) -> set[str]:
        """Invalidate sections that depend on changed files.

        Args:
            changed_files: Set of file paths that changed

        Returns:
            Set of section names that were invalidated
        """
        invalidated = set()

        for section_name, entry in list(self.cache.items()):
            # Check if any dependency files changed
            if entry.dependency_files & changed_files:
                del self.cache[section_name]
                invalidated.add(section_name)
                logger.info(f"Invalidated section: {section_name}")

        return invalidated

    def clear(self) -> None:
        """Clear all cached sections."""
        self.cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("Cleared section cache")

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_size = sum(len(entry.content) for entry in self.cache.values())
        return {
            "total_sections": len(self.cache),
            "total_size_bytes": total_size,
            "sections": list(self.cache.keys()),
        }
