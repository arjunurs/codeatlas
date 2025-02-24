"""Command-line interface for the documentation generator.

This module provides the command-line interface for generating documentation,
including argument parsing and main execution flow.
"""

import argparse
import logging
import sys
from typing import List, Optional

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

    # API key arguments are mutually exclusive
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument(
        "--anthropic-api-key",
        help="Anthropic API key"
    )
    key_group.add_argument(
        "--openai-api-key",
        help="OpenAI API key"
    )
    key_group.add_argument(
        "--api-key-env",
        help="Path to .env file containing API keys"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for LLM generation (0.0 to 1.0)"
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
            temperature=args.temperature
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