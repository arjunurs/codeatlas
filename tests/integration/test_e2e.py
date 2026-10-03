"""End-to-end integration tests for the documentation generator.

These tests verify the complete workflow from source code analysis
to final documentation output, testing the integration between all
components.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.runnables import RunnableLambda

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


class TestDependencyManifests:
    """The Dependencies section is written from the project's manifests."""

    def test_dependencies_prompt_shows_the_pyproject_above_the_package(
        self, tmp_path: Path, fake_chat_model_with_usage, fake_embeddings
    ):
        """--source repo/calc reads repo/pyproject.toml, for that section only."""
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "calc"\ndependencies = ["numpy>=2.1"]\n\n'
            "[tool.ruff]\nline-length = 100\n"
        )
        (repo / "calc").mkdir()
        (repo / "calc" / "__init__.py").write_text("")
        (repo / "calc" / "calculator.py").write_text(CALCULATOR_SOURCE)
        llm_provider = MagicMock(model_name="claude-sonnet-5")
        llm_provider.get_langchain_llm.return_value = fake_chat_model_with_usage
        embedding_provider = MagicMock(model_name="text-embedding-3-small")
        embedding_provider.get_langchain_embeddings.return_value = fake_embeddings

        with CodeDocumentationGenerator(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            generation_options=GenerationOptions(
                selected_sections=["overview", "dependencies"],
                skip_diagrams=True,
                parallel_sections=False,
            ),
            cache_config=CacheConfig(enabled=False),
        ) as generator:
            generator.generate_documentation(
                str(repo / "calc"), str(tmp_path / "output")
            )

        overview, dependencies = fake_chat_model_with_usage.prompts
        assert "Analyze the project dependencies" in dependencies
        assert 'dependencies = ["numpy>=2.1"]' in dependencies
        assert "line-length" not in dependencies
        assert "numpy" not in overview


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
            pipeline = generator._rag_pipeline
            assert pipeline is not None and pipeline.vector_store is not None
            client = pipeline.vector_store._client
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


def failing_model(*failures: str) -> RunnableLambda:
    """A model that raises each message in turn, then answers normally."""
    remaining = list(failures)

    def answer(prompt) -> str:
        if remaining:
            raise RuntimeError(remaining.pop(0))
        return "generated text"

    return RunnableLambda(answer)


def generate_sections(model, source_dir: Path, output_dir: Path, fake_embeddings):
    """Generate the overview and dependencies sections, one after the other."""
    llm_provider = MagicMock(model_name="claude-sonnet-5")
    llm_provider.get_langchain_llm.return_value = model
    embedding_provider = MagicMock(model_name="text-embedding-3-small")
    embedding_provider.get_langchain_embeddings.return_value = fake_embeddings
    with CodeDocumentationGenerator(
        llm_provider,
        embedding_provider,
        generation_options=GenerationOptions(
            selected_sections=["overview", "dependencies"],
            skip_diagrams=True,
            parallel_sections=False,
        ),
        cache_config=CacheConfig(enabled=False),
    ) as generator:
        generator.generate_documentation(str(source_dir), str(output_dir))


class TestSectionFailures:
    """How a run reports sections that fail."""

    def test_run_fails_when_every_section_fails(
        self, temp_source_dir, temp_output_dir, fake_embeddings
    ):
        """One shared cause is reported once, and the pages are still written."""
        model = failing_model("model down", "model down")

        with pytest.raises(
            DocumentationError,
            match=r"^No section could be generated: RuntimeError: model down$",
        ):
            generate_sections(model, temp_source_dir, temp_output_dir, fake_embeddings)

        assert (temp_output_dir / "index.html").exists()
        overview = (temp_output_dir / "sections" / "overview.html").read_text()
        assert "RuntimeError: model down" in overview

    def test_sections_failing_differently_are_each_listed(
        self, temp_source_dir, temp_output_dir, fake_embeddings
    ):
        """Different causes are listed by section."""
        model = failing_model("first cause", "second cause")

        with pytest.raises(DocumentationError) as exc_info:
            generate_sections(model, temp_source_dir, temp_output_dir, fake_embeddings)

        assert str(exc_info.value) == (
            "No section could be generated:\n"
            "  - Overview: RuntimeError: first cause\n"
            "  - Dependencies: RuntimeError: second cause"
        )

    def test_partial_failure_is_one_warning(
        self, temp_source_dir, temp_output_dir, fake_embeddings, caplog
    ):
        """A run where some sections work succeeds, with one warning for the rest."""
        model = failing_model("model down")

        with caplog.at_level(logging.INFO, logger="docgen"):
            generate_sections(model, temp_source_dir, temp_output_dir, fake_embeddings)

        problems = [
            r
            for r in caplog.records
            if r.name.startswith("docgen") and r.levelno >= logging.WARNING
        ]
        assert [r.getMessage() for r in problems] == [
            "1 of 2 sections failed:\n  - Overview: RuntimeError: model down"
        ]


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
