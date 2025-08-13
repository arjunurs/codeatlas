"""Configuration constants for the documentation generator.

This module provides centralized configuration constants to avoid magic numbers
and make the system more configurable.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GeneratorConfig:
    """Configuration settings for the documentation generator."""
    
    # Text processing settings
    CHUNK_SIZE: int = 2000
    CHUNK_OVERLAP: int = 200
    
    # LLM settings
    DEFAULT_TEMPERATURE: float = 0.2
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    DEFAULT_OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Diagram settings
    MAX_DIAGRAM_NODES: int = 50
    
    # File processing settings
    DEFAULT_FILE_ENCODING: str = "utf-8"
    
    # Output settings
    DEFAULT_OUTPUT_DIR: str = "docs"
    
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


# Default configuration instance
DEFAULT_CONFIG = GeneratorConfig()


def create_config(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    temperature: Optional[float] = None,
    anthropic_model: Optional[str] = None,
    openai_embedding_model: Optional[str] = None,
    max_diagram_nodes: Optional[int] = None,
    file_encoding: Optional[str] = None,
    output_dir: Optional[str] = None,
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
        
    Returns:
        GeneratorConfig instance with specified overrides
    """
    return GeneratorConfig(
        CHUNK_SIZE=chunk_size or DEFAULT_CONFIG.CHUNK_SIZE,
        CHUNK_OVERLAP=chunk_overlap or DEFAULT_CONFIG.CHUNK_OVERLAP,
        DEFAULT_TEMPERATURE=temperature or DEFAULT_CONFIG.DEFAULT_TEMPERATURE,
        DEFAULT_ANTHROPIC_MODEL=anthropic_model or DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL,
        DEFAULT_OPENAI_EMBEDDING_MODEL=openai_embedding_model or DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL,
        MAX_DIAGRAM_NODES=max_diagram_nodes or DEFAULT_CONFIG.MAX_DIAGRAM_NODES,
        DEFAULT_FILE_ENCODING=file_encoding or DEFAULT_CONFIG.DEFAULT_FILE_ENCODING,
        DEFAULT_OUTPUT_DIR=output_dir or DEFAULT_CONFIG.DEFAULT_OUTPUT_DIR,
    )