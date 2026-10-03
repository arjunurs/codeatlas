"""Configuration constants for the documentation generator.

This module provides centralized configuration constants to avoid magic numbers
and make the system more configurable.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class QualityMode(Enum):
    """Quality mode presets for documentation generation.

    Each preset selects the Anthropic model used for every section:
    - FAST: Lowest cost, fastest generation (Claude Haiku)
    - BALANCED: Default; good quality at moderate cost (Claude Sonnet)
    - BEST: Highest quality, highest cost (Claude Opus)
    """

    FAST = "fast"
    BALANCED = "balanced"
    BEST = "best"


# Model selected by each quality mode preset
QUALITY_MODE_MODELS: dict[QualityMode, str] = {
    QualityMode.FAST: "claude-haiku-4-5",
    QualityMode.BALANCED: "claude-sonnet-5",
    QualityMode.BEST: "claude-opus-5",
}


@dataclass
class CacheConfig:
    """Cache-related configuration."""

    enabled: bool = True
    cache_dir: Path | None = None
    force_refresh: bool = False


@dataclass
class GenerationOptions:
    """Options controlling what the generator produces."""

    exclude_patterns: list[str] = field(default_factory=list)
    skip_diagrams: bool = False
    selected_sections: list[str] | None = None
    selected_diagrams: list[str] | None = None
    template_dir: str | None = None
    dry_run: bool = False
    max_files: int | None = None
    diagrams_only: bool = False
    parallel_sections: bool = True
    enable_cost_tracking: bool = True


@dataclass
class GeneratorConfig:
    """Configuration settings for the documentation generator."""

    # Text processing settings
    CHUNK_SIZE: int = 2000
    CHUNK_OVERLAP: int = 200

    # LLM settings
    # None = use the model's default sampling. Claude Sonnet 5+ rejects
    # non-default temperature values, so only set this for older models.
    DEFAULT_TEMPERATURE: float | None = None
    DEFAULT_ANTHROPIC_MODEL: str = QUALITY_MODE_MODELS[QualityMode.BALANCED]
    DEFAULT_OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Output limit per section. langchain-anthropic defaults to 4096, which cut
    # long sections off mid-sentence.
    DEFAULT_MAX_OUTPUT_TOKENS: int = 8192

    # Diagram settings
    MAX_DIAGRAM_NODES: int = 50

    # File processing settings
    DEFAULT_FILE_ENCODING: str = "utf-8"

    # Output settings
    DEFAULT_OUTPUT_DIR: str = "output"

    # Cache settings
    CACHE_ENABLED: bool = True
    DEFAULT_CACHE_DIR: str = ".docgen_cache"
    CACHE_TTL_DAYS: int = 30

    # Quality mode settings
    DEFAULT_QUALITY_MODE: QualityMode = QualityMode.BALANCED

    # Parallel processing settings
    PARALLEL_SECTIONS: bool = True
    MAX_PARALLEL_WORKERS: int = 5

    # RAG retriever settings
    RETRIEVER_K: int = 10
    RETRIEVER_SEARCH_TYPE: str = "similarity"  # or "mmr"
    RETRIEVER_SCORE_THRESHOLD: float | None = None
    RETRIEVER_FETCH_K: int = 20  # For MMR
    RETRIEVER_LAMBDA_MULT: float = 0.5  # For MMR diversity

    def __post_init__(self):
        """Validate configuration values."""
        if self.DEFAULT_TEMPERATURE is not None and not (
            0 <= self.DEFAULT_TEMPERATURE <= 1
        ):
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

        # Validate RAG retriever settings
        if self.RETRIEVER_K <= 0:
            raise ValueError("Retriever K must be positive")
        if self.RETRIEVER_SEARCH_TYPE not in ("similarity", "mmr"):
            raise ValueError("Retriever search type must be 'similarity' or 'mmr'")
        if self.RETRIEVER_SCORE_THRESHOLD is not None:
            if not 0 <= self.RETRIEVER_SCORE_THRESHOLD <= 1:
                raise ValueError("Retriever score threshold must be between 0 and 1")
        if self.RETRIEVER_FETCH_K <= 0:
            raise ValueError("Retriever fetch K must be positive")
        if not 0 <= self.RETRIEVER_LAMBDA_MULT <= 1:
            raise ValueError("Retriever lambda mult must be between 0 and 1")


# Default configuration instance
DEFAULT_CONFIG = GeneratorConfig()


def get_model_for_quality_mode(quality_mode: QualityMode) -> str:
    """Get the Anthropic model selected by a quality mode preset.

    Args:
        quality_mode: Quality mode preset

    Returns:
        Model name
    """
    return QUALITY_MODE_MODELS[quality_mode]


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
    retriever_k: int | None = None,
    retriever_search_type: str | None = None,
    retriever_score_threshold: float | None = None,
    retriever_fetch_k: int | None = None,
    retriever_lambda_mult: float | None = None,
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
        retriever_k: Override for retriever K
        retriever_search_type: Override for retriever search type
        retriever_score_threshold: Override for retriever score threshold
        retriever_fetch_k: Override for retriever fetch K
        retriever_lambda_mult: Override for retriever lambda mult

    Returns:
        GeneratorConfig instance with specified overrides
    """
    from dataclasses import replace

    # Map parameter names to config field names
    overrides = {
        "CHUNK_SIZE": chunk_size,
        "CHUNK_OVERLAP": chunk_overlap,
        "DEFAULT_TEMPERATURE": temperature,
        "DEFAULT_ANTHROPIC_MODEL": anthropic_model,
        "DEFAULT_OPENAI_EMBEDDING_MODEL": openai_embedding_model,
        "MAX_DIAGRAM_NODES": max_diagram_nodes,
        "DEFAULT_FILE_ENCODING": file_encoding,
        "DEFAULT_OUTPUT_DIR": output_dir,
        "CACHE_ENABLED": cache_enabled,
        "DEFAULT_CACHE_DIR": cache_dir,
        "CACHE_TTL_DAYS": cache_ttl_days,
        "DEFAULT_QUALITY_MODE": quality_mode,
        "PARALLEL_SECTIONS": parallel_sections,
        "MAX_PARALLEL_WORKERS": max_parallel_workers,
        "RETRIEVER_K": retriever_k,
        "RETRIEVER_SEARCH_TYPE": retriever_search_type,
        "RETRIEVER_SCORE_THRESHOLD": retriever_score_threshold,
        "RETRIEVER_FETCH_K": retriever_fetch_k,
        "RETRIEVER_LAMBDA_MULT": retriever_lambda_mult,
    }

    # Filter out None values (keep only explicit overrides)
    active_overrides = {k: v for k, v in overrides.items() if v is not None}

    return replace(DEFAULT_CONFIG, **active_overrides)
