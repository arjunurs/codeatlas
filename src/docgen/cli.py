"""Command-line interface for the documentation generator.

This module provides the command-line interface for generating documentation,
including argument parsing and main execution flow.
"""

import argparse
import logging
import sys
from typing import List, Optional

from docgen.config import DEFAULT_CONFIG
from docgen.core.generator import CodeDocumentationGenerator
from docgen.utils.api_keys import get_api_keys
from docgen.utils.logging import setup_logging
from .exceptions.errors import DocumentationError, ApiKeyError

logger = logging.getLogger(__name__)

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Optional list of command line arguments

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate comprehensive documentation for Python codebases"
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Source directory containing Python files"
    )
    parser.add_argument(
        "--output",
        default="docs",
        help="Output directory for documentation (default: docs)"
    )

    # API key arguments
    parser.add_argument(
        "--anthropic-api-key",
        help="Anthropic API key (can also be set via ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--openai-api-key",
        help="OpenAI API key (can also be set via OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--api-key-env",
        help="Path to .env file containing API keys"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_CONFIG.DEFAULT_TEMPERATURE,
        help=f"Temperature for LLM generation (0.0 to 1.0, default: {DEFAULT_CONFIG.DEFAULT_TEMPERATURE})"
    )
    parser.add_argument(
        "--anthropic-model",
        default=DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL,
        help=f"Anthropic model to use (default: {DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL})"
    )
    parser.add_argument(
        "--openai-embedding-model",
        default=DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL,
        help=f"OpenAI embedding model to use (default: {DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL})"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args(args)

def main() -> None:
    """Main entry point for the CLI."""
    try:
        args = parse_args()
        setup_logging(args.verbose)

        # Get API keys
        anthropic_key, openai_key = get_api_keys(
            args.anthropic_api_key,
            args.openai_api_key,
            args.api_key_env
        )

        # Initialize generator
        generator = CodeDocumentationGenerator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            temperature=args.temperature,
            anthropic_model=args.anthropic_model,
            openai_embedding_model=args.openai_embedding_model
        )

        # Generate documentation
        generator.generate_documentation(args.source, args.output)

        logger.info("Documentation generated successfully")

    except (DocumentationError, ApiKeyError, ValueError) as e:
        logger.error(f"Documentation generation failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 