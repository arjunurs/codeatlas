"""Code each section is given for where it sits in the project, not for its wording.

Similarity search picks the chunks that read most like a section's prompt. On Flask
that meant CLI helpers and debugging output for every section, and nothing of how a
request is handled. These excerpts come from the analysis instead: the call path
from the entry point for Data Flow, outlines of the classes the package exports for
Key Classes, the replaceable parts and environment variables for Integration
Points, and the third-party imports for Dependencies. They go first in a section's
context; similarity search fills the rest of the budget.
"""

from __future__ import annotations

import ast
import collections
import heapq
import itertools
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from langchain_core.documents import Document

from ..models.call_graph import CallGraph
from ..models.file_analysis import FileAnalysis
from .modules import ImportKind, ModuleIndex, import_base, module_name
from .sequence import choose_entry, is_test, reached

# Part of the section cache key: bump when the rules below change what is chosen
RULES_VERSION = 2

# Longest excerpt of one function, and of one class outline, in characters
FUNCTION_CAP = 2_500
OUTLINE_CAP = 1_500

# Most names considered for one section, so a large project stays quick
_MAX_CANDIDATES = 200

# Reach is only compared, so counting stops here on a large project
_REACH_CAP = 500

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class _Definition:
    """A class or function in the analyzed code."""

    node: ast.ClassDef | _FunctionNode
    analysis: FileAnalysis

    @property
    def is_class(self) -> bool:
        return isinstance(self.node, ast.ClassDef)


