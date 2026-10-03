"""Code analysis module.

This module provides functionality for analyzing Python source code and extracting
information about code structure, dependencies, and relationships.
"""

from __future__ import annotations

import ast
import fnmatch
import logging
import os
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePath

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

    def analyze_package_dependencies(
        self, analyses: Sequence[FileAnalysis], root: str
    ) -> dict[str, set[str]]:
        """Map each package to the top-level packages its imports come from.

        A file's package is its directory relative to the source root, dotted;
        a file at the root is its own package. Only the given analyses count,
        so excluded files and files past --max-files add nothing.

        Args:
            analyses: File analysis results
            root: The source root package names start from

        Returns:
            Dictionary mapping package names to the packages they import
        """
        dependencies: dict[str, set[str]] = {}
        for analysis in analyses:
            rel_path = os.path.relpath(analysis.file_path, root)
            package_name = os.path.dirname(rel_path).replace(os.sep, ".")
            if not package_name:
                package_name = os.path.splitext(os.path.basename(rel_path))[0]

            imported = dependencies.setdefault(package_name, set())
            for imp in analysis.imports:
                top_pkg = imp.split(".")[0]
                # A relative import such as "from . import x" names no package
                if top_pkg and top_pkg != package_name:
                    imported.add(top_pkg)
        return dependencies

    def analyze_function_calls(
        self, analyses: Sequence[FileAnalysis], root: str | None = None
    ) -> dict[str, set[str]]:
        """Map each function and method to the calls it makes.

        Functions are named by module path from the source root, as in
        pkg.module.func and pkg.module.Class.method. A call is named the same
        way when it can be traced to a function or class in the analyzed code:
        one in the same module, a method called through self or cls, or a name
        imported from an analyzed module. Any other call keeps its bare name.

        Args:
            analyses: File analysis results
            root: The source root module paths start from; without it, a
                relative file path is used as given and an absolute one by
                its file name

        Returns:
            Dictionary mapping qualified function names to the calls they make
        """
        parsed = []
        for analysis in analyses:
            # Clean up the code by removing leading/trailing whitespace
            cleaned_code = analysis.content.strip()
            if not cleaned_code:
                continue
            try:
                tree = ast.parse(cleaned_code)
            except SyntaxError as e:
                logger.warning(
                    f"Syntax error analyzing function calls in {analysis.file_path}: {e}"
                )
                continue
            is_package = os.path.basename(analysis.file_path) == "__init__.py"
            module = _ModuleDefinitions.from_tree(
                module_name(analysis.file_path, root), is_package, tree
            )
            parsed.append((module, tree))

        resolver = _CallResolver([module for module, _ in parsed])
        call_graph: dict[str, set[str]] = {}
        for module, tree in parsed:
            visitor = _CallVisitor(module, resolver)
            visitor.visit(tree)
            call_graph.update(visitor.calls)
        return call_graph

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


