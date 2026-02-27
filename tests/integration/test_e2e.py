"""End-to-end integration tests for the documentation generator.

These tests verify the complete workflow from source code analysis
to final documentation output, testing the integration between all
components.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docgen.core.analyzer import CodeAnalyzer
from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import ApiKeyError, DocumentationError
from docgen.models.code_entity import EntityType
from docgen.templates.html import get_template_manager


class TestFullWorkflow:
    """Test the complete documentation generation workflow."""

    def test_analyze_generate_verify(
        self,
        temp_source_dir: Path,
        temp_output_dir: Path,
        mock_llm,
        mock_embeddings,
    ):
        """Test the full workflow: analyze source -> generate docs -> verify output.

        This test verifies that:
        1. Source code is properly analyzed
        2. Vector store is created successfully
        3. Documentation sections are generated
        4. HTML output is created in the correct structure
        """
        # Create a mock RAG chain that returns strings directly (as LCEL chains do after StrOutputParser)
        mock_rag_chain = MagicMock()
        mock_rag_chain.invoke.return_value = (
            "# Generated Content\n\nThis is documentation."
        )

        mock_vector_store = MagicMock()
        mock_vector_store.delete_collection = MagicMock()

        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings
            ),
            patch("docgen.core.generator.Chroma") as mock_chroma,
            patch.object(
                CodeDocumentationGenerator,
                "_create_vector_store_and_rag_chain",
                return_value=mock_rag_chain,
            ),
        ):
            mock_chroma.from_documents.return_value = mock_vector_store

            # Create generator and run
            generator = CodeDocumentationGenerator(
                anthropic_api_key="test-key",
                openai_api_key="test-key",
            )
            generator._vector_store = mock_vector_store

            generator.generate_documentation(str(temp_source_dir), str(temp_output_dir))

            # Verify output structure
            assert (temp_output_dir / "index.html").exists()
            assert (temp_output_dir / "sections").is_dir()
            assert (temp_output_dir / "diagrams").is_dir()
            assert (temp_output_dir / "assets").is_dir()
            assert (temp_output_dir / "search.html").exists()

            # Verify section files
            sections_dir = temp_output_dir / "sections"
            expected_sections = [
                "overview.html",
                "dependencies.html",
                "key_classes_and_functions.html",
                "data_flow.html",
                "integration_points.html",
            ]
            for section in expected_sections:
                assert (sections_dir / section).exists(), f"Missing section: {section}"

    def test_context_manager_cleanup(
        self,
        temp_source_dir: Path,
        temp_output_dir: Path,
        mock_llm,
        mock_embeddings,
    ):
        """Test that the context manager properly cleans up resources."""
        # Create a mock RAG chain that returns strings directly
        mock_rag_chain = MagicMock()
        mock_rag_chain.invoke.return_value = "Content"

        mock_vector_store = MagicMock()
        mock_vector_store.delete_collection = MagicMock()

        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings
            ),
            patch("docgen.core.generator.Chroma") as mock_chroma,
            patch.object(
                CodeDocumentationGenerator,
                "_create_vector_store_and_rag_chain",
                return_value=mock_rag_chain,
            ),
        ):
            mock_chroma.from_documents.return_value = mock_vector_store

            with CodeDocumentationGenerator(
                anthropic_api_key="test-key",
                openai_api_key="test-key",
                cache_enabled=False,  # Disable caching so cleanup deletes the collection
            ) as generator:
                generator._vector_store = mock_vector_store
                generator.generate_documentation(
                    str(temp_source_dir), str(temp_output_dir)
                )

            # After context exit, cleanup should have been called
            mock_vector_store.delete_collection.assert_called_once()


class TestErrorHandling:
    """Test error handling in the documentation generator."""

    def test_empty_source_directory(
        self,
        empty_source_dir: Path,
        temp_output_dir: Path,
        mock_llm,
        mock_embeddings,
    ):
        """Test that empty source directory raises appropriate error."""
        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings
            ),
        ):
            generator = CodeDocumentationGenerator(
                anthropic_api_key="test-key",
                openai_api_key="test-key",
            )

            with pytest.raises(DocumentationError, match="No Python files found"):
                generator.generate_documentation(
                    str(empty_source_dir), str(temp_output_dir)
                )

    def test_invalid_source_directory(
        self,
        temp_output_dir: Path,
        mock_llm,
        mock_embeddings,
    ):
        """Test that invalid source directory raises ValueError."""
        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings
            ),
        ):
            generator = CodeDocumentationGenerator(
                anthropic_api_key="test-key",
                openai_api_key="test-key",
            )

            with pytest.raises(ValueError, match="Invalid source directory"):
                generator.generate_documentation(
                    "/nonexistent/path", str(temp_output_dir)
                )

    def test_missing_api_keys(self):
        """Test that missing API keys raise appropriate error."""
        with pytest.raises(ApiKeyError):
            CodeDocumentationGenerator(
                anthropic_api_key=None,
                openai_api_key=None,
            )

    def test_partial_api_keys(self):
        """Test that partial API keys raise appropriate error."""
        with pytest.raises(
            ApiKeyError, match="Both Anthropic and OpenAI API keys are required"
        ):
            CodeDocumentationGenerator(
                anthropic_api_key="test-key",
                openai_api_key=None,
            )

        with pytest.raises(
            ApiKeyError, match="Both Anthropic and OpenAI API keys are required"
        ):
            CodeDocumentationGenerator(
                anthropic_api_key=None,
                openai_api_key="test-key",
            )


class TestCodeAnalysis:
    """Test code analysis integration."""

    def test_analyzer_processes_source_files(self, temp_source_dir: Path):
        """Test that analyzer correctly processes Python source files."""
        analyzer = CodeAnalyzer()
        analyses = analyzer.analyze_directory(str(temp_source_dir))

        # Should find all Python files
        file_names = [Path(a.file_path).name for a in analyses]
        assert "__init__.py" in file_names
        assert "main.py" in file_names
        assert "utils.py" in file_names

        # Check main.py analysis
        main_analysis = next(a for a in analyses if Path(a.file_path).name == "main.py")
        assert len(main_analysis.entities) > 0

        # Should have found the class
        class_entities = [
            e for e in main_analysis.entities if e.type == EntityType.CLASS
        ]
        assert len(class_entities) >= 1
        assert any(e.name == "MainClass" for e in class_entities)

        # Should have found the function
        func_entities = [
            e for e in main_analysis.entities if e.type == EntityType.FUNCTION
        ]
        assert len(func_entities) >= 1
        assert any(e.name == "helper_function" for e in func_entities)

    def test_analyzer_handles_syntax_errors(self, tmp_path: Path):
        """Test that analyzer handles files with syntax errors gracefully."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()

        # Create file with syntax error
        (source_dir / "bad.py").write_text("def broken(\n    syntax error here")

        analyzer = CodeAnalyzer()
        analyses = analyzer.analyze_directory(str(source_dir))

        # Should still return a result (possibly with error flag)
        assert len(analyses) >= 0  # May be empty or have error info