class StructuralContext:
    """Chooses code excerpts for each section from the project's structure.

    Args:
        analyses: The analyzed files
        graph: The calls each function makes
        root: The directory module names start from
        budget: Most characters of excerpts one section is given
    """

    def __init__(
        self,
        analyses: Sequence[FileAnalysis],
        graph: CallGraph,
        root: str,
        *,
        budget: int,
    ) -> None:
        self._graph = graph
        self._root = root
        self._budget = budget
        self._analyses = [a for a in analyses if not is_test(self._module(a))]
        self._definitions = self._index_definitions()
        self._modules = ModuleIndex(self._module(a) for a in analyses)
        # Every section that uses the path reads this; worked out once, here
        self._path = list(itertools.islice(self._walk_from_entry(), _MAX_CANDIDATES))

    def for_section(self, section: str) -> list[Document]:
        """The excerpts for a section, most important first, within the budget.

        Args:
            section: The section's title

        Returns:
            Documents whose source is the file each excerpt comes from; empty
            for a section without rules
        """
        candidates = self._candidates(section.lower())
        excerpts, used, seen = [], 0, set()
        for count, (key, document) in enumerate(candidates):
            if count >= _MAX_CANDIDATES:
                break
            text = document.page_content
            if key in seen or not text or used + len(text) > self._budget:
                continue
            seen.add(key)
            excerpts.append(document)
            used += len(text)
        return excerpts

    def _candidates(self, section: str) -> Iterator[tuple[str, Document]]:
        """Everything a section could be given, in priority order."""
        if section == "overview":
            yield from self._api_map()
            yield from self._functions(self._entry_path(), limit=2)
            yield from self._outlines(self._key_classes())
        elif section == "dependencies":
            yield from self._third_party_map()
        elif section == "key classes and functions":
            yield from self._outlines(self._key_classes())
        elif section == "data flow":
            yield from self._functions(self._entry_path())
        elif section == "integration points":
            yield from self._api_map()
            yield from self._functions(self._entry_path(), limit=2)
            yield from self._outlines(self._component_classes())
            yield from self._functions(self._environment_readers())

    # Choosing names

    def _entry_path(self) -> list[str]:
        """The entry point and the functions it runs, in walk order."""
        return self._path

    def _walk_from_entry(self) -> Iterator[str]:
        """The entry point, then the functions it runs, the one reaching the most
        code first, ties in call order: on codeatlas, generate_documentation
        before the argument parsing main also calls."""
        entry = choose_entry(self._graph)
        if entry is None:
            return
        callees = {f: list(reached(self._graph, f)) for f in self._graph.calls}
        reach: dict[str, int] = {}
        order = itertools.count()
        pending = [(0, next(order), entry)]
        seen = {entry}
        while pending:
            _, _, function = heapq.heappop(pending)
            yield function
            for callee in callees.get(function, []):
                if callee not in seen and not is_test(callee):
                    seen.add(callee)
                    if callee not in reach:
                        reach[callee] = _reach(callee, callees)
                    heapq.heappush(pending, (-reach[callee], next(order), callee))

    def _key_classes(self) -> list[str]:
        """The exported classes (or the most used ones), their analyzed bases, and
        the classes whose methods the entry point runs."""
        classes = [n for n in self._exports() if self._is_class(n)]
        if not classes:
            classes = self._most_used_classes()
        owners = [
            owner
            for owner in (f.rsplit(".", 1)[0] for f in self._entry_path())
            if self._is_class(owner) and self._is_main_class(owner)
        ]
        chosen: list[str] = []
        for name in classes + owners:
            for each in [name, *self._graph.classes.get(name, [])]:
                if self._is_class(each) and each not in chosen:
                    chosen.append(each)
        return chosen

    def _component_classes(self) -> list[str]:
        """Classes a key class plugs in through a class attribute, such as
        session_interface = SecureCookieSessionInterface(), with their bases:
        the parts an application replaces to change behavior."""
        chosen: list[str] = []
        for name in self._key_classes():
            definition = self._definitions[name]
            module = self._module(definition.analysis)
            for statement in definition.node.body:
                value = getattr(statement, "value", None)
                if not isinstance(statement, ast.Assign | ast.AnnAssign):
                    continue
                target = value.func if isinstance(value, ast.Call) else value
                if not isinstance(target, ast.Name):
                    continue
                component = self._resolve(module, target.id, definition.analysis)
                if component is None:
                    continue
                for each in [component, *self._graph.classes.get(component, [])]:
                    if self._is_class(each) and each not in chosen:
                        chosen.append(each)
        return chosen

    def _environment_readers(self) -> list[str]:
        """Functions that read environment variables, in module order."""
        readers = []
        for name, definition in self._definitions.items():
            if definition.is_class:
                continue
            for node in ast.walk(definition.node):
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr in _ENVIRONMENT
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                ):
                    readers.append(name)
                    break
        return readers

    def _exports(self) -> list[str]:
        """The classes and functions the top-level package re-exports."""
        return [name for name in self._exported_names() if name in self._definitions]

    def _exported_names(self) -> list[str]:
        """Everything of its own the top-level package re-exports: classes and
        functions, but also objects such as Flask's request proxy and signals."""
        names = []
        for analysis in self._top_packages():
            module = self._module(analysis)
            for imported in analysis.imports:
                placed = self._modules.place(imported, module, True)
                if placed is None or placed.kind is not ImportKind.INTERNAL:
                    continue
                name = self._absolute(imported, module, is_package=True)
                if name and name not in names:
                    names.append(name)
        return names

    def _most_used_classes(self) -> list[str]:
        """Classes, other than private helpers and exceptions, by how many
        functions outside them create or call them."""
        uses: collections.Counter[str] = collections.Counter()
        for caller, callees in self._graph.calls.items():
            for callee in set(callees):
                owner = (
                    callee
                    if callee in self._graph.classes
                    else callee.rsplit(".", 1)[0]
                )
                if (
                    self._is_class(owner)
                    and self._is_main_class(owner)
                    and not caller.startswith(owner + ".")
                ):
                    uses[owner] += 1
        return [name for name, _ in uses.most_common(10)]

    # Building excerpts

    def _functions(
        self, names: Iterator[str] | list[str], limit: int | None = None
    ) -> Iterator[tuple[str, Document]]:
        given = 0
        for name in names:
            definition = self._definitions.get(name)
            if definition is None or definition.is_class:
                continue
            yield (
                name,
                self._document(_function_source(definition), definition.analysis),
            )
            given += 1
            if limit is not None and given >= limit:
                return

    def _outlines(self, names: list[str]) -> Iterator[tuple[str, Document]]:
        for name in names:
            definition = self._definitions[name]
            yield (
                name,
                self._document(_class_outline(definition.node), definition.analysis),
            )

    def _api_map(self) -> Iterator[tuple[str, Document]]:
        packages = self._top_packages()
        by_module: dict[str, list[str]] = {}
        for name in self._exported_names():
            if "." not in name:
                continue
            module, short = name.rsplit(".", 1)
            by_module.setdefault(module, []).append(short)
        if packages and by_module:
            lines = ["Names the package exports, by the module that defines them:"]
            lines += [
                f"{module}: {', '.join(names)}" for module, names in by_module.items()
            ]
            yield "api", self._document("\n".join(lines), packages[0])

    def _third_party_map(self) -> Iterator[tuple[str, Document]]:
        lines = ["Third-party imports, by module:"]
        for analysis in sorted(self._analyses, key=self._module):
            module = self._module(analysis)
            is_package = analysis.file_path.endswith("__init__.py")
            outside = [
                imported
                for imported in analysis.imports
                if (placed := self._modules.place(imported, module, is_package))
                and placed.kind is ImportKind.THIRD_PARTY
            ]
            if outside:
                lines.append(f"{module}: {', '.join(dict.fromkeys(outside))}")
        if len(lines) > 1:
            text = "\n".join(lines)
            if len(text) > self._budget:
                text = text[: self._budget].rsplit("\n", 1)[0]
            yield "imports", Document(page_content=text)

    # Helpers

    def _index_definitions(self) -> dict[str, _Definition]:
        definitions: dict[str, _Definition] = {}
        for analysis in self._analyses:
            try:
                tree = ast.parse(analysis.content)
            # A file the analyzer read but Python cannot parse here (or one
            # nested too deeply) gives no excerpts; the rest still do
            except (SyntaxError, ValueError, RecursionError):
                continue
            stack: list[tuple[ast.AST, str]] = [(tree, self._module(analysis))]
            while stack:
                parent, prefix = stack.pop()
                for child in ast.iter_child_nodes(parent):
                    if isinstance(child, ast.ClassDef | _FunctionNode):
                        name = f"{prefix}.{child.name}"
                        definitions[name] = _Definition(child, analysis)
                        if isinstance(child, ast.ClassDef):
                            stack.append((child, name))
        return definitions

    def _top_packages(self) -> list[FileAnalysis]:
        packages = [a for a in self._analyses if a.file_path.endswith("__init__.py")]
        if not packages:
            return []
        depth = min(self._module(a).count(".") for a in packages)
        return [a for a in packages if self._module(a).count(".") == depth]

    def _absolute(self, imported: str, module: str, *, is_package: bool) -> str | None:
        level = len(imported) - len(imported.lstrip("."))
        if level:
            return import_base(module, is_package, imported[level:] or None, level)
        return imported

    def _resolve(self, module: str, name: str, analysis: FileAnalysis) -> str | None:
        """The class a bare name means in a module: its own, or one it imports."""
        if self._is_class(f"{module}.{name}"):
            return f"{module}.{name}"
        is_package = analysis.file_path.endswith("__init__.py")
        for imported in analysis.imports:
            if imported.rsplit(".", 1)[-1] == name:
                absolute = self._absolute(imported, module, is_package=is_package)
                if absolute and self._is_class(absolute):
                    return absolute
        return None

    def _is_main_class(self, name: str) -> bool:
        """Whether a class the entry point uses is worth an outline: not a
        private helper, and not an exception it may raise."""
        node = self._definitions[name].node
        if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
            return False
        bases = [ast.unparse(base).rsplit(".", 1)[-1] for base in node.bases]
        return not any(base.endswith(_EXCEPTION_SUFFIXES) for base in bases)

    def _is_class(self, name: str) -> bool:
        definition = self._definitions.get(name)
        return definition is not None and definition.is_class

    def _module(self, analysis: FileAnalysis) -> str:
        return module_name(analysis.file_path, self._root)

    def _document(self, text: str, analysis: FileAnalysis) -> Document:
        return Document(page_content=text, metadata={"source": analysis.file_path})


