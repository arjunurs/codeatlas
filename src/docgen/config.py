"""Configuration constants for the documentation generator.

This module provides centralized configuration constants to avoid magic numbers
and make the system more configurable.
"""

from dataclasses import dataclass
from enum import Enum


class QualityMode(Enum):
    """Quality mode presets for documentation generation.

    These presets balance cost and quality:
    - FAST: Lowest cost, fastest generation (Haiku for everything)
    - BALANCED: Good balance of cost and quality (Haiku for sections, Sonnet for complex tasks)
    - BEST: Highest quality, highest cost (Sonnet for everything)
    """

    FAST = "fast"
    BALANCED = "balanced"
    BEST = "best"


@dataclass
class GeneratorConfig:
    """Configuration settings for the documentation generator."""

    # Text processing settings
    CHUNK_SIZE: int = 2000
    CHUNK_OVERLAP: int = 200

    # LLM settings
    DEFAULT_TEMPERATURE: float = 0.2
    DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    DEFAULT_OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Diagram settings
    MAX_DIAGRAM_NODES: int = 50

    # File processing settings
    DEFAULT_FILE_ENCODING: str = "utf-8"

    # Output settings
    DEFAULT_OUTPUT_DIR: str = "docs"

    # Cache settings
    CACHE_ENABLED: bool = True
    DEFAULT_CACHE_DIR: str = ".docgen_cache"
    CACHE_TTL_DAYS: int = 30

    # Quality mode settings
    DEFAULT_QUALITY_MODE: QualityMode = QualityMode.BALANCED

    # Parallel processing settings
    PARALLEL_SECTIONS: bool = True
    MAX_PARALLEL_WORKERS: int = 5

    def __post_init__(self):
        """Validate configuration values."""
        if not 0 <= self.DEFAULT_TEMPERATURE <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        if self.CHUNK_SIZE <= 0:
            raise ValueError("Chunk size must be positive")
        if self.CHUNK_OVERLAP < 0:
            raise ValueError("Chunk overlap cannot be negative")
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.MAX_DIAGRAM_NODES <= 0:
            raise ValueError("Max diagram nodes must be positive")
        if self.CACHE_TTL_DAYS <= 0:
            raise ValueError("Cache TTL days must be positive")
        if self.MAX_PARALLEL_WORKERS <= 0:
            raise ValueError("Max parallel workers must be positive")


# Default configuration instance
DEFAULT_CONFIG = GeneratorConfig()


def get_model_for_quality_mode(quality_mode: QualityMode, task: str = "general") -> str:
    """Get recommended model for quality mode and task.

    Args:
        quality_mode: Quality mode preset
        task: Task type ('general', 'simple', 'complex')

    Returns:
        Model name
    """
    HAIKU = "claude-haiku-4"
    SONNET = "claude-sonnet-4-20250514"

    if quality_mode == QualityMode.FAST:
        return HAIKU
    if quality_mode == QualityMode.BEST:
        return SONNET
    # BALANCED: use Sonnet for complex tasks, Haiku otherwise
    return SONNET if task == "complex" else HAIKU


def create_config(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    temperature: float | None = None,
    anthropic_model: str | None = None,
    openai_embedding_model: str | None = None,
    max_diagram_nodes: int | None = None,
    file_encoding: str | None = None,
    output_dir: str | None = None,
    cache_enabled: bool | None = None,
    cache_dir: str | None = None,
    cache_ttl_days: int | None = None,
    quality_mode: QualityMode | None = None,
    parallel_sections: bool | None = None,
    max_parallel_workers: int | None = None,
) -> GeneratorConfig:
    """Create a custom configuration with overrides.

    Args:
        chunk_size: Override for text chunk size
        chunk_overlap: Override for text chunk overlap
        temperature: Override for LLM temperature
        anthropic_model: Override for Anthropic model name
        openai_embedding_model: Override for OpenAI embedding model
        max_diagram_nodes: Override for maximum diagram nodes
        file_encoding: Override for file encoding
        output_dir: Override for default output directory
        cache_enabled: Override for cache enabled flag
        cache_dir: Override for cache directory
        cache_ttl_days: Override for cache TTL days
        quality_mode: Override for quality mode
        parallel_sections: Override for parallel sections flag
        max_parallel_workers: Override for max parallel workers

    Returns:
        GeneratorConfig instance with specified overrides
    """
    return GeneratorConfig(
        CHUNK_SIZE=chunk_size or DEFAULT_CONFIG.CHUNK_SIZE,
        CHUNK_OVERLAP=chunk_overlap or DEFAULT_CONFIG.CHUNK_OVERLAP,
        DEFAULT_TEMPERATURE=temperature or DEFAULT_CONFIG.DEFAULT_TEMPERATURE,
        DEFAULT_ANTHROPIC_MODEL=anthropic_model
        or DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL,
        DEFAULT_OPENAI_EMBEDDING_MODEL=openai_embedding_model
        or DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL,
        MAX_DIAGRAM_NODES=max_diagram_nodes or DEFAULT_CONFIG.MAX_DIAGRAM_NODES,
        DEFAULT_FILE_ENCODING=file_encoding or DEFAULT_CONFIG.DEFAULT_FILE_ENCODING,
        DEFAULT_OUTPUT_DIR=output_dir or DEFAULT_CONFIG.DEFAULT_OUTPUT_DIR,
        CACHE_ENABLED=cache_enabled
        if cache_enabled is not None
        else DEFAULT_CONFIG.CACHE_ENABLED,
        DEFAULT_CACHE_DIR=cache_dir or DEFAULT_CONFIG.DEFAULT_CACHE_DIR,
        CACHE_TTL_DAYS=cache_ttl_days or DEFAULT_CONFIG.CACHE_TTL_DAYS,
        DEFAULT_QUALITY_MODE=quality_mode or DEFAULT_CONFIG.DEFAULT_QUALITY_MODE,
        PARALLEL_SECTIONS=parallel_sections
        if parallel_sections is not None
        else DEFAULT_CONFIG.PARALLEL_SECTIONS,
        MAX_PARALLEL_WORKERS=max_parallel_workers
        or DEFAULT_CONFIG.MAX_PARALLEL_WORKERS,
    )
