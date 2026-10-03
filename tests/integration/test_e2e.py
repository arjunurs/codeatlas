"""End-to-end integration tests for the documentation generator.

These tests verify the complete workflow from source code analysis
to final documentation output, testing the integration between all
components.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docgen.cli import main
from docgen.config import CacheConfig, GenerationOptions
from docgen.core.analyzer import CodeAnalyzer
from docgen.core.generator import CodeDocumentationGenerator
from docgen.exceptions.errors import DocumentationError
from docgen.models.code_entity import EntityType
from docgen.providers.base import BaseEmbeddingProvider, BaseLLMProvider
from docgen.templates.html import get_template_manager

SECTION_MARKDOWN = "## Summary\n\nThe calculator project adds **e2e-marker** numbers."

CALCULATOR_SOURCE = '''"""A small calculator."""


class Calculator:
    """Adds numbers."""

    def add_numbers(self, a: int, b: int) -> int:
        """Return the sum of a and b."""
        return a + b
'''

MAIN_SOURCE = '''from calculator import Calculator


def run() -> int:
    """Add two numbers."""
    return Calculator().add_numbers(2, 3)
'''


class TestCommandLineRun:
    """The codeatlas command on a small project, down to the generated HTML.

    Only the two SDK clients are replaced, by fake LangChain models. Analysis,
    chunking, the Chroma store, retrieval, the RAG chain, usage tracking,
    Markdown rendering, sanitizing, and templates all run for real.
    """

    def test_generated_text_reaches_every_section_page(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
        fake_chat_model_with_usage,
        fake_embeddings,
    ):
        """Each section page shows the model's text, rendered from Markdown."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "calculator.py").write_text(CALCULATOR_SOURCE)
        (project / "main.py").write_text(MAIN_SOURCE)
        output = tmp_path / "output"

        chat_model = fake_chat_model_with_usage.model_copy(
            update={"content": SECTION_MARKDOWN}
        )
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        # Keep any default paths, such as .docgen_cache, out of the repository
        monkeypatch.chdir(tmp_path)

        with (
            patch("docgen.providers.anthropic.ChatAnthropic", return_value=chat_model),
            patch(
                "docgen.providers.openai.OpenAIEmbeddings",
                return_value=fake_embeddings,
            ),
            # setup_logging replaces the root handlers, including pytest's
            patch("docgen.cli.setup_logging"),
        ):
            main(["--source", str(project), "-o", str(output)])

        pages = sorted(path.name for path in (output / "sections").glob("*.html"))
        assert pages == [
            "data_flow.html",
            "dependencies.html",
            "integration_points.html",
            "key_classes_and_functions.html",
            "overview.html",
        ]
        for page in pages:
            html = (output / "sections" / page).read_text()
            assert "<strong>e2e-marker</strong>" in html, page

        # Retrieval put the project's code into every section prompt
        assert len(chat_model.prompts) == 5
        assert all("def add_numbers" in prompt for prompt in chat_model.prompts)

        # The diagrams were built from the same analysis
        assert "Calculator" in (output / "diagrams" / "classes.html").read_text()

        # The reported usage reached the cost summary: 5 calls of 120 + 30 tokens
        summary = capsys.readouterr().out
        assert "Input tokens: 600" in summary
        assert "Output tokens: 150" in summary


class TestPythonApiRun:
    """Custom providers, written as CONTRIBUTING.md describes, run end to end."""

    def test_custom_providers_generate_documentation(
        self, tmp_path: Path, fake_chat_model_with_usage, fake_embeddings
    ):
        """Providers that only create their models are enough for a full run."""
        chat_model = fake_chat_model_with_usage.model_copy(
            update={"content": SECTION_MARKDOWN}
        )

        class LocalLLMProvider(BaseLLMProvider):
            def _create_llm(self):
                return chat_model

        class LocalEmbeddingProvider(BaseEmbeddingProvider):
            def _create_embeddings(self):
                return fake_embeddings

        project = tmp_path / "project"
        project.mkdir()
        (project / "calculator.py").write_text(CALCULATOR_SOURCE)
        output = tmp_path / "output"

        with CodeDocumentationGenerator(
            llm_provider=LocalLLMProvider(api_key="unused", model="local-model"),
            embedding_provider=LocalEmbeddingProvider(
                api_key="unused", model="local-embeddings"
            ),
            generation_options=GenerationOptions(
                selected_sections=["overview"], skip_diagrams=True
            ),
            cache_config=CacheConfig(enabled=False),
        ) as generator:
            generator.generate_documentation(str(project), str(output))

        overview = (output / "sections" / "overview.html").read_text()
        assert "<strong>e2e-marker</strong>" in overview
        assert "def add_numbers" in chat_model.prompts[0]


