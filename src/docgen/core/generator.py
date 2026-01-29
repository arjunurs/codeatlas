"""Documentation generator core functionality.

This module provides the main CodeDocumentationGenerator class that orchestrates
the entire documentation generation process.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..cache.content_cache import SectionContentCache
from ..cache.vector_cache import VectorStoreCache
from ..config import (
    DEFAULT_CONFIG,
    GeneratorConfig,
    QualityMode,
    get_model_for_quality_mode,
)
from ..exceptions.errors import (
    ApiKeyError,
    DocumentationError,
    LLMError,
    TemplateError,
    VectorStoreError,
)
from ..models.file_analysis import FileAnalysis
from ..prompts.sections import (
    SECTION_ORDER,
    get_all_available_sections,
    get_section_prompt,
)
from ..providers.anthropic import AnthropicProvider
from ..providers.base import EmbeddingProvider, LLMProvider
from ..providers.openai import OpenAIEmbeddingProvider
from ..templates.html import get_template_manager
from ..utils.cost_tracker import CostTracker
from .analyzer import CodeAnalyzer
from .diagrams import DiagramGenerator

logger = logging.getLogger(__name__)


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
        _vector_store: The Chroma vector store (for cleanup)
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
            anthropic_model: Anthropic model name to use
            openai_embedding_model: OpenAI embedding model to use
            config: Custom configuration settings
            llm_provider: LLM provider instance (provider mode)
            embedding_provider: Embedding provider instance (provider mode)
            exclude_patterns: Glob patterns to exclude files/directories
            skip_diagrams: Skip diagram generation entirely
            sections: List of sections to generate (None = all)
            diagrams: List of diagrams to generate (None = all)
            template_dir: Custom HTML template directory
            dry_run: Analyze code without LLM calls
            max_files: Maximum number of files to analyze
            cache_enabled: Enable vector store and content caching
            cache_dir: Cache directory path (Path object or None)
            force_refresh: Force cache refresh (ignore existing cache)
            quality_mode: Quality mode preset (fast/balanced/best)
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
        final_anthropic_model = anthropic_model or self.config.DEFAULT_ANTHROPIC_MODEL
        final_openai_model = (
            openai_embedding_model or self.config.DEFAULT_OPENAI_EMBEDDING_MODEL
        )

        if not 0 <= final_temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        self.temperature = final_temperature

        # Initialize providers
        self._llm_provider: LLMProvider | None = None
        self._embedding_provider: EmbeddingProvider | None = None
        self._vector_store: Chroma | None = None

        # In diagrams-only mode, API keys are not required
        if diagrams_only:
            logger.info("Diagrams-only mode: API keys not required")
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
            self.llm = llm_provider.get_langchain_llm()
            self.embeddings = embedding_provider.get_langchain_embeddings()

        # Legacy mode: use API keys to create providers
        elif anthropic_api_key is not None or openai_api_key is not None:
            if not anthropic_api_key or not openai_api_key:
                raise ApiKeyError("Both Anthropic and OpenAI API keys are required")

            try:
                self._llm_provider = AnthropicProvider(
                    api_key=anthropic_api_key,
                    model=final_anthropic_model,
                    temperature=final_temperature,
                )
                self._embedding_provider = OpenAIEmbeddingProvider(
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
        self.selected_diagrams = diagrams
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

        # Section content cache (initialized on first use)
        self._section_cache: SectionContentCache | None = None
        # Store analyses for section caching
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
        if self._vector_store is not None:
            try:
                if not self.cache_enabled:
                    # Only delete collection if caching is disabled
                    self._vector_store.delete_collection()
                # Note: When caching is enabled, we preserve the vector store on disk
            except Exception as e:
                logger.warning(f"Error cleaning up vector store: {str(e)}")
            finally:
                self._vector_store = None

    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert markdown content to HTML.

        Args:
            content: Markdown-formatted text content

        Returns:
            HTML-formatted content
        """
        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        return md.convert(content)

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
            self._setup_output_directories(abs_output_dir)

            # Analyze codebase
            logger.info("Analyzing Python files...")
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
            else:
                logger.info("Skipping diagram generation (--no-diagrams)")

            # In diagrams-only mode, skip all section generation
            if self.diagrams_only:
                logger.info(
                    "Diagrams-only mode: skipping LLM calls and section generation"
                )
                documentation = {
                    "title": "Code Documentation (Diagrams Only)",
                    "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sections": [],  # No sections in diagrams-only mode
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
                        for name in (self.selected_sections or SECTION_ORDER)
                        if name in SECTION_ORDER
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
            self._create_final_html_output(
                documentation, diagrams, abs_output_dir, generation_errors
            )
            logger.info(f"Documentation generated successfully in {abs_output_dir}")

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

    def _setup_output_directories(self, output_dir: str) -> None:
        """Create the output directory structure.

        Args:
            output_dir: Base output directory path
        """
        for subdir in ["", "sections", "diagrams", "assets"]:
            os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    def _create_vector_store_and_rag_chain(
        self,
        analyses: Sequence[FileAnalysis],
        source_dir: Path | None = None,
    ) -> Runnable:
        """Create vector store and RAG chain from analyses using LCEL.

        Args:
            analyses: List of file analysis results
            source_dir: Source directory path (for caching)

        Returns:
            LCEL RAG chain for documentation generation

        Raises:
            VectorStoreError: If vector store creation fails
        """
        try:
            # Create documents for vector store
            logger.info("Creating vector store...")
            documents = self._create_documents(analyses)

            if not documents:
                logger.error("No documentation content could be generated")
                raise DocumentationError("No documentation content could be generated")

            # Split documents
            texts = self.text_splitter.split_documents(documents)

            # Create or load vector store (with caching if enabled)
            if self.cache_enabled and self.cache_dir and source_dir:
                logger.info("Cache enabled: using persistent vector store")

                # Get list of current Python files for change detection
                current_files = [
                    Path(source_dir) / analysis.file_path for analysis in analyses
                ]

                # Use vector store cache
                cache = VectorStoreCache(
                    cache_dir=Path(self.cache_dir),
                    source_dir=Path(source_dir),
                    embeddings=self.embeddings,
                    force_refresh=self.force_refresh,
                )

                self._vector_store = cache.get_or_create_vector_store(
                    analyses=analyses,
                    documents=texts,
                    current_files=current_files,
                )
            else:
                # No caching - create ephemeral vector store
                logger.info("Cache disabled: creating ephemeral vector store")
                self._vector_store = Chroma.from_documents(texts, self.embeddings)

            # Create retriever with configurable search parameters
            if self.config.RETRIEVER_SEARCH_TYPE == "mmr":
                retriever = self._vector_store.as_retriever(
                    search_type="mmr",
                    search_kwargs={
                        "k": self.config.RETRIEVER_K,
                        "fetch_k": self.config.RETRIEVER_FETCH_K,
                        "lambda_mult": self.config.RETRIEVER_LAMBDA_MULT,
                    },
                )
                logger.info(
                    f"Using MMR retriever: k={self.config.RETRIEVER_K}, "
                    f"fetch_k={self.config.RETRIEVER_FETCH_K}, "
                    f"lambda_mult={self.config.RETRIEVER_LAMBDA_MULT}"
                )
            elif self.config.RETRIEVER_SCORE_THRESHOLD:
                retriever = self._vector_store.as_retriever(
                    search_type="similarity_score_threshold",
                    search_kwargs={
                        "score_threshold": self.config.RETRIEVER_SCORE_THRESHOLD,
                        "k": self.config.RETRIEVER_K,
                    },
                )
                logger.info(
                    f"Using similarity threshold retriever: k={self.config.RETRIEVER_K}, "
                    f"threshold={self.config.RETRIEVER_SCORE_THRESHOLD}"
                )
            else:
                retriever = self._vector_store.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": self.config.RETRIEVER_K},
                )
                logger.info(f"Using similarity retriever: k={self.config.RETRIEVER_K}")

            # Create RAG prompt template
            rag_prompt = ChatPromptTemplate.from_template(
                """You are a senior software architect and technical writer analyzing a Python codebase.

Your task: Create clear, accurate, and actionable documentation from the provided code context.

## Guidelines:
1. **Be Specific**: Reference actual code with proper formatting (`ClassName`, `method_name()`, `module.function()`)
2. **Be Accurate**: Only describe what you can verify from the context - avoid speculation
3. **Explain WHY**: Don't just describe WHAT the code does - explain the reasoning, design decisions, and trade-offs
4. **Use Examples**: Include concrete usage examples and patterns from the actual codebase
5. **Admit Gaps**: If the context is insufficient to answer fully, clearly state what information is missing

## Format Requirements:
- Use Markdown with ## for main sections, ### for subsections
- Wrap all code elements in `backticks` (classes, methods, variables, file paths)
- Use ```python for code blocks with proper indentation
- Add blank lines between sections and list items for readability
- Use tables for structured comparisons when appropriate

Context:
{context}

Question: {question}

Answer:"""
            )

            # Helper function to format retrieved documents
            def format_docs(docs):
                return "\n\n---\n\n".join(doc.page_content for doc in docs)

            # Build LCEL RAG chain
            rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | rag_prompt
                | self.llm
                | StrOutputParser()
            )

            return rag_chain
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise VectorStoreError(f"Failed to create vector store: {str(e)}")

    def _generate_all_diagrams(
        self, analyses: Sequence[FileAnalysis]
    ) -> tuple[dict[str, str], list[tuple[str, str]]]:
        """Generate all documentation diagrams.

        Args:
            analyses: List of file analysis results

        Returns:
            Tuple of (diagrams dict, list of (diagram_name, error_message) pairs)
        """
        logger.info("Generating diagrams...")
        diagrams: dict[str, str] = {}
        errors: list[tuple[str, str]] = []

        def should_generate(diagram_key: str) -> bool:
            """Check if a diagram should be generated based on selection."""
            if not self.selected_diagrams:
                return True
            return diagram_key in self.selected_diagrams

        # Generate architecture diagram
        if should_generate("architecture"):
            try:
                diagrams["architecture"] = (
                    self.diagram_generator.generate_architecture_diagram(analyses)
                )
            except Exception as e:
                errors.append(("architecture", str(e)))

        # Generate class diagram
        if should_generate("class"):
            try:
                diagrams["class_diagram"] = (
                    self.diagram_generator.generate_class_diagram(analyses)
                )
            except Exception as e:
                errors.append(("class_diagram", str(e)))

        # Generate function-related diagrams
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

        # Generate dependency diagram
        if should_generate("dependency"):
            try:
                package_deps = self.analyzer.analyze_package_dependencies()
                diagrams["package_dependencies"] = (
                    self.diagram_generator.generate_dependency_diagram(package_deps)
                )
            except Exception as e:
                errors.append(("package_dependencies", str(e)))

        return diagrams, errors

    def _generate_section_with_cache(
        self,
        rag_chain: Runnable,
        section_name: str,
    ) -> str:
        """Generate a section with caching support.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_name: Name of the section to generate

        Returns:
            Section content (markdown)
        """
        # Try to get from cache
        if self._section_cache and self._current_analyses:
            cached_content = self._section_cache.get_cached_section(
                section_name, self._current_analyses
            )
            if cached_content is not None:
                if self.cost_tracker:
                    # Record as cached request (no API call)
                    model_name = get_model_for_quality_mode(
                        self.quality_mode, "general"
                    )
                    self.cost_tracker.record_llm_usage(
                        model=model_name,
                        input_tokens=0,
                        output_tokens=0,
                        cached=True,
                    )
                return cached_content

        # Generate new content
        content = self._generate_section(rag_chain, section_name)

        # Cache the generated content
        if self._section_cache and self._current_analyses:
            self._section_cache.cache_section(
                section_name, content, self._current_analyses
            )

        return content

    def _generate_documentation_sections(self, rag_chain: Runnable) -> dict[str, Any]:
        """Generate all documentation sections using the RAG chain.

        Args:
            rag_chain: LCEL RAG chain for content generation

        Returns:
            Tuple of (documentation dict, list of (section_name, error) pairs)
        """
        logger.info("Generating documentation content...")

        # Filter sections if specific ones are selected
        # When user specifies sections, they can choose from all available sections (core + optional)
        # When no sections specified, use only core sections (SECTION_ORDER)
        if self.selected_sections:
            all_sections = get_all_available_sections()
            sections_to_generate = self._filter_sections(all_sections)
        else:
            sections_to_generate = SECTION_ORDER
        if self.selected_sections:
            logger.info(f"Generating selected sections: {sections_to_generate}")

        # Generate sections (with optional parallelization)
        if self.parallel_sections and len(sections_to_generate) > 1:
            sections, errors = self._generate_sections_parallel(
                rag_chain, sections_to_generate
            )
        else:
            sections, errors = self._generate_sections_sequential(
                rag_chain, sections_to_generate
            )

        if errors:
            logger.warning(
                f"Some sections failed to generate ({len(errors)} errors):\n"
                + "\n".join(f"  - {name}: {error}" for name, error in errors)
            )

        documentation = {
            "title": "Code Documentation",
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections": sections,
        }

        return documentation, errors

    def _generate_sections_sequential(
        self,
        rag_chain: Runnable,
        section_names: list[str],
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        """Generate sections sequentially.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_names: List of section names to generate

        Returns:
            Tuple of (sections list, errors list)
        """
        sections = []
        errors: list[tuple[str, str]] = []

        for section_name in section_names:
            logger.info(f"Generating section: {section_name}")
            try:
                content = self._generate_section_with_cache(rag_chain, section_name)
                html_content = self._convert_markdown_to_html(content)
                sections.append({"title": section_name, "content": html_content})
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Failed to generate section '{section_name}': {error_msg}"
                )
                errors.append((section_name, error_msg))
                sections.append(
                    {
                        "title": section_name,
                        "content": f"*Error generating this section: {error_msg}*",
                    }
                )

        return sections, errors

    def _generate_sections_parallel(
        self,
        rag_chain: Runnable,
        section_names: list[str],
    ) -> tuple[list[dict], list[tuple[str, str]]]:
        """Generate sections in parallel.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_names: List of section names to generate

        Returns:
            Tuple of (sections list, errors list)
        """
        logger.info(f"Generating {len(section_names)} sections in parallel")

        sections_dict = {}
        errors: list[tuple[str, str]] = []

        max_workers = min(len(section_names), self.config.MAX_PARALLEL_WORKERS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all section generation tasks
            future_to_section = {
                executor.submit(
                    self._generate_section_with_cache, rag_chain, section_name
                ): section_name
                for section_name in section_names
            }

            # Collect results as they complete
            for future in as_completed(future_to_section):
                section_name = future_to_section[future]
                try:
                    content = future.result()
                    html_content = self._convert_markdown_to_html(content)
                    sections_dict[section_name] = {
                        "title": section_name,
                        "content": html_content,
                    }
                    logger.info(f"Completed section: {section_name}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        f"Failed to generate section '{section_name}': {error_msg}"
                    )
                    errors.append((section_name, error_msg))
                    sections_dict[section_name] = {
                        "title": section_name,
                        "content": f"*Error generating this section: {error_msg}*",
                    }

        # Return sections in original order
        sections = [sections_dict[name] for name in section_names]
        return sections, errors

    def _generate_section(self, rag_chain: Runnable, section_name: str) -> str:
        """Generate content for a documentation section.

        Args:
            rag_chain: LCEL RAG chain for content generation
            section_name: Name of the section to generate

        Returns:
            Generated section content as a string

        Raises:
            LLMError: If section generation fails
        """
        try:
            prompt = get_section_prompt(section_name)

            # Special handling for Cross-Reference Documentation
            if "cross" in section_name.lower() and "reference" in section_name.lower():
                if self._current_analyses:
                    # Import here to avoid circular dependency
                    from .cross_reference import CrossReferenceAnalyzer

                    # Generate structured cross-reference data
                    analyzer = CrossReferenceAnalyzer(self._current_analyses)
                    reference_report = analyzer.generate_reference_report(limit=15)

                    # Enhance prompt with structured data
                    prompt = (
                        f"{prompt}\n\n"
                        f"## Pre-analyzed Cross-Reference Data\n\n"
                        f"Use this structured analysis as the foundation for your response. "
                        f"Expand on it with additional insights from the codebase context:\n\n"
                        f"{reference_report}"
                    )

            return rag_chain.invoke(prompt)
        except Exception as e:
            raise LLMError(
                f"Failed to generate section '{section_name}': {str(e)}"
            ) from e

    def _filter_sections(self, available_sections: list[str]) -> list[str]:
        """Filter sections based on user selection.

        Args:
            available_sections: List of all available section names

        Returns:
            List of sections to generate (all if no selection, filtered otherwise)
        """
        if not self.selected_sections:
            return available_sections

        selected_lower = [sel.lower() for sel in self.selected_sections]

        def matches_selection(section: str) -> bool:
            """Check if section matches any user selection."""
            # Normalize both the section name and user inputs
            normalized = section.lower().replace(" ", "_").replace("_and_", "_")
            section_lower = section.lower()

            for sel in selected_lower:
                # Normalize user selection the same way (remove all special chars)
                sel_normalized = sel.replace("_", "").replace("-", "")
                section_normalized = normalized.replace("_", "").replace("-", "")

                # Check various matching strategies
                if (
                    section in self.selected_sections
                    or section_lower == sel
                    or normalized == sel
                    or sel_normalized == section_normalized
                    or section_lower.startswith(sel)
                    or sel in section_lower
                    or section_normalized.startswith(
                        sel_normalized
                    )  # prefix match on normalized
                    or sel_normalized in section_normalized
                ):  # user input contained in section
                    return True

            return False

        return [s for s in available_sections if matches_selection(s)]

    def _create_final_html_output(
        self,
        documentation: dict[str, Any],
        diagrams: dict[str, str],
        output_dir: str,
        generation_errors: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        """Generate final HTML documentation output.

        Args:
            documentation: Dictionary containing documentation content
            diagrams: Dictionary containing Mermaid diagram codes
            output_dir: Directory where HTML files will be generated
            generation_errors: Optional dict with 'diagrams' and 'sections' error lists
        """
        logger.info("Generating HTML documentation...")
        try:
            self._generate_html_documentation(
                documentation, diagrams, output_dir, generation_errors
            )
        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise TemplateError(f"Failed to generate HTML documentation: {str(e)}")

    def _create_documents(self, analyses: Sequence[FileAnalysis]) -> list[Document]:
        """Create LangChain documents from file analyses.

        Args:
            analyses: List of file analysis results

        Returns:
            List of LangChain documents for vector store
        """
        documents: list[Document] = []

        for analysis in analyses:
            # Add file content
            documents.append(
                Document(
                    page_content=analysis.content,
                    metadata={"source": analysis.file_path},
                )
            )

            # Add entity information
            for entity in analysis.entities:
                doc = self._format_entity_document(entity)
                documents.append(
                    Document(page_content=doc, metadata={"source": analysis.file_path})
                )

        return documents

    def _format_entity_document(self, entity) -> str:
        """Format a code entity as a document string.

        Args:
            entity: CodeEntity to format

        Returns:
            Formatted document string
        """
        lines = [f"Type: {entity.type}", f"Name: {entity.name}"]

        if entity.docstring:
            lines.append(f"Description: {entity.docstring}")

        if entity.type == "class":
            methods = ", ".join(entity.methods) if entity.methods else "None"
            lines.append(f"Methods: {methods}")
            if entity.parent_class:
                lines.append(f"Inherits from: {entity.parent_class}")

        return "\n".join(lines) + "\n"

    def _generate_html_documentation(
        self,
        documentation: dict[str, Any],
        diagrams: dict[str, str],
        output_dir: str,
        generation_errors: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        """Generate HTML documentation with embedded diagrams.

        Args:
            documentation: Dictionary containing documentation content
            diagrams: Dictionary containing Mermaid diagram codes
            output_dir: Directory where HTML files will be generated
            generation_errors: Optional dict with 'diagrams' and 'sections' error lists

        Raises:
            DocumentationError: If HTML generation fails
        """
        try:
            # Prepare error summary for display
            errors = generation_errors or {"diagrams": [], "sections": []}
            has_errors = bool(errors.get("diagrams") or errors.get("sections"))

            # Generate index page
            index_context = {
                "title": documentation["title"],
                "documentation": documentation,
                "base_url": "./",  # Current directory for index page
                "navigation": self._generate_navigation(
                    "index", documentation["sections"], "./"
                ),
                "generation_errors": errors if has_errors else None,
            }
            self.template_manager.render_template(
                "index", index_context, output_dir, "index.html"
            )

            # Generate section pages
            sections_list = documentation["sections"]
            for i, section in enumerate(sections_list):
                filename = f"sections/{section['title'].lower().replace(' ', '_')}.html"

                # Determine prev/next sections for navigation
                prev_section = sections_list[i - 1]["title"] if i > 0 else None
                next_section = (
                    sections_list[i + 1]["title"]
                    if i < len(sections_list) - 1
                    else None
                )

                section_context = {
                    "title": section["title"],
                    "section": section,
                    "base_url": "../",  # Parent directory for section pages
                    "navigation": self._generate_navigation(
                        section["title"], sections_list, "../"
                    ),
                    "prev_section": prev_section,
                    "next_section": next_section,
                }
                self.template_manager.render_template(
                    "section", section_context, output_dir, filename
                )

            # Generate diagram pages
            diagram_files = {
                "architecture": diagrams.get("architecture", ""),
                "dependencies": diagrams.get("package_dependencies", ""),
                "classes": diagrams.get("class_diagram", ""),
                "sequence": diagrams.get("sequence", ""),
                "call_graph": diagrams.get("function_calls", ""),
            }

            for name, diagram in diagram_files.items():
                if diagram:
                    filename = f"diagrams/{name}.html"
                    diagram_context = {
                        "title": f"{name.replace('_', ' ').title()} Diagram",
                        "diagram_code": diagram,
                        "base_url": "../",  # Parent directory for diagram pages
                        "navigation": self._generate_navigation(
                            "diagrams", documentation["sections"], "../"
                        ),
                    }
                    self.template_manager.render_template(
                        "diagrams", diagram_context, output_dir, filename
                    )

            # Generate search page
            search_context = {
                "title": "Search Documentation",
                "base_url": "./",  # Current directory for search page
                "navigation": self._generate_navigation(
                    "search", documentation["sections"], "./"
                ),
            }
            self.template_manager.render_template(
                "search", search_context, output_dir, "search.html"
            )

        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise DocumentationError(f"Failed to generate HTML documentation: {str(e)}")

    def _generate_navigation(
        self, active_page: str, sections: list[dict[str, str]], base_url: str
    ) -> str:
        """Generate navigation HTML for the current page.

        Args:
            active_page: Currently active page
            sections: List of documentation sections
            base_url: Base URL for relative paths

        Returns:
            Navigation HTML content
        """
        return self.template_manager.templates["navigation"].render(
            active=active_page,
            sections=[s["title"] for s in sections],
            base_url=base_url,
        )
