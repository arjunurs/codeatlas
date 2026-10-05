"""Tests for finding a project's dependency manifests."""

import logging
from pathlib import Path

from docgen.core.manifests import (
    MAX_MANIFEST_CHARS,
    Manifest,
    add_manifests,
    find_manifests,
)

PYPROJECT = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "shop"
requires-python = ">=3.10"
dependencies = [
    "starlette>=0.40.0,<1.0.0",
    "pydantic>=2.7",
]

[project.urls]
Homepage = "https://example.com"

[project.optional-dependencies]
standard = ["httpx>=0.23"]

[dependency-groups]
tests = ["pytest>=8"]

[tool.ruff]
line-length = 88

[[tool.mypy.overrides]]
module = "shop.legacy"
"""


def _project(root: Path, files: dict[str, str]) -> Path:
    """Write files under root, creating their folders, and return root."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def test_manifest_one_level_above_the_source_is_found(tmp_path):
    """--source shop/shop finds the pyproject.toml of the checkout above it."""
    repo = _project(
        tmp_path / "repo",
        {"pyproject.toml": PYPROJECT, "shop/__init__.py": "", ".git/HEAD": ""},
    )

    manifests = find_manifests(repo / "shop")

    assert [manifest.name for manifest in manifests] == ["pyproject.toml"]


def test_nearest_directory_with_a_manifest_is_used(tmp_path):
    """A subproject's own requirements win over the repository's pyproject."""
    repo = _project(
        tmp_path / "repo",
        {
            "pyproject.toml": PYPROJECT,
            "tools/requirements.txt": "click>=8\n",
            "tools/cli/main.py": "",
        },
    )

    manifests = find_manifests(repo / "tools" / "cli")

    assert manifests == [Manifest("requirements.txt", "click>=8")]


def test_search_stops_at_the_repository_root(tmp_path):
    """A manifest outside the source's repository belongs to something else."""
    _project(
        tmp_path,
        {"pyproject.toml": PYPROJECT, "repo/.git/HEAD": "", "repo/app/main.py": ""},
    )

    assert find_manifests(tmp_path / "repo" / "app") == []


def test_worktree_git_file_also_marks_the_repository_root(tmp_path):
    """In a git worktree, .git is a file rather than a folder."""
    _project(
        tmp_path,
        {"pyproject.toml": PYPROJECT, "repo/.git": "gitdir: ..", "repo/app/x.py": ""},
    )

    assert find_manifests(tmp_path / "repo" / "app") == []


def test_pyproject_keeps_only_the_tables_that_declare_dependencies(tmp_path):
    """Tool configuration, often most of the file, is left out."""
    _project(tmp_path, {"pyproject.toml": PYPROJECT})

    [manifest] = find_manifests(tmp_path)

    assert manifest.text.splitlines()[0] == "[build-system]"
    for kept in [
        'build-backend = "hatchling.build"',
        'requires-python = ">=3.10"',
        '"starlette>=0.40.0,<1.0.0",',
        "[project.optional-dependencies]",
        'standard = ["httpx>=0.23"]',
        "[dependency-groups]",
        'tests = ["pytest>=8"]',
    ]:
        assert kept in manifest.text
    for dropped in ["project.urls", "Homepage", "tool.ruff", "line-length", "mypy"]:
        assert dropped not in manifest.text


def test_poetry_dependency_tables_are_kept(tmp_path):
    """Poetry declares dependencies in its own tables, groups and extras too."""
    _project(
        tmp_path,
        {
            "pyproject.toml": """\
[tool.poetry]
name = "shop"

[tool.poetry.dependencies]
python = "^3.10"
requests = { version = "^2.31", optional = true }

[tool.poetry.group."dev".dependencies]
pytest = "^8.0"

[tool.poetry.extras]
http = ["requests"]

[tool.black]
line-length = 100
"""
        },
    )

    [manifest] = find_manifests(tmp_path)

    for kept in ['python = "^3.10"', 'pytest = "^8.0"', 'http = ["requests"]']:
        assert kept in manifest.text
    for dropped in ['name = "shop"', "tool.black", "line-length"]:
        assert dropped not in manifest.text


def test_setup_cfg_keeps_its_install_and_extras_options(tmp_path):
    """setup.cfg declares dependencies under [options]; the rest is left out."""
    _project(
        tmp_path,
        {
            "setup.cfg": """\
[metadata]
name = shop

[options]
python_requires = >=3.9
install_requires =
    requests>=2.31

[options.extras_require]
cli = click>=8

[flake8]
max-line-length = 100
"""
        },
    )

    [manifest] = find_manifests(tmp_path)

    for kept in ["python_requires = >=3.9", "requests>=2.31", "cli = click>=8"]:
        assert kept in manifest.text
    for dropped in ["name = shop", "flake8", "max-line-length"]:
        assert dropped not in manifest.text