class TestGeneratorLifecycle:
    """Test the generator's resource handling."""

    def test_context_manager_drops_the_in_memory_store(
        self,
        temp_source_dir: Path,
        temp_output_dir: Path,
        fake_chat_model_with_usage,
        fake_embeddings,
    ):
        """Leaving the with block drops the run's in-memory vector store."""
        llm_provider = MagicMock(model_name="claude-sonnet-5")
        llm_provider.get_langchain_llm.return_value = fake_chat_model_with_usage
        embedding_provider = MagicMock(model_name="text-embedding-3-small")
        embedding_provider.get_langchain_embeddings.return_value = fake_embeddings

        with CodeDocumentationGenerator(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            generation_options=GenerationOptions(
                selected_sections=["overview"], skip_diagrams=True
            ),
            cache_config=CacheConfig(enabled=False),
        ) as generator:
            generator.generate_documentation(str(temp_source_dir), str(temp_output_dir))
            client = generator._rag_pipeline.vector_store._client
            collections_during_run = client.count_collections()

        assert client.count_collections() == collections_during_run - 1


class TestErrorHandling:
    """Test error handling in the documentation generator."""

    def test_empty_source_directory(
        self, empty_source_dir: Path, temp_output_dir: Path
    ):
        """Test that empty source directory raises appropriate error."""
        generator = CodeDocumentationGenerator(
            llm_provider=MagicMock(), embedding_provider=MagicMock()
        )

        with pytest.raises(DocumentationError, match="No Python files found"):
            generator.generate_documentation(
                str(empty_source_dir), str(temp_output_dir)
            )

    def test_invalid_source_directory(self, temp_output_dir: Path):
        """Test that invalid source directory raises ValueError."""
        generator = CodeDocumentationGenerator(
            llm_provider=MagicMock(), embedding_provider=MagicMock()
        )

        with pytest.raises(ValueError, match="Invalid source directory"):
            generator.generate_documentation("/nonexistent/path", str(temp_output_dir))

    @pytest.mark.parametrize(
        ("has_llm", "has_embeddings"), [(False, False), (True, False), (False, True)]
    )
    def test_missing_provider_rejected(self, has_llm, has_embeddings):
        """A run that calls the models needs both providers."""
        with pytest.raises(
            ValueError, match="required unless diagrams_only or dry_run"
        ):
            CodeDocumentationGenerator(
                llm_provider=MagicMock() if has_llm else None,
                embedding_provider=MagicMock() if has_embeddings else None,
            )

    @pytest.mark.parametrize(
        "options",
        [GenerationOptions(diagrams_only=True), GenerationOptions(dry_run=True)],
    )
    def test_modes_without_model_calls_need_no_providers(self, options):
        """Diagrams-only and dry-run runs can be set up without providers."""
        generator = CodeDocumentationGenerator(generation_options=options)

        assert generator.llm_provider is None
        assert generator.embedding_provider is None


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

    def test_analyzer_skips_files_with_syntax_errors(self, tmp_path: Path, caplog):
        """A file that does not parse is skipped with a warning; others are analyzed."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "bad.py").write_text("def broken(\n    syntax error here")
        (source_dir / "good.py").write_text("def ok():\n    return 1\n")

        with caplog.at_level(logging.WARNING, logger="docgen.core.analyzer"):
            analyses = CodeAnalyzer().analyze_directory(str(source_dir))

        assert [Path(a.file_path).name for a in analyses] == ["good.py"]
        assert "Skipping" in caplog.text
        assert "bad.py" in caplog.text


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
                llm_provider=llm_provider, embedding_provider=embedding_provider
            )

            assert generator.llm_provider is llm_provider
            assert generator.embedding_provider is embedding_provider
