"""Code analysis functionality for the documentation generator.

This module provides the CodeAnalyzer class for parsing and analyzing Python source code,
including dependency analysis and function call tracking.
"""

import os
import ast
import glob
import logging
from typing import List, Dict, Set, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
import pkg_resources
import requirements
from functools import lru_cache

from ..models.code_entity import CodeEntity
from ..models.file_analysis import FileAnalysis
from ..exceptions.errors import CodeParseError

logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """Analyzes Python source code to extract structure and relationships.
    
    This class handles:
    1. Parsing Python files to extract classes, functions, and imports
    2. Analyzing package dependencies
    3. Building function call graphs
    4. Tracking inheritance relationships
    
    The analyzer uses threading for parallel file processing and caching
    for improved performance.
    
    Attributes:
        skip_validation: Whether to skip validation in FileAnalysis creation
        max_workers: Maximum number of parallel workers for file processing
    """
    
    def __init__(self, skip_validation: bool = False, max_workers: int = 4) -> None:
        """Initialize the analyzer.
        
        Args:
            skip_validation: Whether to skip validation in FileAnalysis creation
            max_workers: Maximum number of parallel workers for file processing
        """
        self.skip_validation = skip_validation
        self.max_workers = max_workers
    
    def analyze_directory(self, directory_path: str) -> List[FileAnalysis]:
        """Analyze all Python files in a directory.
        
        Uses parallel processing for improved performance on large codebases.
        
        Args:
            directory_path: Path to the directory to analyze
            
        Returns:
            List of FileAnalysis objects for each Python file
            
        Raises:
            CodeParseError: If directory doesn't exist or no Python files found
        """
        if not os.path.isdir(directory_path):
            raise CodeParseError(f"Directory does not exist: {directory_path}")
            
        python_files = self._find_python_files(directory_path)
        if not python_files:
            raise CodeParseError(f"No Python files found in {directory_path}")
            
        analyses = []
        failed_files = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self.analyze_file, file_path): file_path
                for file_path in python_files
            }
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {str(e)}")
                    failed_files.append(file_path)
                    
        if not analyses:
            raise CodeParseError("No files could be successfully analyzed")
            
        if failed_files:
            logger.warning(f"Failed to analyze {len(failed_files)} files")
            
        return analyses
    
    def _find_python_files(self, directory_path: str) -> List[str]:
        """Find all Python files in a directory recursively.
        
        Args:
            directory_path: Directory to search
            
        Returns:
            List of Python file paths
        """
        python_files = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    @lru_cache(maxsize=128)
    def analyze_file(self, file_path: str) -> FileAnalysis:
        """Parse a Python source file and extract code entities.
        
        This method is cached to improve performance when the same file
        is analyzed multiple times.
        
        Args:
            file_path: Path to the Python file to analyze
            
        Returns:
            FileAnalysis object containing extracted information
            
        Raises:
            CodeParseError: If file parsing fails
        """
        try:
            abs_path = os.path.abspath(file_path)
            if not os.path.isfile(abs_path):
                raise CodeParseError(f"File does not exist: {file_path}")
                
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not content.strip():
                logger.warning(f"Empty file: {file_path}")
                return FileAnalysis(
                    file_path=abs_path,
                    entities=[],
                    imports=[],
                    content="",
                    _skip_validation=True
                )
                
            tree = ast.parse(content)
            entities = self._extract_entities(tree, abs_path)
            imports = self._extract_imports(tree)
            
            return FileAnalysis(
                file_path=abs_path,
                entities=entities,
                imports=imports,
                content=content,
                _skip_validation=self.skip_validation
            )
            
        except Exception as e:
            raise CodeParseError(f"Failed to parse {file_path}: {str(e)}") from e
    
    def analyze_package_dependencies(self) -> Dict[str, Set[str]]:
        """Analyze package dependencies from requirements.txt.
        
        Returns:
            Dictionary mapping packages to their dependencies
            
        Raises:
            FileNotFoundError: If requirements.txt not found
            ValueError: If requirements.txt is empty
        """
        if not os.path.exists('requirements.txt'):
            raise FileNotFoundError("requirements.txt not found")
            
        with open('requirements.txt', 'r') as f:
            content = f.read().strip()
            
        if not content:
            raise ValueError("requirements.txt is empty")
            
        dependencies: Dict[str, Set[str]] = {}
        for req in requirements.parse(content):
            pkg_name = req.name
            pkg = pkg_resources.working_set.by_key.get(pkg_name)
            if pkg:
                dependencies[pkg_name] = {dep.name for dep in pkg.requires()}
            else:
                dependencies[pkg_name] = set()
                
        return dependencies
    
    def analyze_function_calls(self, analyses: List[FileAnalysis]) -> Dict[str, Set[str]]:
        """Analyze function calls between entities.
        
        Args:
            analyses: List of FileAnalysis objects to analyze
            
        Returns:
            Dictionary mapping function names to sets of called functions
        """
        call_graph: Dict[str, Set[str]] = {}
        
        class CallVisitor(ast.NodeVisitor):
            def __init__(self, current_function: str):
                self.current_function = current_function
                self.called_functions: Set[str] = set()
                
            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Name):
                    self.called_functions.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    self.called_functions.add(node.func.attr)
                self.generic_visit(node)
        
        for analysis in analyses:
            try:
                tree = ast.parse(analysis.content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        visitor = CallVisitor(node.name)
                        visitor.visit(node)
                        call_graph[node.name] = visitor.called_functions
            except Exception as e:
                logger.warning(f"Error analyzing calls in {analysis.file_path}: {str(e)}")
                
        return call_graph
    
    def _extract_entities(self, tree: ast.AST, file_path: str) -> List[CodeEntity]:
        """Extract code entities from an AST.
        
        Args:
            tree: AST to analyze
            file_path: Path to the source file
            
        Returns:
            List of extracted CodeEntity objects
        """
        entities: List[CodeEntity] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                parent_class = None
                if node.bases:
                    base = node.bases[0]
                    if isinstance(base, ast.Name):
                        parent_class = base.id
                        
                entities.append(CodeEntity(
                    name=node.name,
                    docstring=ast.get_docstring(node) or '',
                    lineno=node.lineno,
                    type='class',
                    methods=[m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    parent_class=parent_class,
                    file_path=file_path
                ))
            elif isinstance(node, ast.FunctionDef):
                # Skip if this is a method (already handled in class processing)
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) 
                          if hasattr(parent, 'body') and node in parent.body):
                    entities.append(CodeEntity(
                        name=node.name,
                        docstring=ast.get_docstring(node) or '',
                        lineno=node.lineno,
                        type='function',
                        file_path=file_path
                    ))
                    
        return entities
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from an AST.
        
        Args:
            tree: AST to analyze
            
        Returns:
            List of imported module names
        """
        imports: List[str] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for name in node.names:
                    imports.append(f"{module}.{name.name}")
                    
        return imports 