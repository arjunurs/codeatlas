"""Cross-reference analysis for tracking component usage across the codebase.

This module provides utilities to build import/usage graphs and track where
components are defined and used throughout the codebase.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..models.file_analysis import FileAnalysis

logger = logging.getLogger(__name__)


@dataclass
class ComponentReference:
    """Reference information for a code component.

    Attributes:
        name: Component name (class, function, module)
        type: Component type ("class", "function", "module")
        defined_in: File path where component is defined
        line_number: Line number where defined (None for modules)
        imported_by: Set of file paths that import this component
        used_in: Set of file paths that use this component
        import_count: Total number of imports
    """

    name: str
    type: str
    defined_in: str
    line_number: int | None
    imported_by: set[str]
    used_in: set[str]

    @property
    def import_count(self) -> int:
        """Total number of files that import this component."""
        return len(self.imported_by)

    @property
    def usage_count(self) -> int:
        """Total number of files that use this component."""
        return len(self.used_in)


class CrossReferenceAnalyzer:
    """Analyzes code to build cross-reference and usage information.

    This analyzer builds a comprehensive map of where components are defined
    and used throughout the codebase by analyzing imports and entity definitions.
    """

    def __init__(self, analyses: list[FileAnalysis]):
        """Initialize the cross-reference analyzer.

        Args:
            analyses: List of file analyses from CodeAnalyzer
        """
        self.analyses = analyses
        self._components: dict[str, ComponentReference] = {}
        self._build_reference_map()

    def _build_reference_map(self) -> None:
        """Build the complete cross-reference map from analyses."""
        # First pass: Register all defined components
        for analysis in self.analyses:
            file_path = analysis.file_path

            # Register module
            module_name = Path(file_path).stem
            if module_name not in self._components:
                self._components[module_name] = ComponentReference(
                    name=module_name,
                    type="module",
                    defined_in=file_path,
                    line_number=None,
                    imported_by=set(),
                    used_in=set(),
                )

            # Register classes and functions
            for entity in analysis.entities:
                component_name = entity.name
                if component_name not in self._components:
                    self._components[component_name] = ComponentReference(
                        name=component_name,
                        type=entity.type,
                        defined_in=file_path,
                        line_number=entity.start_line,
                        imported_by=set(),
                        used_in=set(),
                    )

        # Second pass: Track imports and usage
        for analysis in self.analyses:
            file_path = analysis.file_path

            # Track imports (imports are strings like "os" or "typing.List")
            for import_str in analysis.imports:
                # Split by '.' to get module parts
                parts = import_str.split(".")

                # Track the base module
                base_module = parts[0]
                if base_module in self._components:
                    self._components[base_module].imported_by.add(file_path)
                    self._components[base_module].used_in.add(file_path)

                # Track specific names (e.g., "List" in "typing.List")
                if len(parts) > 1:
                    name = parts[-1]
                    if name in self._components:
                        self._components[name].imported_by.add(file_path)
                        self._components[name].used_in.add(file_path)

                # Also check for the full import string
                if import_str in self._components:
                    self._components[import_str].imported_by.add(file_path)
                    self._components[import_str].used_in.add(file_path)

    def get_top_components(self, limit: int = 15) -> list[ComponentReference]:
        """Get the most referenced components sorted by usage.

        Args:
            limit: Maximum number of components to return

        Returns:
            List of ComponentReference objects sorted by total usage
        """
        components = list(self._components.values())

        # Sort by total usage (imports + usage)
        components.sort(
            key=lambda c: c.import_count + c.usage_count, reverse=True
        )

        return components[:limit]

    def get_component_references(
        self, component_name: str
    ) -> ComponentReference | None:
        """Get reference information for a specific component.

        Args:
            component_name: Name of the component to look up

        Returns:
            ComponentReference if found, None otherwise
        """
        return self._components.get(component_name)

    def get_components_by_type(
        self, component_type: str
    ) -> list[ComponentReference]:
        """Get all components of a specific type.

        Args:
            component_type: Type to filter by ("class", "function", "module")

        Returns:
            List of ComponentReference objects of the specified type
        """
        return [
            comp
            for comp in self._components.values()
            if comp.type == component_type
        ]

    def generate_reference_report(self, limit: int = 15) -> str:
        """Generate a formatted cross-reference report.

        Args:
            limit: Maximum number of components to include

        Returns:
            Markdown-formatted report of top components and their usage
        """
        top_components = self.get_top_components(limit)

        if not top_components:
            return "No cross-references found."

        lines = ["# Cross-Reference Analysis\n"]

        # Group by type
        by_type: dict[str, list[ComponentReference]] = defaultdict(list)
        for comp in top_components:
            by_type[comp.type].append(comp)

        # Generate report for each type
        for comp_type in ["class", "function", "module"]:
            if comp_type not in by_type:
                continue

            components = by_type[comp_type]
            type_title = comp_type.capitalize() + "es" if comp_type == "class" else comp_type.capitalize() + "s"
            lines.append(f"\n## {type_title}\n")

            for comp in components:
                # Component header
                location = f"{comp.defined_in}"
                if comp.line_number:
                    location += f":{comp.line_number}"
                lines.append(f"### `{comp.name}`")
                lines.append(f"**Defined in:** `{location}`\n")

                # Usage information
                if comp.imported_by:
                    lines.append(
                        f"**Imported by {len(comp.imported_by)} files:**"
                    )
                    for file_path in sorted(comp.imported_by)[:10]:
                        lines.append(f"- `{file_path}`")
                    if len(comp.imported_by) > 10:
                        lines.append(
                            f"- ... and {len(comp.imported_by) - 10} more"
                        )
                    lines.append("")

                if comp.used_in and comp.used_in != comp.imported_by:
                    additional_usage = comp.used_in - comp.imported_by
                    if additional_usage:
                        lines.append(f"**Also used in {len(additional_usage)} files:**")
                        for file_path in sorted(additional_usage)[:5]:
                            lines.append(f"- `{file_path}`")
                        lines.append("")

        return "\n".join(lines)

    def get_import_graph(self) -> dict[str, list[str]]:
        """Generate an import dependency graph.

        Returns:
            Dictionary mapping file paths to lists of files they import from
        """
        graph: dict[str, list[str]] = defaultdict(list)

        for analysis in self.analyses:
            file_path = analysis.file_path
            imported_files = set()

            # Find which files this file imports from
            for comp in self._components.values():
                if file_path in comp.imported_by and comp.defined_in != file_path:
                    imported_files.add(comp.defined_in)

            graph[file_path] = sorted(imported_files)

        return dict(graph)
