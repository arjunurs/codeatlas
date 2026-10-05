"""HTML templates for documentation generation.

This module loads the HTML templates used to generate the final documentation,
including styling and interactive features, from the templates/files directory
or from a custom directory that overrides some or all of them.
"""

import logging
import os
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from ..utils.path_validation import require_within

logger = logging.getLogger(__name__)


# Default templates directory (relative to this module)
DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "files"


class TemplateManager:
    """Manages HTML templates for documentation generation.

    This class handles loading and rendering of various documentation templates
    including the main index, section pages, and diagram views. A template in
    a custom directory replaces the bundled one of the same name.

    Attributes:
        env: Jinja2 environment for template rendering
        templates: Dictionary of loaded template objects
    """

    def __init__(self, template_dir: str | None = None):
        """Initialize the template manager.

        Args:
            template_dir: Optional custom directory for templates. A
                template it lacks comes from the bundled templates.
        """
        self._template_dir = template_dir
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Set up the Jinja2 environment with appropriate loaders."""
        loaders = []

        # Try custom template directory first
        if self._template_dir:
            if os.path.isdir(self._template_dir):
                loaders.append(FileSystemLoader(self._template_dir))
                logger.debug(f"Using custom template directory: {self._template_dir}")
            else:
                logger.warning(
                    f"Custom template directory does not exist: {self._template_dir}. "
                    "Falling back to default templates."
                )

        # Then the bundled templates, which the package always includes
        loaders.append(FileSystemLoader(str(DEFAULT_TEMPLATES_DIR)))

        # Create environment with choice loader
        self.env = Environment(loader=ChoiceLoader(loaders), autoescape=True)

        self.templates = {}
        template_names = [
            "base",
            "index",
            "section",
            "diagrams",
            "navigation",
        ]
        for name in template_names:
            self.templates[name] = self.env.get_template(f"{name}.html")

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

        require_within(output_path, output_dir)
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
