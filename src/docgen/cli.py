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

# Version string - update this when releasing new versions
__version__ = "0.1.0"


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Optional list of command line arguments

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate comprehensive documentation for Python codebases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (API keys from environment)
  docgen --source ./my_project -o ./docs

  # With .env file for API keys
  docgen --source ./my_project --api-key-env ./.env

  # Exclude test files and limit analysis
  docgen --source ./src --exclude "*_test.py" --exclude "__pycache__" --max-files 50

  # Generate only specific sections without diagrams
  docgen --source ./src --sections overview,dependencies --no-diagrams

  # Preview mode (no LLM calls)
  docgen --source ./src --dry-run

API Keys:
  Set ANTHROPIC_API_KEY and OPENAI_API_KEY environment variables,
  or use --api-key-env to specify a .env file containing them.
"""
    )

    # Version
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    # Required arguments
    parser.add_argument(
        "--source",
        required=True,
        help="Source directory containing Python files"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        default="docs",
        help="Output directory for documentation (default: docs)"
    )

    # API key arguments (only .env file path - no direct keys for security)
    parser.add_argument(
        "--api-key-env",
        metavar="PATH",
        help="Path to .env file containing API keys"
    )

    # Model options
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_CONFIG.DEFAULT_TEMPERATURE,
        metavar="TEMP",
        help=f"Temperature for LLM generation (0.0 to 1.0, default: {DEFAULT_CONFIG.DEFAULT_TEMPERATURE})"
    )
    parser.add_argument(
        "--anthropic-model",
        default=DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL,
        metavar="MODEL",
        help=f"Anthropic model to use (default: {DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL})"
    )
    parser.add_argument(
        "--openai-embedding-model",
        default=DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL,
        metavar="MODEL",
        help=f"OpenAI embedding model to use (default: {DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL})"
    )

    # Logging options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (errors only)"
    )

    # Generation options
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern to exclude files/dirs (can be repeated)"
    )
    parser.add_argument(
        "--no-diagrams",
        action="store_true",
        help="Skip diagram generation"
    )
    parser.add_argument(
        "--sections",
        metavar="LIST",
        help="Comma-separated sections to generate: overview,dependencies,classes,dataflow,integration"
    )
    parser.add_argument(
        "--diagrams",
        metavar="LIST",
        help="Comma-separated diagrams to generate: architecture,class,sequence,callgraph,dependency"
    )
    parser.add_argument(
        "--template-dir",
        metavar="PATH",
        help="Custom HTML template directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze code without LLM calls (preview mode)"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        metavar="N",
        help="Maximum number of files to analyze"
    )

    return parser.parse_args(args)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        args = parse_args()

        # Handle mutually exclusive verbose/quiet
        if args.verbose and args.quiet:
            print("Error: --verbose and --quiet are mutually exclusive", file=sys.stderr)
            sys.exit(1)

        setup_logging(verbose=args.verbose, quiet=args.quiet)

        # In dry-run mode, API keys are not required
        if args.dry_run:
            logger.info("Dry-run mode: API keys not required")
            anthropic_key = "dry-run-placeholder"
            openai_key = "dry-run-placeholder"
        else:
            # Get API keys
            anthropic_key, openai_key = get_api_keys(args.api_key_env)

        # Parse sections and diagrams if provided
        sections = None
        if args.sections:
            sections = [s.strip() for s in args.sections.split(",")]

        diagrams = None
        if args.diagrams:
            diagrams = [d.strip() for d in args.diagrams.split(",")]

        # Initialize generator
        generator = CodeDocumentationGenerator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            temperature=args.temperature,
            anthropic_model=args.anthropic_model,
            openai_embedding_model=args.openai_embedding_model,
            exclude_patterns=args.exclude,
            skip_diagrams=args.no_diagrams,
            sections=sections,
            diagrams=diagrams,
            template_dir=args.template_dir,
            dry_run=args.dry_run,
            max_files=args.max_files
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