def _reach(function: str, callees: dict[str, list[str]]) -> int:
    """How many functions a function reaches, counting up to _REACH_CAP."""
    seen = {function}
    pending = [function]
    while pending and len(seen) <= _REACH_CAP:
        for callee in callees.get(pending.pop(), []):
            if callee not in seen:
                seen.add(callee)
                pending.append(callee)
    return len(seen) - 1


# os.environ and os.getenv; a bare "environ" is often a WSGI environment
_ENVIRONMENT = frozenset({"environ", "getenv"})
_EXCEPTION_SUFFIXES = ("Error", "Exception", "Warning")


def _first_paragraph(docstring: str | None) -> str:
    return (docstring or "").strip().split("\n\n")[0]


def _function_source(definition: _Definition) -> str:
    """A function's source with its docstring cut to the first paragraph."""
    node = definition.node
    source = (
        ast.get_source_segment(definition.analysis.content, node, padded=True) or ""
    )
    first = node.body[0] if node.body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
        and first.end_lineno is not None
    ):
        lines = source.splitlines(keepends=True)
        start, end = first.lineno - node.lineno, first.end_lineno - node.lineno
        indent = " " * first.col_offset
        summary = _first_paragraph(ast.get_docstring(node)).splitlines()
        kept = ""
        if summary:
            body = "\n".join([summary[0], *(indent + line for line in summary[1:])])
            kept = f'{indent}"""{body}"""\n'
        source = "".join(lines[:start]) + kept + "".join(lines[end + 1 :])
    if len(source) > FUNCTION_CAP:
        source = source[:FUNCTION_CAP].rsplit("\n", 1)[0] + "\n    ...\n"
    return source


def _class_outline(node: ast.ClassDef | _FunctionNode) -> str:
    """A class's signature, docstring summary, and public method signatures."""
    assert isinstance(node, ast.ClassDef)
    bases = ", ".join(ast.unparse(base) for base in node.bases)
    lines = [f"class {node.name}({bases}):" if bases else f"class {node.name}:"]
    summary = _first_paragraph(ast.get_docstring(node)).splitlines()
    if summary:
        body = "\n".join([summary[0], *(f"    {line}" for line in summary[1:])])
        lines.append(f'    """{body}"""')
    for child in node.body:
        if isinstance(child, _FunctionNode) and (
            not child.name.startswith("_") or child.name == "__init__"
        ):
            keyword = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
            lines.append(f"    {keyword} {child.name}({ast.unparse(child.args)}): ...")
    outline = "\n".join(lines)
    if len(outline) > OUTLINE_CAP:
        outline = outline[:OUTLINE_CAP].rsplit("\n", 1)[0] + "\n    ..."
    return outline
