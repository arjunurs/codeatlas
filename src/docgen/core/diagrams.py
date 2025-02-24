"""Diagram generation functionality for the documentation generator.

This module provides the DiagramGenerator class for creating various types of
Mermaid diagrams from code analysis results.
"""

import logging
import networkx as nx
from typing import List, Dict, Set, Optional, Tuple
from functools import lru_cache
from dataclasses import dataclass

from ..models.file_analysis import FileAnalysis
from ..exceptions.errors import DiagramGenerationError

logger = logging.getLogger(__name__)

@dataclass
class DiagramConfig:
    """Configuration for diagram generation.
    
    Attributes:
        max_nodes: Maximum number of nodes in function call graphs
        node_limit_warning: Warning message when node limit is exceeded
        default_theme: Default theme for diagrams
    """
    max_nodes: int = 50
    node_limit_warning: str = "Note: Showing top {limit} most connected functions"
    default_theme: str = "default"

class DiagramGenerator:
    """Generates various types of Mermaid diagrams from code analysis.
    
    This class handles the generation of:
    1. Architecture diagrams showing module relationships
    2. Class diagrams showing inheritance and composition
    3. Sequence diagrams showing interactions
    4. Package dependency diagrams
    5. Function call graphs
    
    Each diagram is generated in Mermaid syntax for rendering in HTML.
    The generator includes caching for improved performance and
    configurable limits to prevent oversized diagrams.
    """
    
    def __init__(self, config: Optional[DiagramConfig] = None) -> None:
        """Initialize the diagram generator.
        
        Args:
            config: Optional configuration for diagram generation
        """
        self.config = config or DiagramConfig()
    
    @lru_cache(maxsize=32)
    def generate_architecture_diagram(self, analyses: Tuple[FileAnalysis, ...]) -> str:
        """Generate a Mermaid architecture diagram showing module relationships.
        
        Uses caching to improve performance for repeated generation of the
        same diagram.
        
        Args:
            analyses: Tuple of FileAnalysis objects to visualize
            
        Returns:
            Mermaid diagram code as string
            
        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            # Create directed graph
            G = nx.DiGraph()
            
            # Add nodes and edges from imports
            for analysis in analyses:
                module_name = self._get_module_name(analysis.file_path)
                G.add_node(module_name)
                
                for imp in analysis.imports:
                    imported_module = imp.split('.')[0]
                    if imported_module != module_name:
                        G.add_edge(module_name, imported_module)
            
            # Generate Mermaid code
            mermaid_code = [
                "%%{init: {'theme': '" + self.config.default_theme + "'}}%%",
                "graph TD"
            ]
            
            # Add nodes with tooltips
            for node in G.nodes():
                clean_node = self._clean_name(node)
                tooltip = f"Module: {node}"
                mermaid_code.append(
                    f"    {clean_node}[{node}]:::module"
                    f" tooltip \"{tooltip}\""
                )
            
            # Add edges with counts
            edge_counts: Dict[Tuple[str, str], int] = {}
            for source, target in G.edges():
                key = (self._clean_name(source), self._clean_name(target))
                edge_counts[key] = edge_counts.get(key, 0) + 1
            
            for (source, target), count in edge_counts.items():
                label = f" |{count}|" if count > 1 else ""
                mermaid_code.append(f"    {source} -->|{label}| {target}")
            
            # Add styling
            mermaid_code.extend([
                "    classDef module fill:#f9f,stroke:#333,stroke-width:2px;",
                "    linkStyle default stroke:#666,stroke-width:2px;"
            ])
            
            return "\n".join(mermaid_code)
            
        except Exception as e:
            logger.error(f"Error generating architecture diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate architecture diagram: {str(e)}")
    
    def generate_class_diagram(self, analyses: List[FileAnalysis]) -> str:
        """Generate a Mermaid class diagram showing relationships between classes.
        
        Args:
            analyses: List of FileAnalysis objects to visualize
            
        Returns:
            Mermaid diagram code as string
            
        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            mermaid_code = ["classDiagram"]
            added_classes = set()
            
            for analysis in analyses:
                for entity in analysis.entities:
                    if entity.type == 'class':
                        class_name = self._clean_name(entity.name)
                        if class_name in added_classes:
                            continue
                        
                        # Add class definition
                        mermaid_code.append(f"    class {class_name} {{")
                        
                        # Add docstring as comment
                        if entity.docstring:
                            doc_lines = entity.docstring.split('\n')
                            for line in doc_lines[:3]:  # Limit to first 3 lines
                                if line.strip():
                                    mermaid_code.append(f"        %% {line.strip()}")
                        
                        # Add methods
                        if entity.methods:
                            for method in entity.methods:
                                if not method.startswith('__'):  # Skip special methods
                                    mermaid_code.append(f"        +{method}()")
                        
                        mermaid_code.append("    }")
                        added_classes.add(class_name)
                        
                        # Add inheritance
                        if entity.parent_class:
                            parent_name = self._clean_name(entity.parent_class)
                            if parent_name not in added_classes:
                                mermaid_code.append(f"    class {parent_name}")
                                added_classes.add(parent_name)
                            mermaid_code.append(f"    {parent_name} <|-- {class_name}")
            
            return "\n".join(mermaid_code)
            
        except Exception as e:
            logger.error(f"Error generating class diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate class diagram: {str(e)}")
    
    def generate_sequence_diagram(self, analyses: List[FileAnalysis]) -> str:
        """Generate a Mermaid sequence diagram showing interactions.
        
        Args:
            analyses: List of FileAnalysis objects to visualize
            
        Returns:
            Mermaid diagram code as string
            
        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            mermaid_code = ["sequenceDiagram"]
            participants = set()
            interactions = []
            
            # First pass: collect participants
            for analysis in analyses:
                for entity in analysis.entities:
                    if entity.type == 'class':
                        participants.add(entity.name)
            
            if not participants:
                return "sequenceDiagram\n    Note over A: No clear interactions detected"
            
            # Add participants
            for participant in sorted(participants):
                clean_name = self._clean_name(participant)
                mermaid_code.append(f"    participant {clean_name} as {participant}")
            
            # Second pass: add interactions based on method calls
            for analysis in analyses:
                for entity in analysis.entities:
                    if entity.type == 'class' and entity.methods:
                        source = self._clean_name(entity.name)
                        for method in entity.methods:
                            if not method.startswith('__'):
                                target = source  # Self-call by default
                                interactions.append(
                                    f"    {source}->>+{target}: {method}"
                                )
            
            mermaid_code.extend(interactions)
            return "\n".join(mermaid_code)
            
        except Exception as e:
            logger.error(f"Error generating sequence diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate sequence diagram: {str(e)}")
    
    def generate_dependency_diagram(self, dependencies: Dict[str, Set[str]]) -> str:
        """Generate a Mermaid diagram from package dependencies.
        
        Args:
            dependencies: Dictionary mapping packages to their dependencies
            
        Returns:
            Mermaid diagram code as string
            
        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            mermaid_code = ["graph TD"]
            added_nodes = set()
            
            for package, deps in dependencies.items():
                pkg_name = self._clean_name(package)
                if pkg_name not in added_nodes:
                    mermaid_code.append(f"    {pkg_name}[{package}]")
                    added_nodes.add(pkg_name)
                
                for dep in deps:
                    dep_name = self._clean_name(dep)
                    if dep_name not in added_nodes:
                        mermaid_code.append(f"    {dep_name}[{dep}]")
                        added_nodes.add(dep_name)
                    mermaid_code.append(f"    {pkg_name} --> {dep_name}")
            
            return "\n".join(mermaid_code)
            
        except Exception as e:
            logger.error(f"Error generating dependency diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate dependency diagram: {str(e)}")
    
    def generate_call_graph_diagram(self, call_graph: Dict[str, Set[str]]) -> str:
        """Generate a Mermaid diagram from function call relationships.
        
        Args:
            call_graph: Dictionary mapping functions to their called functions
            
        Returns:
            Mermaid diagram code as string
            
        Raises:
            DiagramGenerationError: If diagram generation fails
        """
        try:
            mermaid_code = ["graph TD"]
            added_nodes = set()
            
            # Calculate function importance (number of connections)
            function_importance = {}
            for caller, callees in call_graph.items():
                function_importance[caller] = len(callees)
                for callee in callees:
                    function_importance[callee] = function_importance.get(callee, 0) + 1
            
            # Sort functions by importance
            sorted_functions = sorted(
                function_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Limit to MAX_NODES most important functions
            important_functions = {
                func for func, _ in sorted_functions[:self.config.max_nodes]
            }
            
            # Add nodes and edges for important functions
            for caller, callees in call_graph.items():
                if caller in important_functions:
                    caller_name = self._clean_name(caller)
                    if caller_name not in added_nodes:
                        mermaid_code.append(f"    {caller_name}[{caller}]")
                        added_nodes.add(caller_name)
                    
                    for callee in callees:
                        if callee in important_functions:
                            callee_name = self._clean_name(callee)
                            if callee_name not in added_nodes:
                                mermaid_code.append(f"    {callee_name}[{callee}]")
                                added_nodes.add(callee_name)
                            mermaid_code.append(f"    {caller_name} --> {callee_name}")
            
            # Add note if functions were omitted
            if len(function_importance) > self.config.max_nodes:
                mermaid_code.append(
                    self.config.node_limit_warning.format(limit=self.config.max_nodes)
                )
            
            return "\n".join(mermaid_code)
            
        except Exception as e:
            logger.error(f"Error generating call graph diagram: {str(e)}")
            raise DiagramGenerationError(f"Failed to generate call graph diagram: {str(e)}")
    
    def _clean_name(self, name: str) -> str:
        """Clean a name for Mermaid compatibility.
        
        Args:
            name: Name to clean
            
        Returns:
            Cleaned name safe for Mermaid diagrams
        """
        return name.replace('-', '_').replace('.', '_').replace('@', 'at_')
    
    def _get_module_name(self, file_path: str) -> str:
        """Extract module name from file path.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            Module name
        """
        parts = file_path.split('/')
        for i, part in enumerate(reversed(parts)):
            if part.endswith('.py'):
                if part == '__init__.py' and i + 1 < len(parts):
                    return parts[-(i+2)]
                return part[:-3]
        return file_path 