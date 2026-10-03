"""Command-line interface for the documentation generator.

This module provides the command-line interface for generating documentation,
including argument parsing and main execution flow.
"""

import argparse
import importlib.metadata
import logging
import sys
from dataclasses import replace
from pathlib import Path

from docgen.config import (
    DEFAULT_CONFIG,
    QUALITY_MODE_MODELS,
    CacheConfig,
    GenerationOptions,
    GeneratorConfig,
    QualityMode,
)
from docgen.core.generator import CodeDocumentationGenerator
from docgen.providers.registry import create_default_providers
from docgen.utils.api_keys import get_api_keys
from docgen.utils.logging import setup_logging

from .cache.metadata import CacheMetadata
from .exceptions.errors import ApiKeyError, CacheError, DocumentationError

logger = logging.getLogger(__name__)


def _package_version() -> str:
    """Return the installed package version, set in pyproject.toml.

    Returns:
        The version, or "0.0.0+unknown" when the package is not installed, for
        example when the source tree is imported directly
    """
    try:
        return importlib.metadata.version("codeatlas")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _package_version()


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    """Add source, output, and API key arguments."""
    parser.add_argument(
        "--version", "-V", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--source", required=True, help="Source directory containing Python files"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_CONFIG.DEFAULT_OUTPUT_DIR,
        help="Output directory for generated documentation (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key-env", metavar="PATH", help="Path to .env file containing API keys"
    )


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    """Add model configuration arguments."""
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_CONFIG.DEFAULT_TEMPERATURE,
        metavar="TEMP",
        help=(
            "Temperature for LLM generation (0.0-1.0, default: model default; "
            "not supported by Claude Sonnet 5 and newer)"
        ),
    )
    parser.add_argument(
        "--anthropic-model",
        metavar="MODEL",
        help="Anthropic model to use; overrides --quality-mode",
    )
    parser.add_argument(
        "--openai-embedding-model",
        default=DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL,
        metavar="MODEL",
        help=f"OpenAI embedding model to use (default: {DEFAULT_CONFIG.DEFAULT_OPENAI_EMBEDDING_MODEL})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Minimal output (errors only)"
    )


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add generation and output arguments."""
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern to exclude files/dirs (can be repeated)",
    )
    parser.add_argument(
        "--no-diagrams", action="store_true", help="Skip diagram generation"
    )
    parser.add_argument(
        "--diagrams-only",
        action="store_true",
        help="Generate only diagrams without LLM section generation (no API costs)",
    )
    parser.add_argument(
        "--sections",
        metavar="LIST",
        help="Comma-separated sections: overview,dependencies,classes,dataflow,integration (optional: migration_guidance,code_quality,cross_reference)",
    )
    parser.add_argument(
        "--diagrams",
        metavar="LIST",
        help="Comma-separated diagrams to generate: architecture,class,sequence,callgraph,dependency",
    )
    parser.add_argument(
        "--template-dir", metavar="PATH", help="Custom HTML template directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze code without LLM calls (preview mode)",
    )
    parser.add_argument(
        "--max-files", type=int, metavar="N", help="Maximum number of files to analyze"
    )
    parser.add_argument(
        "--quality-mode",
        choices=[mode.value for mode in QualityMode],
        default=DEFAULT_CONFIG.DEFAULT_QUALITY_MODE.value,
        help="Model preset: "
        + ", ".join(
            f"{mode.value} ({model}"
            + (", default)" if mode == DEFAULT_CONFIG.DEFAULT_QUALITY_MODE else ")")
            for mode, model in QUALITY_MODE_MODELS.items()
        ),
    )
    parser.add_argument(
        "--no-parallel", action="store_true", help="Disable parallel section generation"
    )
    parser.add_argument(
        "--no-cost-tracking",
        action="store_true",
        help="Disable API cost tracking and summary",
    )


def _add_cache_args(parser: argparse.ArgumentParser) -> None:
    """Add cache-related arguments."""
    parser.add_argument(
        "--cache-dir",
        metavar="PATH",
        help=f"Cache directory (default: {DEFAULT_CONFIG.DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (regenerate everything)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache and regenerate all content",
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear cache and exit"
    )
    parser.add_argument(
        "--cache-stats", action="store_true", help="Show cache statistics and exit"
    )


def _add_rag_args(parser: argparse.ArgumentParser) -> None:
    """Add RAG retrieval arguments."""
    rag_group = parser.add_argument_group("RAG Retrieval Options")
    rag_group.add_argument(
        "--retriever-k",
        type=int,
        default=DEFAULT_CONFIG.RETRIEVER_K,
        metavar="N",
        help="Number of documents to retrieve per query (default: %(default)s)",
    )
    rag_group.add_argument(
        "--retriever-search-type",
        choices=["similarity", "mmr"],
        default=DEFAULT_CONFIG.RETRIEVER_SEARCH_TYPE,
        help="Retrieval method: similarity or mmr (diversity-focused); "
        "default: %(default)s",
    )
    rag_group.add_argument(
        "--retriever-score-threshold",
        type=float,
        metavar="FLOAT",
        help="Minimum similarity score threshold (0.0-1.0, optional)",
    )
    rag_group.add_argument(
        "--retriever-fetch-k",
        type=int,
        default=DEFAULT_CONFIG.RETRIEVER_FETCH_K,
        metavar="N",
        help="Number of documents to fetch before MMR reranking (default: %(default)s)",
    )
    rag_group.add_argument(
        "--retriever-lambda-mult",
        type=float,
        default=DEFAULT_CONFIG.RETRIEVER_LAMBDA_MULT,
        metavar="FLOAT",
        help="MMR diversity parameter: 0=max diversity, 1=max relevance "
        "(default: %(default)s)",
    )


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
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
""",
    )

    _add_source_args(parser)
    _add_model_args(parser)
    _add_output_args(parser)
    _add_cache_args(parser)
    _add_rag_args(parser)

    return parser.parse_args(args)


