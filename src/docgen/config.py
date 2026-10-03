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
    QualityMode.BALANCED: "claude-sonnet-5-5",
    QualityMode.BEST: "claude-opus-5-5",
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
    DEFAULT_CACHE_DIR: str = ".docgen_cache"

    # Quality mode settings
    DEFAULT_QUALITY_MODE: QualityMode = QualityMode.BALANCED

    # Parallel processing settings
    MAX_PARALLEL_WORKERS: int = 5

    # RAG retriever settings
    RETRIEVER_K: int = 10
    RETRIEVER_SEARCH_TYPE: str = "mmr"  # or "similarity"; MMR skips near-duplicates
    RETRIEVER_SCORE_THRESHOLD: float | None = None
    RETRIEVER_FETCH_K: int = 20  # For MMR
    RETRIEVER_LAMBDA_MULT: float = 0.5  # For MMR diversity
    # Share of each section's context (RETRIEVER_K chunks of CHUNK_SIZE) given
    # to code chosen from the project's structure; retrieval fills the rest.
    # 0 leaves the whole context to retrieval.
    STRUCTURAL_CONTEXT_SHARE: float = 0.6

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
        if self.MAX_PARALLEL_WORKERS <= 0:
            raise ValueError("Max parallel workers must be positive")

        # Validate RAG retriever settings
        if self.RETRIEVER_K <= 0:
            raise ValueError("Retriever K must be positive")
        if self.RETRIEVER_SEARCH_TYPE not in ("similarity", "mmr"):
            raise ValueError("Retriever search type must be 'similarity' or 'mmr'")
        threshold = self.RETRIEVER_SCORE_THRESHOLD
        if threshold is not None and not 0 <= threshold <= 1:
            raise ValueError("Retriever score threshold must be between 0 and 1")
        if threshold is not None and self.RETRIEVER_SEARCH_TYPE == "mmr":
            raise ValueError("A retriever score threshold needs similarity search")
        if self.RETRIEVER_FETCH_K <= 0:
            raise ValueError("Retriever fetch K must be positive")
        if not 0 <= self.RETRIEVER_LAMBDA_MULT <= 1:
            raise ValueError("Retriever lambda mult must be between 0 and 1")
        if not 0 <= self.STRUCTURAL_CONTEXT_SHARE <= 1:
            raise ValueError("Structural context share must be between 0 and 1")


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
