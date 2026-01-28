"""Documentation generator core functionality.

This module provides the main CodeDocumentationGenerator class that orchestrates
the entire documentation generation process.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Sequence, Union
import logging

from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, Runnable
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from .analyzer import CodeAnalyzer
from .diagrams import DiagramGenerator
from ..config import GeneratorConfig, DEFAULT_CONFIG
from ..models.file_analysis import FileAnalysis
from ..templates.html import get_template_manager
from ..providers.base import LLMProvider, EmbeddingProvider
from ..providers.anthropic import AnthropicProvider
from ..providers.openai import OpenAIEmbeddingProvider
from ..prompts.sections import SECTION_ORDER, get_section_prompt
from ..exceptions.errors import (
    DocumentationError,
    ApiKeyError,
    VectorStoreError,
    LLMError,
    TemplateError
)

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
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        anthropic_model: Optional[str] = None,
        openai_embedding_model: Optional[str] = None,
        config: Optional[GeneratorConfig] = None,
        *,
        llm_provider: Optional[LLMProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
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

        Raises:
            ValueError: If configuration is invalid
            ApiKeyError: If API keys are invalid or missing
        """
        # Use provided config or default
        self.config = config or DEFAULT_CONFIG

        # Override config values if provided
        final_temperature = temperature if temperature is not None else self.config.DEFAULT_TEMPERATURE
        final_anthropic_model = anthropic_model or self.config.DEFAULT_ANTHROPIC_MODEL
        final_openai_model = openai_embedding_model or self.config.DEFAULT_OPENAI_EMBEDDING_MODEL

        if not 0 <= final_temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        self.temperature = final_temperature

        # Initialize providers
        self._llm_provider: Optional[LLMProvider] = None
        self._embedding_provider: Optional[EmbeddingProvider] = None
        self._vector_store: Optional[Chroma] = None

        # Provider mode: use provided providers
        if llm_provider is not None or embedding_provider is not None:
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
            chunk_size=self.config.CHUNK_SIZE,
            chunk_overlap=self.config.CHUNK_OVERLAP
        )

        # Initialize analysis components
        self.analyzer = CodeAnalyzer()
        self.diagram_generator = DiagramGenerator()
        self.template_manager = get_template_manager()

    def __enter__(self) -> "CodeDocumentationGenerator":
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
        """
        if self._vector_store is not None:
            try:
                # Chroma doesn't have a close method, but we can delete the collection
                self._vector_store.delete_collection()
            except Exception as e:
                logger.warning(f"Error cleaning up vector store: {str(e)}")
            finally:
                self._vector_store = None

    @property
    def llm_provider(self) -> Optional[LLMProvider]:
        """Get the LLM provider instance."""
        return self._llm_provider

    @property
    def embedding_provider(self) -> Optional[EmbeddingProvider]:
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
            analyses = self.analyzer.analyze_directory(abs_directory_path)

            if not analyses:
                logger.error("No Python files found in directory")
                raise DocumentationError("No Python files found in directory")

            # Create vector store and RAG chain
            rag_chain = self._create_vector_store_and_rag_chain(analyses)

            # Generate all diagrams (with error aggregation)
            diagrams, diagram_errors = self._generate_all_diagrams(analyses)

            # Generate documentation sections (with error aggregation)
            documentation, section_errors = self._generate_documentation_sections(rag_chain)

            # Create final HTML output with any generation errors
            generation_errors = {
                'diagrams': diagram_errors,
                'sections': section_errors,
            }
            self._create_final_html_output(documentation, diagrams, abs_output_dir, generation_errors)
            logger.info(f"Documentation generated successfully in {abs_output_dir}")

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
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'sections'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'diagrams'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'assets'), exist_ok=True)

    def _create_vector_store_and_rag_chain(self, analyses: Sequence[FileAnalysis]) -> Runnable:
        """Create vector store and RAG chain from analyses using LCEL.

        Args:
            analyses: List of file analysis results

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

            # Create vector store
            logger.info("Creating vector store and RAG chain...")
            texts = self.text_splitter.split_documents(documents)
            self._vector_store = Chroma.from_documents(texts, self.embeddings)
            retriever = self._vector_store.as_retriever()

            # Create RAG prompt template
            rag_prompt = ChatPromptTemplate.from_template(
                """You are a documentation expert analyzing a Python codebase.
Use the following context from the codebase to answer the question.
If you cannot find relevant information in the context, say so.

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
    ) -> tuple[Dict[str, str], List[tuple[str, str]]]:
        """Generate all documentation diagrams.

        Args:
            analyses: List of file analysis results

        Returns:
            Tuple of (diagrams dict, list of (diagram_name, error_message) pairs)
        """
        logger.info("Generating diagrams...")
        diagrams: Dict[str, str] = {}
        errors: List[tuple[str, str]] = []

        # Generate architecture diagram
        try:
            diagrams['architecture'] = self.diagram_generator.generate_architecture_diagram(analyses)
        except Exception as e:
            errors.append(('architecture', str(e)))

        # Generate class diagram
        try:
            diagrams['class_diagram'] = self.diagram_generator.generate_class_diagram(analyses)
        except Exception as e:
            errors.append(('class_diagram', str(e)))

        # Generate function-related diagrams
        try:
            function_calls = self.analyzer.analyze_function_calls(analyses)
            try:
                diagrams['sequence'] = self.diagram_generator.generate_sequence_diagram(function_calls)
            except Exception as e:
                errors.append(('sequence', str(e)))
            try:
                diagrams['function_calls'] = self.diagram_generator.generate_call_graph_diagram(function_calls)
            except Exception as e:
                errors.append(('function_calls', str(e)))
        except Exception as e:
            errors.append(('function_analysis', str(e)))

        # Generate dependency diagram
        try:
            package_deps = self.analyzer.analyze_package_dependencies()
            diagrams['package_dependencies'] = self.diagram_generator.generate_dependency_diagram(package_deps)
        except Exception as e:
            errors.append(('package_dependencies', str(e)))

        return diagrams, errors

    def _generate_documentation_sections(self, rag_chain: Runnable) -> Dict[str, Any]:
        """Generate all documentation sections using the RAG chain.

        Args:
            rag_chain: LCEL RAG chain for content generation

        Returns:
            Tuple of (documentation dict, list of (section_name, error) pairs)
        """
        logger.info("Generating documentation content...")

        sections = []
        errors: List[tuple[str, str]] = []

        for section_name in SECTION_ORDER:
            logger.info(f"Generating section: {section_name}")
            try:
                content = self._generate_section(rag_chain, section_name)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to generate section '{section_name}': {error_msg}")
                errors.append((section_name, error_msg))
                content = f"*Error generating this section: {error_msg}*"

            sections.append({
                'title': section_name,
                'content': content
            })

        if errors:
            logger.warning(
                f"Some sections failed to generate ({len(errors)} errors):\n"
                + "\n".join(f"  - {name}: {error}" for name, error in errors)
            )

        documentation = {
            'title': 'Code Documentation',
            'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'sections': sections
        }

        return documentation, errors

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
            return rag_chain.invoke(prompt)
        except Exception as e:
            raise LLMError(f"Failed to generate section '{section_name}': {str(e)}") from e

    def _create_final_html_output(
        self,
        documentation: Dict[str, Any],
        diagrams: Dict[str, str],
        output_dir: str,
        generation_errors: Optional[Dict[str, List[tuple[str, str]]]] = None
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
            self._generate_html_documentation(documentation, diagrams, output_dir, generation_errors)
        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise TemplateError(f"Failed to generate HTML documentation: {str(e)}")

    def _create_documents(self, analyses: Sequence[FileAnalysis]) -> List[Document]:
        """Create LangChain documents from file analyses.

        Args:
            analyses: List of file analysis results

        Returns:
            List of LangChain documents for vector store
        """
        documents: List[Document] = []

        for analysis in analyses:
            # Add file content
            documents.append(Document(
                page_content=analysis.content,
                metadata={"source": analysis.file_path}
            ))

            # Add entity information
            for entity in analysis.entities:
                doc = f"Type: {entity.type}\nName: {entity.name}\n"
                if entity.docstring:
                    doc += f"Description: {entity.docstring}\n"
                if entity.type == 'class':
                    if entity.methods is not None:
                        doc += f"Methods: {', '.join(entity.methods)}\n"
                    else:
                        doc += "Methods: None\n"
                    if entity.parent_class:
                        doc += f"Inherits from: {entity.parent_class}\n"
                documents.append(Document(
                    page_content=doc,
                    metadata={"source": analysis.file_path}
                ))

        return documents

    def _generate_html_documentation(
        self,
        documentation: Dict[str, Any],
        diagrams: Dict[str, str],
        output_dir: str,
        generation_errors: Optional[Dict[str, List[tuple[str, str]]]] = None
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
            errors = generation_errors or {'diagrams': [], 'sections': []}
            has_errors = bool(errors.get('diagrams') or errors.get('sections'))

            # Generate index page
            index_context = {
                'title': documentation['title'],
                'documentation': documentation,
                'base_url': './',  # Current directory for index page
                'navigation': self._generate_navigation('index', documentation['sections'], './'),
                'generation_errors': errors if has_errors else None,
            }
            self.template_manager.render_template('index', index_context, output_dir, 'index.html')

            # Generate section pages
            for section in documentation['sections']:
                filename = f"sections/{section['title'].lower().replace(' ', '_')}.html"
                section_context = {
                    'title': section['title'],
                    'section': section,
                    'base_url': '../',  # Parent directory for section pages
                    'navigation': self._generate_navigation(section['title'], documentation['sections'], '../')
                }
                self.template_manager.render_template('section', section_context, output_dir, filename)

            # Generate diagram pages
            diagram_files = {
                'architecture': diagrams.get('architecture', ''),
                'dependencies': diagrams.get('package_dependencies', ''),
                'classes': diagrams.get('class_diagram', ''),
                'sequence': diagrams.get('sequence', ''),
                'call_graph': diagrams.get('function_calls', '')
            }

            for name, diagram in diagram_files.items():
                if diagram:
                    filename = f"diagrams/{name}.html"
                    diagram_context = {
                        'title': f"{name.replace('_', ' ').title()} Diagram",
                        'diagram_code': diagram,
                        'base_url': '../',  # Parent directory for diagram pages
                        'navigation': self._generate_navigation('diagrams', documentation['sections'], '../')
                    }
                    self.template_manager.render_template('diagrams', diagram_context, output_dir, filename)

            # Generate search page
            search_context = {
                'title': 'Search Documentation',
                'base_url': './',  # Current directory for search page
                'navigation': self._generate_navigation('search', documentation['sections'], './')
            }
            self.template_manager.render_template('search', search_context, output_dir, 'search.html')

        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise DocumentationError(f"Failed to generate HTML documentation: {str(e)}")

    def _generate_navigation(
        self,
        active_page: str,
        sections: List[Dict[str, str]],
        base_url: str
    ) -> str:
        """Generate navigation HTML for the current page.

        Args:
            active_page: Currently active page
            sections: List of documentation sections
            base_url: Base URL for relative paths

        Returns:
            Navigation HTML content
        """
        return self.template_manager.templates['navigation'].render(
            active=active_page,
            sections=[s['title'] for s in sections],
            base_url=base_url
        )
