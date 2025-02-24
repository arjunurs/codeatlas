"""Command-line interface for the documentation generator.

This module provides the command-line interface for generating documentation,
including argument parsing and main entry point.
"""

import sys
import argparse
import logging
from typing import Optional

from .core.generator import CodeDocumentationGenerator
from .utils.api_keys import get_api_keys
from .utils.logging import setup_logging
from .exceptions.errors import DocumentationError

logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line arguments

    Example:
        >>> args = parse_args()
        >>> print(args.source)
        './my_project'
    """
    parser = argparse.ArgumentParser(
        description="Generate comprehensive documentation for Python codebases using Claude 3 Sonnet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use API keys from environment or .env file
  %(prog)s --source ./my_project --output ./docs

  # Use custom environment variable
  %(prog)s --source ./my_project --output ./docs --api-key-env CUSTOM_API_KEY

  # Provide API keys directly (least preferred)
  %(prog)s --source ./my_project --output ./docs --anthropic-api-key sk-ant-... --openai-api-key sk-...

  # Enable verbose logging
  %(prog)s --source ./my_project --output ./docs --verbose
        """
    )

    parser.add_argument(
        "--source", "-s",
        required=True,
        help="Path to the Python codebase to document"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="docs",
        help="Output directory for generated documentation (default: docs)"
    )

    # API key arguments
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument(
        "--anthropic-api-key",
        help="Anthropic API key (least preferred method)"
    )
    key_group.add_argument(
        "--api-key-env",
        help="Environment variable containing API keys"
    )

    parser.add_argument(
        "--openai-api-key",
        help="OpenAI API key for embeddings (least preferred method)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for LLM generation (0.0-1.0, default: 0.1)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--log-file",
        help="Path to log file (optional)"
    )

    return parser.parse_args()

def main() -> None:
    """Main entry point for the CLI.

    This function:
    1. Parses command line arguments
    2. Sets up logging
    3. Gets API keys
    4. Initializes the documentation generator
    5. Generates documentation
    """
    try:
        args = parse_args()
        setup_logging(args.verbose, args.log_file)
        logger.info("Starting documentation generation...")

        anthropic_key, openai_key = get_api_keys(
            args.anthropic_api_key,
            args.openai_api_key,
            args.api_key_env
        )

        generator = CodeDocumentationGenerator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            temperature=args.temperature
        )

        generator.generate_documentation(
            directory_path=args.source,
            output_dir=args.output
        )

        logger.info(
            f"Documentation generated successfully in {args.output}/documentation.html"
        )
    except Exception as e:
        logger.error(f"Documentation generation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 