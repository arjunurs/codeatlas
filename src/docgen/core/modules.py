"""Naming the analyzed modules, and placing imports among them.

An import refers to one of the analyzed modules, the standard library, or a
third-party package. The diagrams show the first and the last.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath

STDLIB_MODULES = frozenset(sys.stdlib_module_names)


def module_root(source_dir: str) -> str:
    """The directory module names start from, for a source directory.

    That is the source directory itself, unless it is a package (it holds an
    __init__.py): then module names start above it, and above any package it
    sits in, so --source src/pkg names its modules pkg.x, as its own imports
    do.
    """
    root = os.path.abspath(source_dir)
    while os.path.isfile(os.path.join(root, "__init__.py")):
        parent = os.path.dirname(root)
        if parent == root:
            break
        root = parent
    return root


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


def import_base(
    module: str, is_package: bool, imported: str | None, level: int
) -> str | None:
    """The absolute name a from-import reads from, or None if it is outside.

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


def unique_suffixes(names: Iterable[str]) -> dict[str, str]:
    """Map each dotted suffix that only one of the names ends with to that name.

    a.b.c has the suffixes b.c and c. An absolute import names a module from
    its own package root, which may sit below the source root (src/pkg is
    imported as pkg), so imports are also matched against these.
    """
    owners: dict[str, set[str]] = defaultdict(set)
    for name in names:
        parts = name.split(".")
        for start in range(1, len(parts)):
            owners[".".join(parts[start:])].add(name)
    return {suffix: names.pop() for suffix, names in owners.items() if len(names) == 1}


class ImportKind(Enum):
    """Where an imported name comes from."""

    INTERNAL = "internal"
    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"


@dataclass(frozen=True)
class PlacedImport:
    """Where an import comes from.

    Attributes:
        kind: The analyzed code, the standard library, or a third-party package
        name: The analyzed module, or the top-level package for other kinds
    """

    kind: ImportKind
    name: str


class ModuleIndex:
    """The analyzed modules, for telling where an import comes from."""

    def __init__(self, modules: Iterable[str]) -> None:
        self._modules = set(modules)
        self._by_suffix = unique_suffixes(self._modules)

    def place(
        self, imported: str, importer: str, importer_is_package: bool
    ) -> PlacedImport | None:
        """Place a name as an import statement writes it.

        Args:
            imported: The imported name, with a relative import's leading dots
            importer: The importing module
            importer_is_package: Whether the importer is a package __init__

        Returns:
            Where the import comes from, or None for a relative import that
            reaches outside the analyzed modules
        """
        level = len(imported) - len(imported.lstrip("."))
        if level:
            absolute = import_base(
                importer, importer_is_package, imported[level:] or None, level
            )
            module = absolute and longest_prefix(absolute, self._modules.__contains__)
            return PlacedImport(ImportKind.INTERNAL, module) if module else None

        module = longest_prefix(imported, self._modules.__contains__)
        if module:
            return PlacedImport(ImportKind.INTERNAL, module)
        top_level = imported.split(".")[0]
        # A standard-library name is checked before suffixes, so a project's
        # own utils/logging.py does not take over "import logging"
        if top_level in STDLIB_MODULES:
            return PlacedImport(ImportKind.STDLIB, top_level)
        suffix = longest_prefix(imported, self._by_suffix.__contains__)
        if suffix:
            return PlacedImport(ImportKind.INTERNAL, self._by_suffix[suffix])
        return PlacedImport(ImportKind.THIRD_PARTY, top_level)


def longest_prefix(name: str, matches: Callable[[str], bool]) -> str | None:
    """The longest dotted prefix of a name that matches, if any."""
    parts = name.split(".")
    for end in range(len(parts), 0, -1):
        prefix = ".".join(parts[:end])
        if matches(prefix):
            return prefix
    return None
