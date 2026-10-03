"""HTML documentation renderer.

This module handles generating HTML output from documentation content
and Mermaid diagrams using Jinja2 templates.
"""

from __future__ import annotations

import os
from typing import Any

import jinja2
import markdown
import nh3

from ..exceptions.errors import DocumentationError


class DocumentationRenderer:
    """Renders documentation content into HTML pages.

    Handles the HTML output pipeline: setting up directories, rendering
    index/section/diagram/search pages via the template manager.
    """

    def __init__(self, template_manager) -> None:
        self.template_manager = template_manager

    def setup_output_directories(self, output_dir: str) -> None:
        """Create the output directory structure.

        Args:
            output_dir: Base output directory path
        """
        for subdir in ["", "sections", "diagrams", "assets"]:
            os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    def convert_markdown_to_html(self, content: str) -> str:
        """Convert markdown content to HTML.

        Args:
            content: Markdown-formatted text content

        Returns:
            HTML-formatted content
        """
        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        return md.convert(content)

    def render(
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
            # Section content (LLM output and error text) is inserted as HTML,
            # so keep only an allowlist of tags and attributes: no scripts,
            # event handlers, or javascript: URLs
            documentation = {
                **documentation,
                "sections": [
                    {**section, "content": nh3.clean(section["content"])}
                    for section in documentation["sections"]
                ],
            }

            errors = generation_errors or {"diagrams": [], "sections": []}
            has_errors = bool(errors.get("diagrams") or errors.get("sections"))

            # Generate index page
            index_context = {
                "title": documentation["title"],
                "documentation": documentation,
                "base_url": "./",
                "navigation": self.generate_navigation(
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

                prev_section = sections_list[i - 1]["title"] if i > 0 else None
                next_section = (
                    sections_list[i + 1]["title"]
                    if i < len(sections_list) - 1
                    else None
                )

                section_context = {
                    "title": section["title"],
                    "section": section,
                    "base_url": "../",
                    "navigation": self.generate_navigation(
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
                        "base_url": "../",
                        "navigation": self.generate_navigation(
                            "diagrams", documentation["sections"], "../"
                        ),
                    }
                    self.template_manager.render_template(
                        "diagrams", diagram_context, output_dir, filename
                    )

            # Generate search page
            search_context = {
                "title": "Search Documentation",
                "base_url": "./",
                "navigation": self.generate_navigation(
                    "search", documentation["sections"], "./"
                ),
            }
            self.template_manager.render_template(
                "search", search_context, output_dir, "search.html"
            )

        except (OSError, jinja2.TemplateError) as e:
            raise DocumentationError(
                f"Failed to generate HTML documentation: {e}"
            ) from e

    def generate_navigation(
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
