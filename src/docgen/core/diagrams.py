"""Diagram generation module.

This module provides functionality for generating various types of diagrams
for code documentation.
"""

import logging
import os
from typing import Dict, List, Set

from ..exceptions.errors import DiagramGenerationError
from ..models.file_analysis import FileAnalysis

logger = logging.getLogger(__name__)

class DiagramGenerator:
    """Generates various types of diagrams for code documentation.

    This class provides methods for generating:
    - Class diagrams
    - Sequence diagrams
    - Dependency diagrams
    - Call graph diagrams
    """

    def __init__(self, max_nodes: int = 50):
        """Initialize the diagram generator.

        Args:
            max_nodes: Maximum number of nodes to show in diagrams
        """
        self.max_nodes = max_nodes

    @staticmethod
    def _clean_name(name: str) -> str:
        """Clean a name for use in Mermaid diagrams.

        Args:
            name: Name to clean

        Returns:
            Cleaned name safe for use in diagrams
        """
        clean = name.replace("-", "_").replace(".", "_").replace("/", "_").replace("@", "")
        return clean

    def _add_node_with_limit(self, diagram: List[str], node_name: str, nodes_seen: Set[str], nodes_added: int) -> bool:
        """Add a node to the diagram if within node limit.

        Args:
            diagram: List of diagram lines
            node_name: Name of node to add
            nodes_seen: Set of nodes already added
            nodes_added: Number of nodes added so far

        Returns:
            True if node was added, False if limit reached
        """
        if nodes_added >= self.max_nodes:
            if not any(line.startswith("    Note:") for line in diagram):
                diagram.append(f"    Note: Showing top {self.max_nodes} nodes")
            return False

        clean_name = self._clean_name(node_name)
        if node_name not in nodes_seen:
            diagram.append(f"    {clean_name}[{clean_name}]")
            nodes_seen.add(node_name)
            return True
        return False

    def generate_class_diagram(self, analyses: List[FileAnalysis]) -> str:
        """Generate a class diagram from file analyses.

        Args:
            analyses: List of file analyses

        Returns:
            Mermaid class diagram source

        Raises:
            DiagramGenerationError: If no classes found or diagram generation fails
        """
        if not analyses:
            raise DiagramGenerationError("No files to analyze")

        classes = []
        for analysis in analyses:
            for entity in analysis.entities:
                if entity.type == "class":
                    classes.append(entity)

        if not classes:
            raise DiagramGenerationError("No classes found in analyzed files")

        diagram = ["classDiagram"]
        nodes_added = 0

        for cls in classes:
            if nodes_added >= self.max_nodes:
                diagram.append(f"    note \"Diagram truncated at {self.max_nodes} nodes\"")
                break

            # Add class definition
            if cls.parent_class:
                diagram.append(f"    {cls.name} --|> {cls.parent_class}")
            
            # Add class declaration
            diagram.append(f"    class {cls.name} {{")

            # Add methods
            if cls.methods:
                for method in cls.methods:
                    diagram.append(f"        +{method}()")
            
            diagram.append("    }")
            nodes_added += 1

        return "\n".join(diagram)

    def generate_sequence_diagram(self, call_graph: Dict[str, Set[str]]) -> str:
        """Generate a sequence diagram from function call graph.

        Args:
            call_graph: Dictionary mapping functions to their called functions

        Returns:
            Mermaid sequence diagram source

        Raises:
            DiagramGenerationError: If no function calls found or diagram generation fails
        """
        if not call_graph:
            raise DiagramGenerationError("Empty call graph")

        diagram = ["sequenceDiagram"]
        nodes_added = 0

        for caller, callees in call_graph.items():
            if not callees:
                continue

            if nodes_added >= self.max_nodes:
                diagram.append(f"    Note over {self._clean_name(caller)}: Diagram truncated at {self.max_nodes} nodes")
                break

            for callee in callees:
                clean_caller = self._clean_name(caller)
                clean_callee = self._clean_name(callee)
                diagram.append(f"    {clean_caller}->>+{clean_callee}: call()")
                diagram.append(f"    {clean_callee}-->>-{clean_caller}: return")
                nodes_added += 1

        if nodes_added == 0:
            raise DiagramGenerationError("No function calls found in call graph")

        return "\n".join(diagram)

    def generate_dependency_diagram(self, dependencies: Dict[str, Set[str]]) -> str:
        """Generate a dependency diagram from package dependencies.

        Args:
            dependencies: Dictionary mapping packages to their dependencies

        Returns:
            Mermaid graph diagram source

        Raises:
            DiagramGenerationError: If no dependencies found or diagram generation fails
        """
        if not dependencies:
            raise DiagramGenerationError("No dependencies to analyze")

        diagram = ["graph LR"]
        nodes_seen = set()
        nodes_added = 0

        for package, deps in dependencies.items():
            if nodes_added >= self.max_nodes:
                diagram.append(f"    Note: Diagram truncated at {self.max_nodes} nodes")
                break

            clean_package = self._clean_name(package)
            if package not in nodes_seen:
                diagram.append(f"    {clean_package}[{package}]")
                nodes_seen.add(package)
                nodes_added += 1

            for dep in deps:
                if nodes_added >= self.max_nodes:
                    break

                clean_dep = self._clean_name(dep)
                if dep not in nodes_seen:
                    diagram.append(f"    {clean_dep}[{dep}]")
                    nodes_seen.add(dep)
                    nodes_added += 1

                diagram.append(f"    {clean_package} --> {clean_dep}")

        if nodes_added == 0:
            raise DiagramGenerationError("No dependencies found in packages")

        return "\n".join(diagram)

    def generate_call_graph_diagram(self, call_graph: Dict[str, Set[str]]) -> str:
        """Generate a call graph diagram showing function calls.

        Args:
            call_graph: Dictionary mapping functions to their called functions

        Returns:
            Mermaid graph diagram markup

        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            if not call_graph:
                return "graph TD\n    Note: No function calls found"

            diagram = ["graph TD"]
            nodes_seen = set()
            nodes_added = 0

            for caller, callees in call_graph.items():
                if nodes_added >= self.max_nodes:
                    break

                clean_caller = self._clean_name(caller)
                if self._add_node_with_limit(diagram, caller, nodes_seen, nodes_added):
                    nodes_added += 1

                for callee in callees:
                    if nodes_added >= self.max_nodes:
                        break

                    clean_callee = self._clean_name(callee)
                    if self._add_node_with_limit(diagram, callee, nodes_seen, nodes_added):
                        nodes_added += 1

                    diagram.append(f"    {clean_caller} --> {clean_callee}")

            if nodes_added >= self.max_nodes:
                diagram.append(f"    Note: Showing top {self.max_nodes} nodes")

            return "\n".join(diagram)
        except Exception as e:
            logger.debug(f"Error in call graph diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate call graph diagram: {str(e)}")

    def generate_architecture_diagram(self, analyses: List[FileAnalysis]) -> str:
        """Generate an architecture diagram showing module relationships.

        Args:
            analyses: List of file analyses

        Returns:
            Mermaid graph diagram markup

        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            if not analyses:
                return "graph TD\n    Note: No files to analyze"

            diagram = ["graph TD"]
            nodes_seen = set()
            nodes_added = 0

            for analysis in analyses:
                if nodes_added >= self.max_nodes:
                    break

                module_name = os.path.splitext(os.path.basename(analysis.file_path))[0]
                if self._add_node_with_limit(diagram, module_name, nodes_seen, nodes_added):
                    nodes_added += 1

                for imp in analysis.imports:
                    if nodes_added >= self.max_nodes:
                        break

                    if self._add_node_with_limit(diagram, imp, nodes_seen, nodes_added):
                        nodes_added += 1

                    clean_module = self._clean_name(module_name)
                    clean_imp = self._clean_name(imp)
                    diagram.append(f"    {clean_module} --> {clean_imp}")

            if nodes_added >= self.max_nodes:
                diagram.append(f"    Note: Showing top {self.max_nodes} nodes")

            return "\n".join(diagram)
        except Exception as e:
            logger.debug(f"Error in architecture diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate architecture diagram: {str(e)}") 