def test_requirements_files_are_kept_whole_after_the_project_files(tmp_path):
    """pyproject.toml and setup.cfg come first, then requirements files by name."""
    _project(
        tmp_path,
        {
            "requirements.txt": "-e .\n",
            "requirements-dev.txt": "# Tests\npytest>=8\n",
            "setup.cfg": "[options]\ninstall_requires = rich\n",
            "pyproject.toml": PYPROJECT,
            "requirements-docs.txt/README": "a folder named like a manifest",
        },
    )

    manifests = find_manifests(tmp_path)

    assert [manifest.name for manifest in manifests] == [
        "pyproject.toml",
        "setup.cfg",
        "requirements-dev.txt",
        "requirements.txt",
    ]
    assert manifests[2].text == "# Tests\npytest>=8"


def test_manifest_that_links_outside_its_directory_is_skipped(tmp_path, caplog):
    """A requirements file linked to a file elsewhere is not read.

    Its text goes into the Dependencies prompt, so a checkout could send any
    readable file to the model providers. Links inside the folder still work.
    """
    project = _project(
        tmp_path / "project",
        {"pyproject.toml": PYPROJECT, "requirements/base.txt": "click\n"},
    )
    (project / "requirements.txt").symlink_to(project / "requirements" / "base.txt")
    private = tmp_path / "notes.txt"
    private.write_text("private notes\n")
    (project / "requirements-dev.txt").symlink_to(private)

    with caplog.at_level(logging.WARNING, logger="docgen"):
        manifests = find_manifests(project)

    assert [manifest.name for manifest in manifests] == [
        "pyproject.toml",
        "requirements.txt",
    ]
    assert manifests[1].text == "click"
    assert "requirements-dev.txt" in caplog.text
    assert "outside" in caplog.text


def test_manifest_that_declares_nothing_does_not_end_the_search(tmp_path):
    """A pyproject.toml holding only tool settings is passed over."""
    _project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT,
            "app/pyproject.toml": "[tool.ruff]\nline-length = 100\n",
            "app/main.py": "",
        },
    )

    manifests = find_manifests(tmp_path / "app")

    assert [manifest.name for manifest in manifests] == ["pyproject.toml"]
    assert "starlette" in manifests[0].text


def test_unreadable_manifest_is_skipped_with_a_warning(tmp_path, monkeypatch, caplog):
    """A file that cannot be read leaves the others, and the run, unaffected."""
    _project(tmp_path, {"pyproject.toml": PYPROJECT, "requirements.txt": "click\n"})
    read_text = Path.read_text

    def fail_for_pyproject(path, *args, **kwargs):
        if path.name == "pyproject.toml":
            raise PermissionError(13, "Permission denied")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_pyproject)

    with caplog.at_level(logging.WARNING, logger="docgen"):
        manifests = find_manifests(tmp_path)

    assert manifests == [Manifest("requirements.txt", "click")]
    assert "pyproject.toml" in caplog.text
    assert "Permission denied" in caplog.text


def test_manifests_are_added_to_the_prompt_in_code_blocks():
    """The prompt keeps its text and gains each file under its name."""
    manifests = [
        Manifest("pyproject.toml", '[project]\ndependencies = ["pydantic>=2"]'),
        Manifest("setup.cfg", "[options]\ninstall_requires = rich"),
        Manifest("requirements.txt", "click>=8"),
    ]

    prompt = add_manifests("Analyze the dependencies.", manifests)

    assert prompt.startswith("Analyze the dependencies.\n\n")
    for block in [
        '### pyproject.toml\n\n```toml\n[project]\ndependencies = ["pydantic>=2"]\n```',
        "### setup.cfg\n\n```ini\n[options]\ninstall_requires = rich\n```",
        "### requirements.txt\n\n```text\nclick>=8\n```",
    ]:
        assert block in prompt


def test_prompt_is_unchanged_without_manifests():
    assert add_manifests("Analyze the dependencies.", []) == "Analyze the dependencies."


def test_manifest_text_is_cut_off_at_the_size_limit():
    """A long manifest, such as a pinned requirements file, is cut at a line."""
    line = "package-with-a-long-name==1.0.0\n"
    long_text = line * (MAX_MANIFEST_CHARS // len(line) + 50)
    manifests = [Manifest("requirements.txt", long_text), Manifest("extra.txt", "x")]

    prompt = add_manifests("Prompt.", manifests)

    assert len(prompt) < MAX_MANIFEST_CHARS + 1_000
    assert "package-with-a-long-name==1.0.0\n... (cut off)\n```" in prompt
    assert "extra.txt" not in prompt