def module_name(file_path: str, root: str | None = None) -> str:
    """Name a file by its dotted module path from the source root.

    pkg/mod.py is pkg.mod, and pkg/__init__.py is pkg. Without a root, a
    relative path is used as given and an absolute one by its file name.
    """
    if root is not None:
        file_path = os.path.relpath(file_path, root)
    elif os.path.isabs(file_path):
        file_path = os.path.basename(file_path)
    parts = list(PurePath(file_path).with_suffix("").parts)
    if len(parts) > 1 and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class _ModuleDefinitions:
    """What a module defines and imports, for resolving the calls made in it.

    Attributes:
        name: Dotted module name
        functions: Names of the module's top-level functions
        classes: Each top-level class's name, mapped to its method names
        imports: Each imported name, mapped to the qualified name it refers to
    """

    name: str
    functions: set[str]
    classes: dict[str, set[str]]
    imports: dict[str, str]

    @classmethod
    def from_tree(
        cls, name: str, is_package: bool, tree: ast.Module
    ) -> _ModuleDefinitions:
        """Collect a module's definitions and imports from its AST."""
        functions = {
            node.name for node in tree.body if isinstance(node, _FUNCTION_NODES)
        }
        classes = {
            node.name: {
                item.name for item in node.body if isinstance(item, _FUNCTION_NODES)
            }
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        imports: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        imports[alias.asname] = alias.name
                    else:
                        top_level = alias.name.split(".")[0]
                        imports[top_level] = top_level
            elif isinstance(node, ast.ImportFrom):
                base = _import_base(name, is_package, node.module, node.level)
                if base is None:
                    continue
                for alias in node.names:
                    if alias.name != "*":
                        target = f"{base}.{alias.name}" if base else alias.name
                        imports[alias.asname or alias.name] = target
        return cls(name, functions, classes, imports)


def _import_base(
    module: str, is_package: bool, imported: str | None, level: int
) -> str | None:
    """The absolute module a from-import reads from, or None if it is outside.

    from .util import x, written in pkg/main.py, reads from pkg.util.
    """
    if level == 0:
        return imported or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    if level - 1 > len(package):
        return None
    parts = package[: len(package) - (level - 1)]
    if imported:
        parts.append(imported)
    return ".".join(parts)


class _CallResolver:
    """Traces a call to the function or class in the analyzed code it reaches."""

    def __init__(self, modules: list[_ModuleDefinitions]) -> None:
        self._known: set[str] = set()
        for module in modules:
            self._known.add(module.name)
            self._known.update(f"{module.name}.{name}" for name in module.functions)
            for class_name, methods in module.classes.items():
                qualified = f"{module.name}.{class_name}"
                self._known.add(qualified)
                self._known.update(f"{qualified}.{method}" for method in methods)
        # An absolute import names a module from its own package root, which
        # may sit below the source root (src/pkg imported as pkg), so imported
        # names also match a known name by its trailing parts
        suffixes: dict[str, set[str]] = defaultdict(set)
        for qualified in self._known:
            parts = qualified.split(".")
            for start in range(1, len(parts) - 1):
                suffixes[".".join(parts[start:])].add(qualified)
        self._by_suffix = {
            suffix: names.pop() for suffix, names in suffixes.items() if len(names) == 1
        }

    def resolve(
        self, module: _ModuleDefinitions, class_name: str | None, func: ast.expr
    ) -> str | None:
        """Name the callee of a call, qualified when it can be traced.

        Args:
            module: The module the call is made in
            class_name: The class whose method makes the call, if any
            func: The call's func expression

        Returns:
            The qualified or bare callee name, or None for a call through an
            expression with no name, such as f()()
        """
        if isinstance(func, ast.Name):
            return self._owner(module, func.id) or func.id
        if not isinstance(func, ast.Attribute):
            return None
        if isinstance(func.value, ast.Name):
            receiver = func.value.id
            methods = module.classes.get(class_name, set()) if class_name else set()
            if receiver in ("self", "cls") and func.attr in methods:
                return f"{module.name}.{class_name}.{func.attr}"
            owner = self._owner(module, receiver)
            if owner and f"{owner}.{func.attr}" in self._known:
                return f"{owner}.{func.attr}"
        return func.attr

    def _owner(self, module: _ModuleDefinitions, name: str) -> str | None:
        """The known function, class, or module a name refers to in a module."""
        if name in module.functions or name in module.classes:
            return f"{module.name}.{name}"
        target = module.imports.get(name)
        if target is None:
            return None
        if target in self._known:
            return target
        return self._by_suffix.get(target)


class _CallVisitor(ast.NodeVisitor):
    """Records the calls each function in one module makes."""

    def __init__(self, module: _ModuleDefinitions, resolver: _CallResolver) -> None:
        self.calls: dict[str, set[str]] = {}
        self._module = module
        self._resolver = resolver
        self._scope = [module.name]
        self._class: str | None = None
        self._function: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class, so its methods are named after it."""
        previous_class = self._class
        # Only top-level classes are indexed, so self.x() resolves only there
        self._class = node.name if len(self._scope) == 1 else None
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()
        self._class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit a function, recording the calls in its body under its name."""
        previous_function = self._function
        self._function = ".".join([*self._scope, node.name])
        self.calls[self._function] = set()
        self._scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self._scope.pop()
        self._function = previous_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition like a plain one."""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record a call made inside a function."""
        if self._function is not None:
            callee = self._resolver.resolve(self._module, self._class, node.func)
            if callee:
                self.calls[self._function].add(callee)
        self.generic_visit(node)
