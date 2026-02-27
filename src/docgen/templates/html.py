"""HTML templates for documentation generation.

This module provides the HTML templates used to generate the final documentation,
including styling and interactive features. It supports both file-based templates
and embedded templates for backward compatibility.
"""

import logging
import os
from pathlib import Path
from typing import Any

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    TemplateNotFound,
)

logger = logging.getLogger(__name__)


class StringTemplateLoader(BaseLoader):
    """Custom template loader that loads templates from strings."""

    def __init__(self, templates: dict[str, str]):
        self.templates = templates

    def get_source(self, environment, template):
        # Remove .html extension if present for lookup
        lookup_name = (
            template.replace(".html", "") if template.endswith(".html") else template
        )
        if lookup_name in self.templates:
            source = self.templates[lookup_name]
            return source, None, lambda: True
        raise TemplateNotFound(template)


# Default templates directory (relative to this module)
DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "files"


class TemplateManager:
    """Manages HTML templates for documentation generation.

    This class handles loading and rendering of various documentation templates
    including the main index, section pages, and diagram views.

    The manager supports two modes:
    1. File-based templates: Loads templates from a specified directory
    2. Embedded templates: Falls back to embedded string templates

    Attributes:
        env: Jinja2 environment for template rendering
        templates: Dictionary of loaded template objects
    """

    def __init__(self, template_dir: str | None = None):
        """Initialize the template manager.

        Args:
            template_dir: Optional custom directory for templates.
                If not provided, uses the default templates directory.
                Falls back to embedded templates if no files are found.
        """
        self._template_dir = template_dir
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up the Jinja2 environment with appropriate loaders."""
        loaders = []
        custom_dir_configured = False

        # Try custom template directory first
        if self._template_dir:
            if os.path.isdir(self._template_dir):
                loaders.append(FileSystemLoader(self._template_dir))
                custom_dir_configured = True
                logger.debug(f"Using custom template directory: {self._template_dir}")
            else:
                logger.warning(
                    f"Custom template directory does not exist: {self._template_dir}. "
                    "Falling back to default templates."
                )

        # Then try default templates directory
        if DEFAULT_TEMPLATES_DIR.is_dir():
            loaders.append(FileSystemLoader(str(DEFAULT_TEMPLATES_DIR)))
            logger.debug(f"Using default template directory: {DEFAULT_TEMPLATES_DIR}")

        # Finally fall back to embedded templates
        loaders.append(StringTemplateLoader(_EMBEDDED_TEMPLATES))

        # Create environment with choice loader
        self.env = Environment(loader=ChoiceLoader(loaders), autoescape=True)

        # Pre-load templates for backward compatibility
        self.templates = {}
        template_names = [
            "base",
            "index",
            "section",
            "diagrams",
            "search",
            "navigation",
        ]
        for name in template_names:
            try:
                # Try .html extension first (file-based)
                self.templates[name] = self.env.get_template(f"{name}.html")
                source_type = "file-based"
            except TemplateNotFound:
                # Fall back to no extension (embedded)
                self.templates[name] = self.env.get_template(name)
                source_type = "embedded"
                if custom_dir_configured:
                    logger.warning(
                        f"Template '{name}' not found in custom directory, using {source_type} version"
                    )
            logger.debug(f"Loaded template '{name}' from {source_type}")

    def render_to_string(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> str:
        """Render a template and return the result as a string.

        Args:
            template_name: Name of the template to render
            context: Template context data

        Returns:
            Rendered template content

        Raises:
            ValueError: If template name is not recognized
        """
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")

        return self.templates[template_name].render(**context)

    def render_template(
        self,
        template_name: str,
        context: dict[str, Any],
        output_dir: str,
        filename: str | None = None,
    ) -> None:
        """Render a template and save it to a file.

        Args:
            template_name: Name of the template to render
            context: Template context data
            output_dir: Output directory path
            filename: Optional custom filename
        """
        output = self.render_to_string(template_name, context)

        if filename:
            output_path = os.path.join(output_dir, filename)
        else:
            output_path = os.path.join(output_dir, f"{template_name}.html")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)


def get_template_manager(template_dir: str | None = None) -> TemplateManager:
    """Get a template manager instance.

    Args:
        template_dir: Optional custom directory for templates

    Returns:
        TemplateManager instance
    """
    return TemplateManager(template_dir=template_dir)


# Embedded templates as fallback (minimal versions for backward compatibility)
_EMBEDDED_TEMPLATES = {
    "base": """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .sidebar { width: 300px; height: 100vh; position: fixed; top: 0; left: 0; overflow-y: auto; background: white; border-right: 1px solid #e5e7eb; padding: 1rem; }
        .main-content { margin-left: 300px; padding: 1rem; min-height: 100vh; }
        .nav-item { padding: 0.5rem; cursor: pointer; border-radius: 4px; display: block; width: 100%; margin-bottom: 0.25rem; }
        .nav-item:hover { background: #f3f4f6; }
        .nav-item.active { background: #e5e7eb; }
        .search-box { width: 100%; padding: 0.5rem; border: 1px solid #e5e7eb; border-radius: 4px; margin-bottom: 1rem; }
        .diagram-container { width: 100%; height: 80vh; overflow: auto; border: 1px solid #e5e7eb; padding: 0.5rem; background: white; }
        .mermaid { min-height: 80vh; }
    </style>
    <script>mermaid.initialize({ startOnLoad: true, theme: 'default' });</script>
</head>
<body class="bg-gray-100">
    <div class="sidebar">
        <input type="text" id="search" placeholder="Search..." class="search-box">
        <div id="navigation">{{ navigation | safe }}</div>
    </div>
    <div class="main-content">{% block content %}{% endblock %}</div>
</body>
</html>""",
    "index": """{% extends "base" %}
{% block content %}
<h1 class="text-4xl font-bold mb-8">{{ documentation.title }}</h1>
{% if generation_errors %}
<div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-8">
    <h3 class="font-medium text-yellow-800">Generation Warnings</h3>
    <ul class="mt-2 text-yellow-700 list-disc list-inside">
        {% for name, error in generation_errors.sections %}<li><strong>Section "{{ name }}":</strong> {{ error }}</li>{% endfor %}
        {% for name, error in generation_errors.diagrams %}<li><strong>Diagram "{{ name }}":</strong> {{ error }}</li>{% endfor %}
    </ul>
</div>
{% endif %}
<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
    <div class="bg-white p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-semibold mb-4">Sections</h2>
        <ul class="space-y-2">
            {% for section in documentation.sections %}
            <li><a href="{{ base_url }}/sections/{{ section.title | lower | replace(' ', '_') }}.html" class="text-blue-600 hover:text-blue-800">{{ section.title }}</a></li>
            {% endfor %}
        </ul>
    </div>
    <div class="bg-white p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-semibold mb-4">Diagrams</h2>
        <ul class="space-y-2">
            <li><a href="{{ base_url }}/diagrams/architecture.html" class="text-blue-600 hover:text-blue-800">Architecture</a></li>
            <li><a href="{{ base_url }}/diagrams/classes.html" class="text-blue-600 hover:text-blue-800">Classes</a></li>
        </ul>
    </div>
</div>
<footer class="text-center text-gray-500 mt-12">Generated on {{ documentation.generated_date }}</footer>
{% endblock %}""",
    "section": """{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow-lg">
    <h1 class="text-4xl font-bold mb-8">{{ section.title }}</h1>
    <div class="prose max-w-none">{{ section.content | safe }}</div>
</div>
{% endblock %}""",
    "diagrams": """{% extends "base" %}
{% block content %}
<div class="bg-white rounded-lg shadow-lg">
    <div class="p-4 border-b"><h1 class="text-2xl font-bold">{{ title }}</h1></div>
    <div id="diagram" class="diagram-container">
        <pre class="mermaid">{{ diagram_code | trim }}</pre>
    </div>
</div>
{% endblock %}""",
    "search": """{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow-lg">
    <h1 class="text-4xl font-bold mb-8">Search Results</h1>
    <div id="search-results"></div>
</div>
{% endblock %}""",
    "navigation": """<nav>
    <div class="mb-4"><a href="{{ base_url }}index.html" class="nav-item {% if active == 'index' %}active{% endif %}"><i class="fas fa-home mr-2"></i> Home</a></div>
    <div class="mb-4">
        <h3 class="font-semibold mb-2 pb-2 border-b">Documentation</h3>
        {% for section in sections %}<a href="{{ base_url }}sections/{{ section | lower | replace(' ', '_') }}.html" class="nav-item {% if active == section %}active{% endif %}">{{ section }}</a>{% endfor %}
    </div>
    <div>
        <h3 class="font-semibold mb-2 pb-2 border-b">Diagrams</h3>
        <a href="{{ base_url }}diagrams/architecture.html" class="nav-item {% if active == 'architecture' %}active{% endif %}"><i class="fas fa-project-diagram mr-2"></i> Architecture</a>
        <a href="{{ base_url }}diagrams/dependencies.html" class="nav-item {% if active == 'dependencies' %}active{% endif %}"><i class="fas fa-cubes mr-2"></i> Dependencies</a>
        <a href="{{ base_url }}diagrams/classes.html" class="nav-item {% if active == 'classes' %}active{% endif %}"><i class="fas fa-sitemap mr-2"></i> Classes</a>
        <a href="{{ base_url }}diagrams/sequence.html" class="nav-item {% if active == 'sequence' %}active{% endif %}"><i class="fas fa-exchange-alt mr-2"></i> Sequence</a>
        <a href="{{ base_url }}diagrams/call_graph.html" class="nav-item {% if active == 'call_graph' %}active{% endif %}"><i class="fas fa-code-branch mr-2"></i> Call Graph</a>
    </div>
</nav>""",
}
