"""HTML documentation renderer.

This module handles generating HTML output from documentation content
and Mermaid diagrams using Jinja2 templates.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import jinja2
import nh3
from markdown_it import MarkdownIt

from ..exceptions.errors import DocumentationError


@dataclass(frozen=True)
class DiagramPage:
    """A diagram's page in the site.

    Attributes:
        page: The page's file name in diagrams/, without .html
        key: The diagram's name in the diagrams the generator passes
        title: What the diagram is called everywhere in the site
        icon: The Font Awesome icon shown beside it in the sidebar
    """

    page: str
    key: str
    title: str
    icon: str


# The diagram pages, in the order the sidebar and the index list them
DIAGRAM_PAGES = (
    DiagramPage("architecture", "architecture", "Architecture", "fa-project-diagram"),
    DiagramPage("dependencies", "package_dependencies", "Dependencies", "fa-cubes"),
    DiagramPage("classes", "class_diagram", "Classes", "fa-sitemap"),
    DiagramPage("sequence", "sequence", "Sequence", "fa-exchange-alt"),
    DiagramPage("call_graph", "function_calls", "Call Graph", "fa-code-branch"),
)


class DocumentationRenderer:
    """Renders documentation content into HTML pages.

    Handles the HTML output pipeline: setting up directories, rendering
    index, section, and diagram pages via the template manager.
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

        Follows CommonMark, plus tables: a sub-item indented to its parent's
        text is nested, which is how the model writes nested lists.

        Args:
            content: Markdown-formatted text content

        Returns:
            HTML-formatted content
        """
        return MarkdownIt("commonmark").enable("table").render(content)

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

            # Only the diagrams that were generated get a page and a link
            pages = [page for page in DIAGRAM_PAGES if diagrams.get(page.key)]
            sections = documentation["sections"]

            # Generate index page
            project = documentation["title"]
            index_context = {
                "title": project,
                "project": project,
                "documentation": documentation,
                "diagram_pages": pages,
                "base_url": "./",
                "navigation": self.generate_navigation("index", sections, "./", pages),
                "generation_errors": errors if has_errors else None,
            }
            self.template_manager.render_template(
                "index", index_context, output_dir, "index.html"
            )

            # Generate section pages
            for i, section in enumerate(sections):
                filename = f"sections/{section['title'].lower().replace(' ', '_')}.html"

                prev_section = sections[i - 1]["title"] if i > 0 else None
                next_section = (
                    sections[i + 1]["title"] if i < len(sections) - 1 else None
                )

                section_context = {
                    "title": section["title"],
                    "project": project,
                    "section": section,
                    "base_url": "../",
                    "navigation": self.generate_navigation(
                        section["title"], sections, "../", pages
                    ),
                    "prev_section": prev_section,
                    "next_section": next_section,
                }
                self.template_manager.render_template(
                    "section", section_context, output_dir, filename
                )

            # Generate diagram pages
            for page in pages:
                diagram_context = {
                    "title": page.title,
                    "project": project,
                    "diagram_code": diagrams[page.key],
                    "base_url": "../",
                    "navigation": self.generate_navigation(
                        page.page, sections, "../", pages
                    ),
                }
                self.template_manager.render_template(
                    "diagrams",
                    diagram_context,
                    output_dir,
                    f"diagrams/{page.page}.html",
                )

        except (OSError, jinja2.TemplateError) as e:
            raise DocumentationError(
                f"Failed to generate HTML documentation: {e}"
            ) from e

    def generate_navigation(
        self,
        active_page: str,
        sections: list[dict[str, str]],
        base_url: str,
        diagram_pages: Sequence[DiagramPage] = (),
    ) -> str:
        """Generate navigation HTML for the current page.

        Args:
            active_page: The current page: index, a section's title, or a
                diagram page's name
            sections: List of documentation sections
            base_url: Base URL for relative paths
            diagram_pages: The diagram pages to link to

        Returns:
            Navigation HTML content
        """
        return self.template_manager.templates["navigation"].render(
            active=active_page,
            sections=[s["title"] for s in sections],
            diagrams=diagram_pages,
            base_url=base_url,
        )
