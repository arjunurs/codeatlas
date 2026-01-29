"""Cache module for the documentation generator.

This module provides caching functionality to reduce API costs by:
- Persisting vector stores across runs
- Caching generated section content
- Tracking file changes to avoid unnecessary re-processing
"""

from .change_detector import ChangeDetectionStrategy, FileChangeDetector
from .content_cache import SectionCacheEntry, SectionContentCache
from .metadata import CacheMetadata, FileMetadata
from .vector_cache import VectorStoreCache

__all__ = [
    "FileMetadata",
    "CacheMetadata",
    "FileChangeDetector",
    "ChangeDetectionStrategy",
    "VectorStoreCache",
    "SectionContentCache",
    "SectionCacheEntry",
]
