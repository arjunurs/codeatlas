"""Documentation generator core functionality.

This module provides the main CodeDocumentationGenerator class that orchestrates
the entire documentation generation process.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..cache.content_cache import SectionContentCache
from ..config import (
    DEFAULT_CONFIG,
    CacheConfig,
    GenerationOptions,
    GeneratorConfig,
    QualityMode,
    get_model_for_quality_mode,
)
from ..exceptions.errors import (
    ApiKeyError,
    DocumentationError,
    LLMError,
    TemplateError,
)
from ..models.file_analysis import FileAnalysis
from ..prompts.sections import select_sections
from ..providers.base import EmbeddingProvider, LLMProvider
from ..providers.registry import get_default_registry
from ..templates.html import get_template_manager
from ..utils.cost_tracker import CostTracker
from .analyzer import CodeAnalyzer
from .cross_reference import CrossReferenceAnalyzer
from .diagrams import DiagramGenerator, select_diagrams
from .rag_pipeline import RAGPipelineFactory
from .renderer import DocumentationRenderer
from .section_orchestrator import SectionOrchestrator

logger = logging.getLogger(__name__)


def _cross_reference_preprocessor(
    prompt: str, analyses: list[FileAnalysis] | None
) -> str:
    """Enhance cross-reference section prompts with pre-analyzed data."""
    if not analyses:
        return prompt
    if "reference" not in prompt.lower() and "cross" not in prompt.lower():
        return prompt

    analyzer = CrossReferenceAnalyzer(analyses)
    reference_report = analyzer.generate_reference_report(limit=15)

    return (
        f"{prompt}\n\n"
        f"## Pre-analyzed Cross-Reference Data\n\n"
        f"Use this structured analysis as the foundation for your response. "
        f"Expand on it with additional insights from the codebase context:\n\n"
        f"{reference_report}"
    )


class CodeDocumentationGenerator:
    """Generates comprehensive documentation for Python codebases using LLMs.

    This class orchestrates the documentation generation process by:
    1. Analyzing Python source code structure and relationships
    2. Generating various architectural diagrams
    3. Using LLMs to explain code patterns and architecture
    4. Creating an interactive HTML documentation

    The generated documentation includes:
    - System architecture overview
    - Package dependencies
    - Class diagrams
    - Sequence diagrams
    - Function call graphs
    - Detailed explanations of key components

    Attributes:
        llm: LangChain chat model for text generation
        embeddings: Vector embeddings for semantic search
        text_splitter: Text splitter for chunking documents
        temperature: Temperature for LLM generation
        analyzer: Code analyzer for parsing source files
        diagram_generator: Generator for Mermaid diagrams
        _rag_pipeline: RAG pipeline factory (for cleanup)
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        temperature: float | None = None,
        anthropic_model: str | None = None,
        openai_embedding_model: str | None = None,
        config: GeneratorConfig | None = None,
        *,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        exclude_patterns: list[str] | None = None,
        skip_diagrams: bool = False,
        sections: list[str] | None = None,
        diagrams: list[str] | None = None,
        template_dir: str | None = None,
        dry_run: bool = False,
        max_files: int | None = None,
        cache_enabled: bool = True,
        cache_dir: Any | None = None,
        force_refresh: bool = False,
        quality_mode: QualityMode | None = None,
        parallel_sections: bool | None = None,
        enable_cost_tracking: bool = True,
        diagrams_only: bool = False,
        retriever_k: int | None = None,
        retriever_search_type: str | None = None,
        retriever_score_threshold: float | None = None,
        retriever_fetch_k: int | None = None,
        retriever_lambda_mult: float | None = None,
    ) -> None:
        """Initialize the documentation generator.

        The generator can be initialized in two ways:
        1. Legacy mode: Pass API keys directly (anthropic_api_key, openai_api_key)
        2. Provider mode: Pass provider instances (llm_provider, embedding_provider)

        Args:
            anthropic_api_key: API key for Anthropic's Claude (legacy mode)
            openai_api_key: API key for OpenAI embeddings (legacy mode)
            temperature: Temperature for LLM generation (0.0 to 1.0)
            anthropic_model: Anthropic model name to use (overrides quality_mode)
            openai_embedding_model: OpenAI embedding model to use
            config: Custom configuration settings
            llm_provider: LLM provider instance (provider mode)
            embedding_provider: Embedding provider instance (provider mode)
            exclude_patterns: Glob patterns to exclude files/directories
            skip_diagrams: Skip diagram generation entirely
            sections: List of sections to generate (None = core sections)
            diagrams: List of diagrams to generate (None = all)
            template_dir: Custom HTML template directory
            dry_run: Analyze code without LLM calls
            max_files: Maximum number of files to analyze
            cache_enabled: Enable vector store and content caching
            cache_dir: Cache directory path (Path object or None)
            force_refresh: Force cache refresh (ignore existing cache)
            quality_mode: Quality mode preset (fast/balanced/best) that selects
                the Anthropic model when anthropic_model is not given
            parallel_sections: Enable parallel section generation
            enable_cost_tracking: Enable API cost tracking
            diagrams_only: Generate only diagrams without LLM section generation (no API costs)

        Raises:
            ValueError: If configuration is invalid
            ApiKeyError: If API keys are invalid or missing (unless diagrams_only=True)
        """
        # Use provided config or default, then apply retriever overrides
        base_config = config or DEFAULT_CONFIG

        # Apply RAG retriever overrides if any are provided
        retriever_overrides = {
            "RETRIEVER_K": retriever_k,
            "RETRIEVER_SEARCH_TYPE": retriever_search_type,
            "RETRIEVER_SCORE_THRESHOLD": retriever_score_threshold,
            "RETRIEVER_FETCH_K": retriever_fetch_k,
            "RETRIEVER_LAMBDA_MULT": retriever_lambda_mult,
        }
        has_overrides = any(v is not None for v in retriever_overrides.values())

        if has_overrides:
            # Copy base config and apply only the provided overrides
            from dataclasses import asdict

            config_dict = asdict(base_config)
            for key, value in retriever_overrides.items():
                if value is not None:
                    config_dict[key] = value
            self.config = GeneratorConfig(**config_dict)
        else:
            self.config = base_config

        # Override config values if provided
        final_temperature = (
            temperature if temperature is not None else self.config.DEFAULT_TEMPERATURE
        )
        # Model precedence: explicit model, then quality mode, then config default
        if anthropic_model:
            final_anthropic_model = anthropic_model
        elif quality_mode is not None:
            final_anthropic_model = get_model_for_quality_mode(quality_mode)
        else:
            final_anthropic_model = self.config.DEFAULT_ANTHROPIC_MODEL
        final_openai_model = (
            openai_embedding_model or self.config.DEFAULT_OPENAI_EMBEDDING_MODEL
        )

        if final_temperature is not None and not 0 <= final_temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        # Reject unknown section names before any work is done
        select_sections(sections)

        self.temperature = final_temperature

        # Name of the model that generates sections (from the provider in
        # provider mode)
        self.model_name = final_anthropic_model

        # Initialize providers
        self._llm_provider: LLMProvider | None = None
        self._embedding_provider: EmbeddingProvider | None = None

        # In diagrams-only mode, API keys are not required
        if diagrams_only:
            logger.debug("Diagrams-only mode: API keys not required")
            self.llm = None
            self.embeddings = None
        # Provider mode: use provided providers
        elif llm_provider is not None or embedding_provider is not None:
            if llm_provider is None or embedding_provider is None:
                raise ApiKeyError(
                    "Both llm_provider and embedding_provider must be provided together"
                )
            self._llm_provider = llm_provider
            self._embedding_provider = embedding_provider
            self.model_name = llm_provider.model_name
            self.llm = llm_provider.get_langchain_llm()
            self.embeddings = embedding_provider.get_langchain_embeddings()

        # Legacy mode: use API keys to create providers
        elif anthropic_api_key is not None or openai_api_key is not None:
            if not anthropic_api_key or not openai_api_key:
                raise ApiKeyError("Both Anthropic and OpenAI API keys are required")

            try:
                registry = get_default_registry()
                self._llm_provider = registry.create_llm_provider(
                    "anthropic",
                    api_key=anthropic_api_key,
                    model=final_anthropic_model,
                    temperature=final_temperature,
                )
                self._embedding_provider = registry.create_embedding_provider(
                    "openai",
                    api_key=openai_api_key,
                    model=final_openai_model,
                )
                self.llm = self._llm_provider.get_langchain_llm()
                self.embeddings = self._embedding_provider.get_langchain_embeddings()
            except Exception as e:
                raise LLMError(f"Failed to initialize LLM components: {str(e)}")
        else:
            raise ApiKeyError(
                "Either provide API keys (anthropic_api_key, openai_api_key) "
                "or provider instances (llm_provider, embedding_provider)"
            )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.CHUNK_SIZE, chunk_overlap=self.config.CHUNK_OVERLAP
        )

        # Store generation options
        self.exclude_patterns = exclude_patterns or []
        self.skip_diagrams = skip_diagrams
        self.selected_sections = sections
        self.selected_diagrams = select_diagrams(diagrams)
        self.template_dir = template_dir
        self.dry_run = dry_run
        self.max_files = max_files
        self.diagrams_only = diagrams_only

        # Cache options (disabled in dry-run and diagrams-only modes)
        self.cache_enabled = cache_enabled and not dry_run and not diagrams_only
        self.cache_dir = cache_dir
        self.force_refresh = force_refresh

        # Quality and performance options
        self.quality_mode = quality_mode or self.config.DEFAULT_QUALITY_MODE
        self.parallel_sections = (
            parallel_sections
            if parallel_sections is not None
            else self.config.PARALLEL_SECTIONS
        )

        # Cost tracking (disabled in dry-run and diagrams-only modes)
        self.enable_cost_tracking = (
            enable_cost_tracking and not dry_run and not diagrams_only
        )
        self.cost_tracker = CostTracker() if self.enable_cost_tracking else None

        # Initialize analysis components
        self.analyzer = CodeAnalyzer()
        self.diagram_generator = DiagramGenerator()
        self.template_manager = get_template_manager(template_dir)

        # Extracted collaborators
        self._renderer = DocumentationRenderer(self.template_manager)
        self._rag_pipeline: RAGPipelineFactory | None = None

        # Section content cache (initialized on first use)
        self._section_cache: SectionContentCache | None = None
        # Store analyses for section caching
        self._current_analyses: list[FileAnalysis] | None = None

    @classmethod
    def create(
        cls,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        *,
        generation_options: GenerationOptions | None = None,
        cache_config: CacheConfig | None = None,
        config: GeneratorConfig | None = None,
    ) -> CodeDocumentationGenerator:
        """Create a generator from provider instances and config objects.

        This is the preferred way to construct a generator. The legacy
        ``__init__`` with raw API keys is retained for backward compatibility.

        Args:
            llm_provider: LLM provider instance
            embedding_provider: Embedding provider instance
            generation_options: Options controlling output
            cache_config: Cache settings
            config: Low-level generator config

        Returns:
            Configured CodeDocumentationGenerator instance
        """
        opts = generation_options or GenerationOptions()
        cache = cache_config or CacheConfig()

        return cls(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            config=config,
            exclude_patterns=opts.exclude_patterns,
            skip_diagrams=opts.skip_diagrams,
            sections=opts.selected_sections,
            diagrams=opts.selected_diagrams,
            template_dir=opts.template_dir,
            dry_run=opts.dry_run,
            max_files=opts.max_files,
            diagrams_only=opts.diagrams_only,
            parallel_sections=opts.parallel_sections,
            enable_cost_tracking=opts.enable_cost_tracking,
            quality_mode=opts.quality_mode,
            cache_enabled=cache.enabled,
            cache_dir=cache.cache_dir,
            force_refresh=cache.force_refresh,
        )

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
        # Backward compat: also clean up vector store if set directly via tests
        direct_store = getattr(self, "_direct_vector_store", None)
        if direct_store is not None:
            try:
                if not self.cache_enabled:
                    direct_store.delete_collection()
            except Exception as e:
                logger.warning(f"Error cleaning up vector store: {str(e)}")
            finally:
                self._direct_vector_store = None

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
            DocumentationError: If documentation generation fails
            ValueError: If directory paths are invalid
        """
        # Validate and convert paths
        abs_directory_path = os.path.abspath(directory_path)
        abs_output_dir = os.path.abspath(output_dir)

        if not os.path.isdir(abs_directory_path):
            raise ValueError(f"Invalid source directory: {directory_path}")

        try:
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
                logger.error("No Python files found in directory")
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
                diagrams, diagram_errors = self._generate_all_diagrams(analyses)
                logger.info(f"Generated {len(diagrams)} diagrams")
                if diagram_errors:
                    logger.warning(
                        f"{len(diagram_errors)} diagram(s) failed:\n"
                        + "\n".join(
                            f"  - {name}: {error}" for name, error in diagram_errors
                        )
                    )
            else:
                logger.debug("Skipping diagram generation (--no-diagrams)")

            # In diagrams-only mode, skip all section generation
            if self.diagrams_only:
                logger.debug(
                    "Diagrams-only mode: skipping LLM calls and section generation"
                )
                documentation = {
                    "title": "Code Documentation (Diagrams Only)",
                    "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sections": [],
                }
                section_errors = []
            # In dry-run mode, skip LLM calls
            elif self.dry_run:
                logger.info("Dry-run mode: skipping LLM calls")
                documentation = {
                    "title": "Code Documentation (Dry Run)",
                    "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sections": [
                        {
                            "title": name,
                            "content": "*Dry-run mode: LLM content not generated*",
                        }
                        for name in select_sections(self.selected_sections)
                    ],
                }
                section_errors = []
            else:
                # Create vector store and RAG chain
                rag_chain = self._create_vector_store_and_rag_chain(
                    analyses,
                    source_dir=Path(abs_directory_path),
                )

                # Generate documentation sections (with error aggregation)
                documentation, section_errors = self._generate_documentation_sections(
                    rag_chain
                )

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

        except DocumentationError:
            raise
        except Exception as e:
            logger.error(f"Error generating documentation: {str(e)}")
            raise DocumentationError(f"Failed to generate documentation: {str(e)}")

    def _generate_all_diagrams(
        self, analyses: Sequence[FileAnalysis]
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Generate all documentation diagrams.

        Args:
            analyses: List of file analysis results

        Returns:
            Tuple of (diagrams dict, list of (diagram_name, error_message) pairs)
        """
        logger.debug("Generating diagrams...")
        diagrams: dict[str, str] = {}
        errors: list[tuple[str, str]] = []

        def should_generate(diagram_key: str) -> bool:
            return diagram_key in self.selected_diagrams

        if should_generate("architecture"):
            try:
                diagrams["architecture"] = (
                    self.diagram_generator.generate_architecture_diagram(analyses)
                )
            except Exception as e:
                errors.append(("architecture", str(e)))

        if should_generate("class"):
            try:
                diagrams["class_diagram"] = (
                    self.diagram_generator.generate_class_diagram(analyses)
                )
            except Exception as e:
                errors.append(("class_diagram", str(e)))

        need_function_analysis = should_generate("sequence") or should_generate(
            "callgraph"
        )
        if need_function_analysis:
            try:
                function_calls = self.analyzer.analyze_function_calls(analyses)
                if should_generate("sequence"):
                    try:
                        diagrams["sequence"] = (
                            self.diagram_generator.generate_sequence_diagram(
                                function_calls
                            )
                        )
                    except Exception as e:
                        errors.append(("sequence", str(e)))
                if should_generate("callgraph"):
                    try:
                        diagrams["function_calls"] = (
                            self.diagram_generator.generate_call_graph_diagram(
                                function_calls
                            )
                        )
                    except Exception as e:
                        errors.append(("function_calls", str(e)))
            except Exception as e:
                errors.append(("function_analysis", str(e)))

        if should_generate("dependency"):
            try:
                package_deps = self.analyzer.analyze_package_dependencies()
                diagrams["package_dependencies"] = (
                    self.diagram_generator.generate_dependency_diagram(package_deps)
                )
            except Exception as e:
                errors.append(("package_dependencies", str(e)))

        return diagrams, errors

    # ---- Backward-compatible delegating methods ----
    # These allow existing tests that patch or call these methods directly
    # to continue working. New code should use the extracted classes.

    def _setup_output_directories(self, output_dir: str) -> None:
        """Create the output directory structure (delegates to renderer)."""
        self._renderer.setup_output_directories(output_dir)

    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert markdown content to HTML (delegates to renderer)."""
        return self._renderer.convert_markdown_to_html(content)

    def _generate_navigation(
        self, active_page: str, sections: list[dict[str, str]], base_url: str
    ) -> str:
        """Generate navigation HTML (delegates to renderer)."""
        return self._renderer.generate_navigation(active_page, sections, base_url)

    # Keep as property for test compatibility
    @property
    def _vector_store(self):
        """Get the underlying vector store (for backward compat)."""
        if self._rag_pipeline is not None:
            return self._rag_pipeline.vector_store
        return getattr(self, "_direct_vector_store", None)

    @_vector_store.setter
    def _vector_store(self, value):
        """Set the vector store directly (for backward compat / tests)."""
        self._direct_vector_store = value

    def _generate_html_documentation(
        self,
        documentation: dict[str, Any],
        diagrams: dict[str, str],
        output_dir: str,
        generation_errors: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        """Generate HTML documentation (delegates to renderer)."""
        self._renderer.render(documentation, diagrams, output_dir, generation_errors)

    def _create_vector_store_and_rag_chain(
        self,
        analyses: Sequence[FileAnalysis],
        source_dir: Path | None = None,
    ):
        """Create vector store and RAG chain (delegates to RAGPipelineFactory)."""
        self._rag_pipeline = RAGPipelineFactory(
            llm=self.llm,
            embeddings=self.embeddings,
            config=self.config,
            text_splitter=self.text_splitter,
            cache_enabled=self.cache_enabled,
            cache_dir=Path(self.cache_dir) if self.cache_dir else None,
            force_refresh=self.force_refresh,
        )
        return self._rag_pipeline.create_rag_chain(analyses, source_dir=source_dir)

    def _create_documents(self, analyses: Sequence[FileAnalysis]):
        """Create LangChain documents (delegates to rag_pipeline module)."""
        from .rag_pipeline import create_documents

        return create_documents(analyses)

    def _format_entity_document(self, entity) -> str:
        """Format a code entity as a document string (delegates to rag_pipeline module)."""
        from .rag_pipeline import format_entity_document

        return format_entity_document(entity)

    def _generate_documentation_sections(self, rag_chain):
        """Generate all documentation sections (delegates to SectionOrchestrator)."""
        orchestrator = SectionOrchestrator(
            config=self.config,
            model_name=self.model_name,
            parallel=self.parallel_sections,
            cost_tracker=self.cost_tracker,
            section_cache=self._section_cache,
            current_analyses=self._current_analyses,
            selected_sections=self.selected_sections,
            section_preprocessors={
                "cross": _cross_reference_preprocessor,
            },
            convert_markdown_to_html=self._renderer.convert_markdown_to_html,
        )
        return orchestrator.generate_documentation_sections(rag_chain)

    def _generate_section_with_cache(self, rag_chain, section_name: str) -> str:
        """Generate a section with caching support (delegates to SectionOrchestrator)."""
        orchestrator = SectionOrchestrator(
            config=self.config,
            model_name=self.model_name,
            parallel=self.parallel_sections,
            cost_tracker=self.cost_tracker,
            section_cache=self._section_cache,
            current_analyses=self._current_analyses,
            selected_sections=self.selected_sections,
            section_preprocessors={
                "cross": _cross_reference_preprocessor,
            },
            convert_markdown_to_html=self._renderer.convert_markdown_to_html,
        )
        return orchestrator._generate_section_with_cache(rag_chain, section_name)

    def _generate_section(self, rag_chain, section_name: str) -> str:
        """Generate a section (delegates to SectionOrchestrator)."""
        orchestrator = SectionOrchestrator(
            config=self.config,
            model_name=self.model_name,
            parallel=self.parallel_sections,
            cost_tracker=self.cost_tracker,
            section_cache=self._section_cache,
            current_analyses=self._current_analyses,
            selected_sections=self.selected_sections,
            section_preprocessors={
                "cross": _cross_reference_preprocessor,
            },
            convert_markdown_to_html=self._renderer.convert_markdown_to_html,
        )
        return orchestrator._generate_section(rag_chain, section_name)

    def _create_final_html_output(
        self,
        documentation: dict[str, Any],
        diagrams: dict[str, str],
        output_dir: str,
        generation_errors: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        """Generate final HTML output (delegates to renderer)."""
        logger.debug("Generating HTML documentation...")
        try:
            self._renderer.render(
                documentation, diagrams, output_dir, generation_errors
            )
        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise TemplateError(f"Failed to generate HTML documentation: {str(e)}")
