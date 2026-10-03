"""Unit tests for HTML template system."""

import pytest

from docgen.templates.html import (
    DEFAULT_TEMPLATES_DIR,
    TemplateManager,
    get_template_manager,
)


class TestTemplateManager:
    """Test cases for TemplateManager."""

    def test_default_initialization(self):
        """Test default initialization with built-in templates."""
        manager = TemplateManager()

        # Should have all required templates
        assert "base" in manager.templates
        assert "index" in manager.templates
        assert "section" in manager.templates
        assert "diagrams" in manager.templates
        assert "search" in manager.templates
        assert "navigation" in manager.templates

    def test_custom_template_directory(self, tmp_path):
        """Test initialization with custom template directory."""
        # Create custom templates
        (tmp_path / "base.html").write_text("<html>{{ title }}</html>")
        (tmp_path / "index.html").write_text("{% extends 'base.html' %}Index")
        (tmp_path / "section.html").write_text("{% extends 'base.html' %}Section")
        (tmp_path / "diagrams.html").write_text("{% extends 'base.html' %}Diagrams")
        (tmp_path / "search.html").write_text("{% extends 'base.html' %}Search")
        (tmp_path / "navigation.html").write_text("<nav></nav>")

        manager = TemplateManager(template_dir=str(tmp_path))

        # Should load custom templates
        assert "base" in manager.templates

    def test_custom_directory_falls_back_to_bundled_templates(self, tmp_path):
        """A template the custom directory lacks comes from the bundled ones."""
        (tmp_path / "section.html").write_text("custom {{ title }}")

        manager = TemplateManager(template_dir=str(tmp_path))

        assert manager.render_to_string("section", {"title": "Overview"}) == (
            "custom Overview"
        )
        assert "Search Documentation" in manager.render_to_string(
            "search", {"title": "Search"}
        )

    def test_render_template_creates_file(self, tmp_path):
        """Test that render_template creates output file."""
        manager = TemplateManager()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        context = {
            "title": "Test Title",
            "navigation": "<nav>Nav</nav>",
        }

        manager.render_template("search", context, str(output_dir), "search.html")

        output_file = output_dir / "search.html"
        assert output_file.exists()
        content = output_file.read_text()
        assert "Search Documentation" in content

    def test_render_template_creates_subdirectory(self, tmp_path):
        """Test that render_template creates subdirectories if needed."""
        manager = TemplateManager()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        context = {
            "title": "Test Section",
            "section": {"title": "Overview", "content": "Content here"},
            "navigation": "<nav>Nav</nav>",
        }

        manager.render_template(
            "section", context, str(output_dir), "sections/overview.html"
        )

        output_file = output_dir / "sections" / "overview.html"
        assert output_file.exists()

    def test_render_unknown_template_raises_error(self):
        """Test that rendering unknown template raises ValueError."""
        manager = TemplateManager()

        with pytest.raises(ValueError, match="Unknown template"):
            manager.render_template("nonexistent", {}, "/tmp", "test.html")

    def test_navigation_template_renders_correctly(self):
        """Test navigation template renders with correct structure."""
        manager = TemplateManager()

        html = manager.templates["navigation"].render(
            active="Overview", sections=["Overview", "Dependencies"], base_url="./"
        )

        assert "Overview" in html
        assert "Dependencies" in html
        assert "index.html" in html

    def test_diagrams_template_renders_mermaid(self, tmp_path):
        """Test diagrams template includes mermaid code."""
        manager = TemplateManager()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        context = {
            "title": "Class Diagram",
            "diagram_code": "classDiagram\n    class Test",
            "navigation": "<nav>Nav</nav>",
        }

        manager.render_template(
            "diagrams", context, str(output_dir), "diagrams/test.html"
        )

        output_file = output_dir / "diagrams" / "test.html"
        content = output_file.read_text()
        assert "mermaid" in content
        assert "classDiagram" in content


class TestGetTemplateManager:
    """Test cases for get_template_manager function."""

    def test_returns_template_manager(self):
        """Test that function returns a TemplateManager."""
        manager = get_template_manager()
        assert isinstance(manager, TemplateManager)

    def test_accepts_custom_directory(self, tmp_path):
        """Test that function accepts custom template directory."""
        manager = get_template_manager(template_dir=str(tmp_path))
        assert isinstance(manager, TemplateManager)


class TestFileBasedTemplates:
    """Test cases for file-based template loading."""

    def test_default_templates_directory_exists(self):
        """Test that default templates directory exists."""
        assert DEFAULT_TEMPLATES_DIR.is_dir()

    def test_required_template_files_exist(self):
        """Test that all required template files exist."""
        required_files = [
            "base.html",
            "index.html",
            "section.html",
            "diagrams.html",
            "search.html",
            "navigation.html",
        ]

        for filename in required_files:
            filepath = DEFAULT_TEMPLATES_DIR / filename
            assert filepath.exists(), f"Missing template file: {filename}"

    def test_templates_are_valid_jinja2(self):
        """Test that all template files are valid Jinja2 templates."""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(DEFAULT_TEMPLATES_DIR)))

        template_names = [
            "base.html",
            "index.html",
            "section.html",
            "diagrams.html",
            "search.html",
            "navigation.html",
        ]

        for name in template_names:
            # Should not raise any syntax errors
            template = env.get_template(name)
            assert template is not None
