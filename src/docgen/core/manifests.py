"""Finding a project's dependency manifests, for the Dependencies section.

Only Python files are analyzed and indexed, so the files that declare the
project's dependencies (pyproject.toml, setup.cfg, requirements files) are
read here and added to the Dependencies prompt.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..utils.error_classification import describe_error

logger = logging.getLogger(__name__)

# How much manifest text one prompt takes, in characters, in all. FastAPI's
# dependency tables are about 5,600; a requirements file with pinned hashes
# can be many times that.
MAX_MANIFEST_CHARS = 12_000

# A TOML table or INI section header, such as [project] or [[tool.x]]. The
# name's characters exclude commas, so an array on a line of its own is not
# taken for one.
_HEADER = re.compile(r"^\s*\[\[?\s*([\w.\-\"' ]+?)\s*\]\]?\s*(?:#.*)?$")

_POETRY_TABLES = re.compile(r"tool\.poetry\.(.+\.)?dependencies|tool\.poetry\.extras")


def _is_pyproject_dependency_table(name: str) -> bool:
    return name in {
        "build-system",
        "project",
        "project.optional-dependencies",
        "dependency-groups",
    } or bool(_POETRY_TABLES.fullmatch(name))


def _is_setup_cfg_dependency_section(name: str) -> bool:
    return name in {"options", "options.extras_require"}


# The files whose dependencies are in some of their tables, with the test for
# those tables; requirements files are kept whole
_TABLE_FILES: dict[str, Callable[[str], bool]] = {
    "pyproject.toml": _is_pyproject_dependency_table,
    "setup.cfg": _is_setup_cfg_dependency_section,
}
_REQUIREMENTS_PATTERN = "requirements*.txt"

_FENCE_LANGUAGES = {".toml": "toml", ".cfg": "ini"}


@dataclass(frozen=True)
class Manifest:
    """The part of one manifest file that declares dependencies.

    Attributes:
        name: The file's name, such as pyproject.toml
        text: The tables that declare dependencies, or the whole file for a
            requirements file
    """

    name: str
    text: str


def find_manifests(source_dir: str | Path) -> list[Manifest]:
    """Find the dependency manifests of the project a source directory is in.

    They are in the source directory, or the nearest directory above it with
    a manifest that declares dependencies: --source fastapi/fastapi finds
    the pyproject.toml of the checkout. The search does not leave the
    repository, so it stops at a directory holding .git.

    Args:
        source_dir: The source directory given to the run

    Returns:
        The manifests in pyproject.toml, setup.cfg, requirements*.txt order,
        or an empty list when none is found
    """
    directory = Path(source_dir).resolve()
    while True:
        manifests = _read_manifests(directory)
        if manifests or (directory / ".git").exists() or directory.parent == directory:
            return manifests
        directory = directory.parent


def _read_manifests(directory: Path) -> list[Manifest]:
    """Read the manifests in one directory, keeping their dependency parts."""
    paths = [directory / name for name in _TABLE_FILES]
    paths += sorted(directory.glob(_REQUIREMENTS_PATTERN))

    manifests = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"Skipping dependency manifest {path}: {describe_error(e)}")
            continue
        keep = _TABLE_FILES.get(path.name)
        if keep is not None:
            text = _keep_tables(text, keep)
        text = text.strip()
        if text:
            manifests.append(Manifest(path.name, text))
    return manifests


def _keep_tables(text: str, keep: Callable[[str], bool]) -> str:
    """Keep the tables of a TOML or INI file whose header names keep accepts.

    The file is filtered as text, by its headers, since Python 3.10 has no
    TOML parser. Lines before the first header are left out.
    """
    kept = []
    keeping = False
    for line in text.splitlines():
        header = _HEADER.match(line)
        if header:
            keeping = keep(re.sub(r"[\s\"']", "", header.group(1)))
        if keeping:
            kept.append(line)
    return "\n".join(kept)


def add_manifests(prompt: str, manifests: Sequence[Manifest]) -> str:
    """Add the project's dependency manifests to a section prompt.

    The manifests take up to MAX_MANIFEST_CHARS in all: the one that reaches
    the limit is cut off at a line, and any after it are left out.

    Args:
        prompt: The section prompt
        manifests: The project's manifests, from find_manifests()

    Returns:
        The prompt with the manifests appended, or unchanged without any
    """
    if not manifests:
        return prompt

    parts = [
        f"{prompt}\n\n## Dependency Manifests\n\n"
        "The project declares its dependencies in these files (for "
        "pyproject.toml and setup.cfg, only the tables that declare "
        "dependencies are shown). Take dependency names, extras, and version "
        "constraints from them, and the code context for what each "
        "dependency is used for."
    ]
    budget = MAX_MANIFEST_CHARS
    for manifest in manifests:
        text = manifest.text
        cut = len(text) > budget
        if cut:
            head = text[:budget]
            text = head[: head.rfind("\n") + 1] + "... (cut off)"
        language = _FENCE_LANGUAGES.get(Path(manifest.name).suffix, "text")
        parts.append(f"### {manifest.name}\n\n```{language}\n{text}\n```")
        if cut:
            break
        budget -= len(text)
    return "\n\n".join(parts)