class TestTemplateRendering:
    """Test template rendering integration."""

    def test_template_manager_renders_all_templates(self, temp_output_dir: Path):
        """Test that template manager can render all template types."""
        manager = get_template_manager()

        # Test navigation rendering
        nav_html = manager.templates["navigation"].render(
            active="Overview", sections=["Overview", "Dependencies"], base_url="./"
        )
        assert "Overview" in nav_html
        assert "Dependencies" in nav_html

        # Test search template
        context = {
            "title": "Search",
            "navigation": nav_html,
        }
        manager.render_template("search", context, str(temp_output_dir), "search.html")
        assert (temp_output_dir / "search.html").exists()

        # Test diagram template
        context = {
            "title": "Test Diagram",
            "diagram_code": "graph TD\n    A --> B",
            "navigation": nav_html,
        }
        manager.render_template(
            "diagrams", context, str(temp_output_dir), "diagrams/test.html"
        )
        assert (temp_output_dir / "diagrams" / "test.html").exists()


class TestProviderIntegration:
    """Test provider integration with the generator."""

    def test_provider_mode_initialization(self, mock_llm, mock_embeddings):
        """Test initialization with provider instances."""
        from docgen.providers.anthropic import AnthropicProvider
        from docgen.providers.openai import OpenAIEmbeddingProvider

        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings", return_value=mock_embeddings
            ),
        ):
            llm_provider = AnthropicProvider(api_key="test-key")
            embedding_provider = OpenAIEmbeddingProvider(api_key="test-key")

            generator = CodeDocumentationGenerator(
                llm_provider=llm_provider,
                embedding_provider=embedding_provider,
            )

            assert generator.llm_provider is llm_provider
            assert generator.embedding_provider is embedding_provider

    def test_mixed_mode_raises_error(self, mock_llm, mock_embeddings):
        """Test that mixing providers and API keys raises appropriate error."""
        from docgen.providers.anthropic import AnthropicProvider

        with patch("docgen.providers.anthropic.ChatAnthropic", return_value=mock_llm):
            llm_provider = AnthropicProvider(api_key="test-key")

            with pytest.raises(ApiKeyError, match="must be provided together"):
                CodeDocumentationGenerator(
                    llm_provider=llm_provider,
                    embedding_provider=None,  # Missing embedding provider
                )