def _get_cache_dir(args: argparse.Namespace, source_path: Path) -> Path:
    """Get cache directory for the project.

    Args:
        args: Parsed command line arguments
        source_path: Source directory path

    Returns:
        Path to cache directory
    """
    if args.cache_dir:
        base_cache_dir = Path(args.cache_dir)
    else:
        base_cache_dir = Path(DEFAULT_CONFIG.DEFAULT_CACHE_DIR)

    # Create project-specific subdirectory based on source path hash
    metadata = CacheMetadata.create_for_project(source_path)
    return base_cache_dir / metadata.project_hash


def _generator_config(args: argparse.Namespace) -> GeneratorConfig:
    """Apply the --retriever-* options to the default config.

    Args:
        args: Parsed command line arguments

    Returns:
        The default config with the retrieval settings replaced

    Raises:
        ValueError: If a retrieval setting is out of range
    """
    overrides = {
        "RETRIEVER_K": args.retriever_k,
        "RETRIEVER_SEARCH_TYPE": args.retriever_search_type,
        "RETRIEVER_SCORE_THRESHOLD": args.retriever_score_threshold,
        "RETRIEVER_FETCH_K": args.retriever_fetch_k,
        "RETRIEVER_LAMBDA_MULT": args.retriever_lambda_mult,
    }
    return replace(
        DEFAULT_CONFIG, **{k: v for k, v in overrides.items() if v is not None}
    )


def _handle_clear_cache(cache_dir: Path) -> int:
    """Clear cache directory.

    Args:
        cache_dir: Path to cache directory

    Returns:
        Exit status code (0 for success)
    """
    import shutil

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"Cache cleared: {cache_dir}")
    else:
        print("No cache found")
    return 0


def _handle_cache_stats(cache_dir: Path) -> int:
    """Show cache statistics.

    Args:
        cache_dir: Path to cache directory

    Returns:
        Exit status code (0 for success)
    """
    if not cache_dir.exists():
        print("No cache found")
        return 0

    # Load cache metadata
    metadata = CacheMetadata.load(cache_dir)
    if not metadata:
        print("Cache exists but is corrupted or empty")
        return 0

    # Calculate cache size
    total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())

    print("Cache Statistics:")
    print(f"  Location: {cache_dir}")
    print(f"  Project: {metadata.project_path}")
    print(f"  Created: {metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Last updated: {metadata.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Cached files: {len(metadata.file_metadata)}")
    print(f"  Cache size: {total_size / 1024:.2f} KB")
    if metadata.git_commit:
        print(f"  Git commit: {metadata.git_commit[:8]}")

    return 0


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI.

    Args:
        argv: Command line arguments, without the program name. Defaults to
            sys.argv[1:].
    """
    try:
        args = parse_args(argv)

        # Handle mutually exclusive verbose/quiet
        if args.verbose and args.quiet:
            print(
                "Error: --verbose and --quiet are mutually exclusive", file=sys.stderr
            )
            sys.exit(1)

        # Handle mutually exclusive no-diagrams/diagrams-only
        if args.no_diagrams and args.diagrams_only:
            print(
                "Error: --no-diagrams and --diagrams-only are mutually exclusive",
                file=sys.stderr,
            )
            sys.exit(1)

        setup_logging(verbose=args.verbose, quiet=args.quiet)

        # Get source path and cache directory
        source_path = Path(args.source).resolve()
        cache_dir = _get_cache_dir(args, source_path)

        # Handle cache-only commands
        if args.clear_cache:
            sys.exit(_handle_clear_cache(cache_dir))
        if args.cache_stats:
            sys.exit(_handle_cache_stats(cache_dir))

        # Build config objects
        cache_enabled = not args.no_cache and not args.dry_run
        cache_cfg = CacheConfig(
            enabled=cache_enabled,
            cache_dir=cache_dir if cache_enabled else None,
            force_refresh=args.force_refresh,
        )

        # Parse comma-separated sections and diagrams if provided
        def parse_csv(value: str | None) -> list[str] | None:
            return [s.strip() for s in value.split(",")] if value else None

        gen_opts = GenerationOptions(
            exclude_patterns=args.exclude,
            skip_diagrams=args.no_diagrams,
            selected_sections=parse_csv(args.sections),
            selected_diagrams=parse_csv(args.diagrams),
            template_dir=args.template_dir,
            dry_run=args.dry_run,
            max_files=args.max_files,
            diagrams_only=args.diagrams_only,
            parallel_sections=not args.no_parallel,
            enable_cost_tracking=not args.no_cost_tracking,
        )

        # Diagrams-only and dry-run modes call no models, so need no keys
        if args.dry_run or args.diagrams_only:
            llm_provider = embedding_provider = None
        else:
            anthropic_key, openai_key = get_api_keys(args.api_key_env)
            llm_provider, embedding_provider = create_default_providers(
                anthropic_key,
                openai_key,
                anthropic_model=args.anthropic_model,
                quality_mode=QualityMode(args.quality_mode),
                embedding_model=args.openai_embedding_model,
                temperature=args.temperature,
            )

        generator = CodeDocumentationGenerator(
            llm_provider,
            embedding_provider,
            generation_options=gen_opts,
            cache_config=cache_cfg,
            config=_generator_config(args),
        )

        # Generate documentation
        generator.generate_documentation(args.source, args.output)

    except (DocumentationError, ApiKeyError, CacheError, ValueError) as e:
        logger.error(f"Documentation generation failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
