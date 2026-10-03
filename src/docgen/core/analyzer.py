"""Code analysis module.

This module provides functionality for analyzing Python source code and extracting
information about code structure, dependencies, and relationships.
"""

import ast
import fnmatch
import logging
import os
from collections.abc import Iterator

from ..config import DEFAULT_CONFIG
from ..exceptions.errors import CodeParseError, FileEncodingError
from ..models.code_entity import CodeEntity, EntityType
from ..models.file_analysis import FileAnalysis
from ..utils.error_classification import describe_error

logger = logging.getLogger(__name__)

# Directories never analyzed: virtualenvs, version control, build output, and
# tool caches (modeled on ruff's default excludes). A directory containing
# pyvenv.cfg is also skipped, which catches virtualenvs with custom names.
DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".bzr",
        ".direnv",
        ".docgen_cache",
        ".eggs",
        ".git",
        ".hg",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "__pypackages__",
        "_build",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)


class CodeAnalyzer:
    """Analyzes Python source code to extract code entities and relationships."""

    def __init__(self, skip_validation: bool = False, encoding: str | None = None):
        """Initialize the code analyzer.

        Args:
            skip_validation: If True, skip validation in FileAnalysis
            encoding: File encoding to use (defaults to config setting)
        """
        self.skip_validation = skip_validation
        self.encoding = encoding or DEFAULT_CONFIG.DEFAULT_FILE_ENCODING
        self._source: str | None = None
        self._analyzed_directory: str | None = None
        self._exclude_patterns: list[str] = []

    def analyze_file(self, file_path: str) -> FileAnalysis:
        """Analyze a single Python file.

        Args:
            file_path: Path to the Python file to analyze

        Returns:
            FileAnalysis object containing the analysis results

        Raises:
            CodeParseError: If file cannot be read or parsed
        """
        if not os.path.exists(file_path):
            raise CodeParseError(f"File does not exist: {file_path}")

        try:
            with open(file_path, encoding=self.encoding) as f:
                self._source = f.read()
        except UnicodeDecodeError as e:
            raise FileEncodingError(
                f"Failed to decode {file_path} with encoding {self.encoding}: {e}"
            ) from e
        except OSError as e:
            raise CodeParseError(f"Failed to read {file_path}: {e}") from e

        if not self._source and os.path.basename(file_path) != "__init__.py":
            raise CodeParseError(f"File is empty: {file_path}")

        try:
            tree = ast.parse(self._source)
            entities = self._extract_entities(tree, file_path)
            imports = self._extract_imports(tree)

            return FileAnalysis(
                file_path=os.path.abspath(file_path),
                entities=entities,
                imports=imports,
                content=self._source,
                _skip_validation=self.skip_validation,
            )
        # ValueError covers a null byte on Python 3.10 and 3.11 (a SyntaxError
        # from 3.12) and the FileAnalysis and CodeEntity checks
        except (SyntaxError, ValueError) as e:
            raise CodeParseError(f"Failed to parse {file_path}: {e}") from e

    def analyze_directory(
        self,
        directory: str,
        exclude_patterns: list[str] | None = None,
        max_files: int | None = None,
    ) -> list[FileAnalysis]:
        """Analyze all Python files in a directory.

        Args:
            directory: Path to directory to analyze
            exclude_patterns: Optional list of glob patterns to exclude files/dirs
            max_files: Optional maximum number of files to analyze

        Returns:
            List of FileAnalysis objects

        Raises:
            CodeParseError: If directory cannot be read or contains no Python files
        """
        if not os.path.exists(directory):
            raise CodeParseError(f"Directory does not exist: {directory}")

        if not os.path.isdir(directory):
            raise CodeParseError(f"Not a directory: {directory}")

        # Store the analyzed directory and excludes for use in other methods
        self._analyzed_directory = os.path.abspath(directory)
        self._exclude_patterns = exclude_patterns or []

        python_files_found = False
        analyses = []

        for file_path in self._iter_python_files(directory, self._exclude_patterns):
            python_files_found = True
            try:
                analysis = self.analyze_file(file_path)
                analyses.append(analysis)

                # Check max_files limit
                if max_files is not None and len(analyses) >= max_files:
                    logger.info(f"Reached max_files limit ({max_files})")
                    return analyses
            # Per-file boundary: one file the analyzer cannot handle, for any
            # reason, is skipped so the rest of the codebase is still documented
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Skipping {file_path}: {describe_error(e)}")

        if not python_files_found:
            raise CodeParseError(f"No Python files found in {directory}")

        return analyses

    def _iter_python_files(
        self, directory: str, exclude_patterns: list[str]
    ) -> Iterator[str]:
        """Yield paths of Python files under a directory, skipping excluded ones.

        Skips the default excluded directories, any virtualenv (a directory
        containing pyvenv.cfg), and anything matching the given glob patterns
        by name or by path relative to the directory.

        Args:
            directory: Directory to walk
            exclude_patterns: Glob patterns for files and directories to skip

        Yields:
            Paths of Python files to analyze
        """
        for root, dirs, files in os.walk(directory):
            # Prune excluded directories (modifying dirs in place affects os.walk)
            dirs[:] = [
                d
                for d in dirs
                if d not in DEFAULT_EXCLUDED_DIRS
                and not os.path.isfile(os.path.join(root, d, "pyvenv.cfg"))
                and not self._matches_any_pattern(d, exclude_patterns)
                and not self._matches_any_pattern(
                    os.path.relpath(os.path.join(root, d), directory),
                    exclude_patterns,
                )
            ]

            for file in files:
                if not file.endswith(".py"):
                    continue

                rel_path = os.path.relpath(os.path.join(root, file), directory)
                if self._matches_any_pattern(file, exclude_patterns):
                    logger.debug(f"Excluding file by name: {rel_path}")
                    continue
                if self._matches_any_pattern(rel_path, exclude_patterns):
                    logger.debug(f"Excluding file by path: {rel_path}")
                    continue

                yield os.path.join(root, file)

    def _matches_any_pattern(self, name: str, patterns: list[str]) -> bool:
        """Check if a name matches any of the given glob patterns.

        Args:
            name: File or directory name to check
            patterns: List of glob patterns

        Returns:
            True if name matches any pattern
        """
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    def analyze_dependencies(
        self, requirements_path: str = "requirements.txt"
    ) -> dict[str, set[str]]:
        """Analyze package dependencies from requirements.txt.

        Args:
            requirements_path: Path to requirements.txt file

        Returns:
            Dictionary mapping packages to their dependencies

        Raises:
            FileNotFoundError: If requirements.txt is not found
            ValueError: If requirements.txt is empty
        """
        if not os.path.exists(requirements_path):
            raise FileNotFoundError(f"Requirements file not found: {requirements_path}")

        with open(requirements_path, encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            raise ValueError("Requirements file is empty")

        dependencies = {}
        version_separators = [">=", "==", ">", "<", "<=", "~=", "!="]

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Extract package name by finding version separator
            package = line
            for sep in version_separators:
                if sep in line:
                    package = line.split(sep)[0].strip()
                    break

            if package:
                dependencies[package] = set()

        return dependencies

    def analyze_package_dependencies(self) -> dict[str, set[str]]:
        """Analyze package dependencies between Python modules.

        Returns:
            Dictionary mapping module names to their dependencies
        """
        try:
            # Try to analyze requirements.txt first
            dependencies = self.analyze_dependencies()
        except (FileNotFoundError, ValueError):
            dependencies = {}

        # Use the analyzed directory if available, otherwise fall back to current working directory
        search_directory = self._analyzed_directory or os.getcwd()

        # Add package dependencies from imports
        for file_path in self._iter_python_files(
            search_directory, self._exclude_patterns
        ):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content)
                imports = self._extract_imports(tree)

                # Get package name from file path relative to the search directory
                rel_path = os.path.relpath(file_path, search_directory)
                package_name = os.path.dirname(rel_path).replace(os.sep, ".")
                if not package_name:
                    package_name = os.path.splitext(os.path.basename(file_path))[0]

                # Add dependencies
                if package_name not in dependencies:
                    dependencies[package_name] = set()

                for imp in imports:
                    # Get top-level package name
                    top_pkg = imp.split(".")[0]
                    if top_pkg != package_name:
                        dependencies[package_name].add(top_pkg)

            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Error reading {file_path}: {e}")
                continue
            except (SyntaxError, ValueError) as e:
                logger.warning(f"Error parsing {file_path}: {e}")
                continue

        return dependencies

    def analyze_function_calls(
        self, analyses: list[FileAnalysis]
    ) -> dict[str, set[str]]:
        """Analyze function call relationships between entities.

        Args:
            analyses: List of file analysis results

        Returns:
            Dictionary mapping function names to called functions
        """
        call_graph = {}

        class FunctionCallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.calls = {}

            def visit_FunctionDef(self, node):
                """Visit a function definition node."""
                # Store the current function name
                prev_function = self.current_function
                self.current_function = node.name

                # Initialize empty set for this function's calls
                self.calls[self.current_function] = set()

                # Visit all the nodes in the function body
                for child in node.body:
                    self.visit(child)

                # Restore previous function context
                self.current_function = prev_function

            def visit_Call(self, node):
                """Visit a function call node."""
                if not self.current_function:
                    return

                # Handle direct function calls
                if isinstance(node.func, ast.Name):
                    self.calls[self.current_function].add(node.func.id)
                # Handle method calls
                elif isinstance(node.func, ast.Attribute):
                    self.calls[self.current_function].add(node.func.attr)

                # Visit any nested calls
                self.generic_visit(node)

        for analysis in analyses:
            try:
                # Clean up the code by removing leading/trailing whitespace
                cleaned_code = analysis.content.strip()
                if not cleaned_code:
                    continue

                tree = ast.parse(cleaned_code)
                visitor = FunctionCallVisitor()
                visitor.visit(tree)

                # Update call graph with all functions and their calls
                call_graph.update(visitor.calls)

            except SyntaxError as e:
                logger.warning(
                    f"Syntax error analyzing function calls in {analysis.file_path}: {e}"
                )

        return call_graph

    def _extract_entities(self, tree: ast.AST, file_path: str) -> list[CodeEntity]:
        """Extract code entities from an AST.

        Args:
            tree: AST to extract entities from
            file_path: Path to the source file

        Returns:
            List of CodeEntity objects
        """
        entities = []

        # Only process top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node) or ""
                methods = []

                # Extract method names
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)

                # Get source code
                source_lines = ast.get_source_segment(self._source, node)
                if source_lines is None:
                    source_lines = ""

                # Get parent class if any
                parent_class = None
                if node.bases:
                    parent_class = ast.unparse(node.bases[0])

                entities.append(
                    CodeEntity(
                        name=node.name,
                        type=EntityType.CLASS,
                        docstring=docstring,
                        methods=methods,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        source=source_lines,
                        parent_class=parent_class,
                    )
                )

            elif isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node) or ""
                source_lines = ast.get_source_segment(self._source, node)
                if source_lines is None:
                    source_lines = ""

                entities.append(
                    CodeEntity(
                        name=node.name,
                        type=EntityType.FUNCTION,
                        docstring=docstring,
                        methods=None,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        source=source_lines,
                    )
                )

        return entities

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from an AST.

        Args:
            tree: AST to extract imports from

        Returns:
            List of import statements
        """
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}" for alias in node.names)
        return imports
