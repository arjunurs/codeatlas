"""Code analysis module.

This module provides functionality for analyzing Python source code and extracting
information about code structure, dependencies, and relationships.
"""

from __future__ import annotations

import ast
import fnmatch
import logging
import os
from collections.abc import Iterator, Sequence

from ..config import DEFAULT_CONFIG
from ..exceptions.errors import CodeParseError, FileEncodingError
from ..models.call_graph import CallGraph
from ..models.code_entity import CodeEntity, EntityType
from ..models.file_analysis import FileAnalysis
from ..utils.error_classification import describe_error
from .calls import trace_calls
from .modules import ImportKind, ModuleIndex, module_name

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
                source = f.read()
        except UnicodeDecodeError as e:
            raise FileEncodingError(
                f"Failed to decode {file_path} with encoding {self.encoding}: {e}"
            ) from e
        except OSError as e:
            raise CodeParseError(f"Failed to read {file_path}: {e}") from e

        if not source and os.path.basename(file_path) != "__init__.py":
            raise CodeParseError(f"File is empty: {file_path}")

        try:
            tree = ast.parse(source)
            entities = self._extract_entities(tree, source)
            imports = self._extract_imports(tree)

            return FileAnalysis(
                file_path=os.path.abspath(file_path),
                entities=entities,
                imports=imports,
                content=source,
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

        python_files_found = False
        analyses = []

        for file_path in self._iter_python_files(directory, exclude_patterns or []):
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

    def analyze_module_imports(
        self, analyses: Sequence[FileAnalysis], root: str
    ) -> dict[str, set[str]]:
        """Map each analyzed module to the analyzed modules it imports.

        Imports of the standard library and third-party packages are left out:
        the architecture diagram is about the project's own modules.

        Args:
            analyses: File analysis results
            root: The source root module names start from

        Returns:
            Dictionary mapping each module to the project modules it imports
        """
        modules = {a.file_path: module_name(a.file_path, root) for a in analyses}
        index = ModuleIndex(modules.values())

        module_imports: dict[str, set[str]] = {}
        for analysis in analyses:
            module = modules[analysis.file_path]
            is_package = os.path.basename(analysis.file_path) == "__init__.py"
            imported = module_imports.setdefault(module, set())
            for name in analysis.imports:
                placed = index.place(name, module, is_package)
                if (
                    placed
                    and placed.kind is ImportKind.INTERNAL
                    and placed.name != module
                ):
                    imported.add(placed.name)
        return module_imports

    def analyze_package_dependencies(
        self, analyses: Sequence[FileAnalysis], root: str
    ) -> dict[str, set[str]]:
        """Map each package to the packages its imports come from.

        A file's package is its directory relative to the source root, dotted;
        a file at the root is its own package. An import of analyzed code
        links to that code's package, and an import of a third-party package
        to its top-level name. Standard-library imports are left out. Only
        the given analyses count, so excluded files and files past
        --max-files add nothing.

        Args:
            analyses: File analysis results
            root: The source root package names start from

        Returns:
            Dictionary mapping each package to the packages it imports. A
            name that is not itself a key is a third-party package.
        """
        modules = {a.file_path: module_name(a.file_path, root) for a in analyses}
        package_of = {
            modules[a.file_path]: _package_name(a.file_path, root) for a in analyses
        }
        index = ModuleIndex(modules.values())

        dependencies: dict[str, set[str]] = {}
        for analysis in analyses:
            module = modules[analysis.file_path]
            package = package_of[module]
            is_package = os.path.basename(analysis.file_path) == "__init__.py"
            imported = dependencies.setdefault(package, set())
            for name in analysis.imports:
                placed = index.place(name, module, is_package)
                if placed is None or placed.kind is ImportKind.STDLIB:
                    continue
                if placed.kind is ImportKind.INTERNAL:
                    target = package_of[placed.name]
                else:
                    target = placed.name
                if target != package:
                    imported.add(target)
        return dependencies

    def analyze_function_calls(
        self, analyses: Sequence[FileAnalysis], root: str | None = None
    ) -> CallGraph:
        """Map each function and method to the calls it makes, in order.

        Functions are named by module path from the source root, as in
        pkg.module.func and pkg.module.Class.method. A call is named the same
        way when it can be traced to a function or class in the analyzed code:
        one in the same module, a name imported from an analyzed module, or a
        method of an object whose class is known (self, cls, or a name or
        attribute annotated with the class or assigned an instance of it),
        including a method inherited from an analyzed base class. Any other
        call keeps its bare name.
        Calls are listed in the order Python makes them (arguments before the
        call), each once.

        Args:
            analyses: File analysis results
            root: The source root module paths start from; without it, a
                relative file path is used as given and an absolute one by
                its file name

        Returns:
            The call graph: each function's calls, and the analyzed classes'
            base classes and the modules, for following calls through them
        """
        parsed = []
        for analysis in analyses:
            # An empty file is still parsed: an empty __init__.py is a module
            # that calls are traced through, as in pkg.util.tool()
            cleaned_code = analysis.content.strip()
            try:
                tree = ast.parse(cleaned_code)
            except SyntaxError as e:
                logger.warning(
                    f"Syntax error analyzing function calls in {analysis.file_path}: {e}"
                )
                continue
            is_package = os.path.basename(analysis.file_path) == "__init__.py"
            parsed.append((module_name(analysis.file_path, root), is_package, tree))
        return trace_calls(parsed)

    def _extract_entities(self, tree: ast.AST, source: str) -> list[CodeEntity]:
        """Extract code entities from an AST.

        Args:
            tree: AST to extract entities from
            source: The source code the AST was parsed from

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
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)

                # Get source code
                source_lines = ast.get_source_segment(source, node)
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

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                source_lines = ast.get_source_segment(source, node)
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
        """Extract the names a module imports from its AST.

        A relative import keeps its leading dots, as written:
        from ..models import entity is recorded as ..models.entity.

        Args:
            tree: AST to extract imports from

        Returns:
            Dotted names of the imported modules and objects
        """
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                dots = "." * node.level
                module = f"{node.module}." if node.module else ""
                imports.extend(f"{dots}{module}{alias.name}" for alias in node.names)
        return imports


def _package_name(file_path: str, root: str) -> str:
    """A file's package: its directory from the root, dotted, or its own name."""
    rel_path = os.path.relpath(file_path, root)
    package = os.path.dirname(rel_path).replace(os.sep, ".")
    return package or os.path.splitext(os.path.basename(rel_path))[0]
