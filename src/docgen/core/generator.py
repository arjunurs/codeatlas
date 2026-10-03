"""Documentation generator core functionality.

This module provides the main CodeDocumentationGenerator class that orchestrates
the entire documentation generation process.
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..cache.content_cache import SectionContentCache
from ..config import (
    DEFAULT_CONFIG,
    CacheConfig,
    GenerationOptions,
    GeneratorConfig,
)
from ..exceptions.errors import DocumentationError
from ..models.call_graph import CallGraph
from ..models.file_analysis import FileAnalysis
from ..prompts.sections import select_sections
from ..providers.base import EmbeddingProvider, LLMProvider
from ..templates.html import get_template_manager
from ..utils.cost_tracker import CostTracker
from ..utils.error_classification import describe_error
from ..utils.usage_tracking import UsageTrackingEmbeddings
from .analyzer import CodeAnalyzer
from .cross_reference import cross_reference_preprocessor
from .diagrams import DiagramGenerator, select_diagrams
from .modules import module_root, project_name
from .rag_pipeline import RAGPipelineFactory
from .renderer import DocumentationRenderer
from .section_orchestrator import SectionOrchestrator

logger = logging.getLogger(__name__)


def _report_failures(
    kind: str, errors: list[tuple[str, str]], *, total: int, required: bool
) -> DocumentationError | None:
    """Warn about the diagrams or sections that failed.

    Args:
        kind: "diagram" or "section"
        errors: (name, error description) for each one that failed
        total: How many were attempted
        required: Whether the run fails when every one of them fails

    Returns:
        The error to fail the run with when every required one failed, in
        place of the warning; otherwise None
    """
    if not errors:
        return None
    lines = "\n".join(f"  - {name}: {message}" for name, message in errors)
    if required and len(errors) == total:
        messages = {message for _, message in errors}
        if len(messages) == 1:
            return DocumentationError(f"No {kind} could be generated: {messages.pop()}")
        return DocumentationError(f"No {kind} could be generated:\n{lines}")
    logger.warning(f"{len(errors)} of {total} {kind}s failed:\n{lines}")
    return None


class CodeDocumentationGenerator:
    """Turns a Python source tree into a documentation site.

    A run analyzes the code, builds Mermaid diagrams from the analysis, writes
    each section with a RAG chain over the code, and renders the HTML. The
    providers supply the LangChain models the chain uses; diagrams-only and
    dry-run modes make no model calls and need none.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        *,
        generation_options: GenerationOptions | None = None,
        cache_config: CacheConfig | None = None,
        config: GeneratorConfig | None = None,
    ) -> None:
        """Set up a generator.

        Args:
            llm_provider: Supplies the chat model that writes the sections.
                Optional in diagrams-only and dry-run modes.
            embedding_provider: Supplies the embeddings model for retrieval.
                Optional in the same modes.
            generation_options: What to generate; by default every core
                section and diagram
            cache_config: Cache settings; caching is on by default
            config: Lower-level settings such as chunk size and retrieval

        Raises:
            ValueError: If a section or diagram name is unknown, or a provider
                is missing for a run that calls the models
        """
        options = generation_options or GenerationOptions()
        cache = cache_config or CacheConfig()
        self.config = config or DEFAULT_CONFIG

        # Reject unknown names before any work is done
        select_sections(options.selected_sections)
        self.selected_diagrams = select_diagrams(options.selected_diagrams)

        calls_models = not (options.diagrams_only or options.dry_run)
        if calls_models and (llm_provider is None or embedding_provider is None):
            raise ValueError(
                "An LLM provider and an embedding provider are required "
                "unless diagrams_only or dry_run is set"
            )
        self._llm_provider = llm_provider
        self._embedding_provider = embedding_provider

        self.exclude_patterns = options.exclude_patterns
        self.skip_diagrams = options.skip_diagrams
        self.selected_sections = options.selected_sections
        self.dry_run = options.dry_run
        self.max_files = options.max_files
        self.diagrams_only = options.diagrams_only
        self.parallel_sections = options.parallel_sections

        # Caching and cost tracking only apply to runs that call the models
        self.cache_enabled = cache.enabled and calls_models
        self.cache_dir = cache.cache_dir
        self.force_refresh = cache.force_refresh
        self.cost_tracker = (
            CostTracker() if options.enable_cost_tracking and calls_models else None
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.CHUNK_SIZE, chunk_overlap=self.config.CHUNK_OVERLAP
        )
        self.analyzer = CodeAnalyzer()
        self.diagram_generator = DiagramGenerator(
            max_nodes=self.config.MAX_DIAGRAM_NODES
        )
        self.template_manager = get_template_manager(options.template_dir)
        self._renderer = DocumentationRenderer(self.template_manager)
        self._rag_pipeline: RAGPipelineFactory | None = None
        self._section_cache: SectionContentCache | None = None
        self._current_analyses: list[FileAnalysis] | None = None

    def __enter__(self) -> CodeDocumentationGenerator:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context manager and cleanup resources.

        Returns:
            False to indicate exceptions should not be suppressed.
        """
        self.cleanup()
        return False

    def cleanup(self) -> None:
        """Clean up resources like the vector store.

        This should be called when done using the generator to free resources.
        The generator can also be used as a context manager for automatic cleanup.

        Note: When caching is enabled, the vector store is preserved on disk.
        """
        if self._rag_pipeline is not None:
            self._rag_pipeline.cleanup(preserve_cache=self.cache_enabled)
            self._rag_pipeline = None

    @property
    def llm_provider(self) -> LLMProvider | None:
        """Get the LLM provider instance."""
        return self._llm_provider

    @property
    def embedding_provider(self) -> EmbeddingProvider | None:
        """Get the embedding provider instance."""
        return self._embedding_provider

    def generate_documentation(self, directory_path: str, output_dir: str) -> None:
        """Generate comprehensive documentation for a Python codebase.

        Args:
            directory_path: Path to the directory containing Python source files
            output_dir: Directory where documentation will be generated

        Raises:
            DocumentationError: If documentation generation fails, or if no
                section (no diagram, in diagrams-only mode) could be generated;
                in that case the output is still written first
            ValueError: If directory paths are invalid
        """
        # Validate and convert paths. The source is resolved once, here, so a
        # symlink in it (as /tmp is on macOS) names files the same way in the
        # analysis and in the cache, which resolves the paths it is given
        abs_directory_path = os.path.realpath(directory_path)
        abs_output_dir = os.path.abspath(output_dir)

        if not os.path.isdir(abs_directory_path):
            raise ValueError(f"Invalid source directory: {directory_path}")

        # Setup output directories
        self._renderer.setup_output_directories(abs_output_dir)

        # Analyze codebase
        logger.debug("Analyzing Python files...")
        analyses = self.analyzer.analyze_directory(
            abs_directory_path,
            exclude_patterns=self.exclude_patterns,
            max_files=self.max_files,
        )

        if not analyses:
            raise DocumentationError("No Python files found in directory")

        logger.info(f"Analyzed {len(analyses)} Python files")

        # Store analyses for section caching
        self._current_analyses = analyses

        # Initialize section cache if enabled
        if self.cache_enabled and self.cache_dir:
            self._section_cache = SectionContentCache(Path(self.cache_dir))

        # Generate diagrams (unless skipped)
        diagrams: dict[str, str] = {}
        diagram_errors: list[tuple[str, str]] = []
        if not self.skip_diagrams:
            diagrams, diagram_errors = self._generate_all_diagrams(
                analyses, abs_directory_path
            )
            logger.info(f"Generated {len(diagrams)} diagrams")
        else:
            logger.debug("Skipping diagram generation (--no-diagrams)")

        # In diagrams-only mode, skip all section generation
        mode = None
        if self.diagrams_only:
            logger.debug(
                "Diagrams-only mode: skipping LLM calls and section generation"
            )
            mode = "Diagrams only"
            sections: list[dict[str, str]] = []
            section_errors = []
        # In dry-run mode, skip LLM calls
        elif self.dry_run:
            logger.info("Dry-run mode: skipping LLM calls")
            mode = "Dry run"
            sections = [
                {
                    "title": name,
                    "content": "*Dry-run mode: LLM content not generated*",
                }
                for name in select_sections(self.selected_sections)
            ]
            section_errors = []
        else:
            # Create vector store and RAG chain
            rag_chain = self._create_vector_store_and_rag_chain(
                analyses,
                source_dir=Path(abs_directory_path),
            )

            # Generate documentation sections (with error aggregation)
            orchestrator = self._create_section_orchestrator()
            sections, section_errors = orchestrator.generate_documentation_sections(
                rag_chain
            )

        documentation = {
            "title": project_name(abs_directory_path),
            "mode": mode,
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections": sections,
        }

        # The run fails if none of what it was asked for could be generated:
        # the sections, or the diagrams in diagrams-only mode. It fails after
        # the output is written, since the pages still show what went wrong.
        diagram_failure = _report_failures(
            "diagram",
            diagram_errors,
            total=len(diagrams) + len(diagram_errors),
            required=self.diagrams_only,
        )
        section_failure = _report_failures(
            "section",
            section_errors,
            total=len(documentation["sections"]),
            required=not self.diagrams_only,
        )
        failure = diagram_failure or section_failure

        # Create final HTML output with any generation errors
        generation_errors = {
            "diagrams": diagram_errors,
            "sections": section_errors,
        }
        self._renderer.render(
            documentation, diagrams, abs_output_dir, generation_errors
        )
        logger.info(f"Documentation written to {abs_output_dir}")

        # Save section cache
        if self._section_cache:
            self._section_cache.save_cache()

        # Print cost summary
        if self.cost_tracker:
            self.cost_tracker.finish()
            self.cost_tracker.print_summary()

        if failure:
            raise failure

    def _generate_all_diagrams(
        self, analyses: Sequence[FileAnalysis], source_dir: str
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Generate the selected diagrams, recording each failure.

        Args:
            analyses: List of file analysis results
            source_dir: The source directory; module names start from it, or
                from above it when it is a package

        Returns:
            Tuple of (diagrams dict, list of (diagram_name, error_message) pairs)
        """
        logger.debug("Generating diagrams...")
        build = self.diagram_generator
        root = module_root(source_dir)

        # The sequence and call graph diagrams share one call analysis
        @functools.cache
        def function_calls() -> CallGraph:
            return self.analyzer.analyze_function_calls(analyses, root=root)

        # Diagram type -> (output name, builder), in generation order
        builders = {
            "architecture": (
                "architecture",
                lambda: build.generate_architecture_diagram(
                    self.analyzer.analyze_module_imports(analyses, root=root)
                ),
            ),
            "class": ("class_diagram", lambda: build.generate_class_diagram(analyses)),
            "sequence": (
                "sequence",
                lambda: build.generate_sequence_diagram(function_calls()),
            ),
            "callgraph": (
                "function_calls",
                lambda: build.generate_call_graph_diagram(function_calls()),
            ),
            "dependency": (
                "package_dependencies",
                lambda: build.generate_dependency_diagram(
                    self.analyzer.analyze_package_dependencies(analyses, root=root)
                ),
            ),
        }

        diagrams: dict[str, str] = {}
        errors: list[tuple[str, str]] = []
        for diagram_type, (name, builder) in builders.items():
            if diagram_type not in self.selected_diagrams:
                continue
            try:
                diagrams[name] = builder()
            # Per-diagram boundary: a diagram that fails, for any reason, is
            # reported and left out, and the others are still generated
            except Exception as e:  # noqa: BLE001
                errors.append((name, describe_error(e)))
        return diagrams, errors

    def _create_vector_store_and_rag_chain(
        self,
        analyses: Sequence[FileAnalysis],
        source_dir: Path | None = None,
    ):
        """Create the vector store and the RAG chain over it."""
        llm_provider, embedding_provider = self._providers()
        # Route embedding calls through a wrapper that records their usage
        embeddings = embedding_provider.get_langchain_embeddings()
        if self.cost_tracker:
            embeddings = UsageTrackingEmbeddings(
                embeddings, self.cost_tracker, embedding_provider.model_name
            )
        self._rag_pipeline = RAGPipelineFactory(
            llm=llm_provider.get_langchain_llm(),
            embeddings=embeddings,
            config=self.config,
            text_splitter=self.text_splitter,
            cache_enabled=self.cache_enabled,
            cache_dir=Path(self.cache_dir) if self.cache_dir else None,
            force_refresh=self.force_refresh,
        )
        return self._rag_pipeline.create_rag_chain(analyses, source_dir=source_dir)

    def _create_section_orchestrator(self) -> SectionOrchestrator:
        """Create the orchestrator that generates the documentation sections."""
        llm_provider, _ = self._providers()
        return SectionOrchestrator(
            config=self.config,
            model_name=llm_provider.model_name,
            parallel=self.parallel_sections,
            cost_tracker=self.cost_tracker,
            section_cache=self._section_cache,
            force_refresh=self.force_refresh,
            current_analyses=self._current_analyses,
            selected_sections=self.selected_sections,
            section_preprocessors={"cross": cross_reference_preprocessor},
            convert_markdown_to_html=self._renderer.convert_markdown_to_html,
        )

    def _providers(self) -> tuple[LLMProvider, EmbeddingProvider]:
        """Return both providers; the constructor ensures them for model runs."""
        if self._llm_provider is None or self._embedding_provider is None:
            raise DocumentationError("This run needs an LLM and an embedding provider")
        return self._llm_provider, self._embedding_provider
