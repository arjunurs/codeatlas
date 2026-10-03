"""Unit tests for the CodeAnalyzer class.

This module contains comprehensive tests for code analysis functionality,
including file parsing, entity extraction, and dependency analysis.
"""

import ast
import os
from unittest.mock import patch

import pytest

from docgen.core.analyzer import CodeAnalyzer
from docgen.exceptions.errors import CodeParseError
from docgen.models.code_entity import CodeEntity, EntityType
from docgen.models.file_analysis import FileAnalysis


@pytest.fixture
def analyzer():
    """Create a CodeAnalyzer instance."""
    return CodeAnalyzer(skip_validation=True)


@pytest.fixture
def sample_python_code():
    """Provide sample Python code for testing."""
    return '''"""Module docstring."""

import os
from typing import List

class TestClass:
    """Test class docstring."""
    def test_method(self, param: str) -> None:
        """Test method docstring."""
        print(param)

def test_function(x: int) -> int:
    """Test function docstring."""
    return x * 2
'''


def test_analyze_file_success(analyzer, tmp_path, sample_python_code):
    """Test successful file analysis."""
    # Create a temporary Python file
    test_file = tmp_path / "test.py"
    test_file.write_text(sample_python_code)

    # Analyze the file
    analysis = analyzer.analyze_file(str(test_file))

    # Verify analysis results
    assert analysis.file_path == str(test_file)
    assert len(analysis.entities) == 2  # TestClass and test_function

    # Verify class entity
    class_entity = next(e for e in analysis.entities if e.type == EntityType.CLASS)
    assert class_entity.name == "TestClass"
    assert class_entity.docstring == "Test class docstring."
    assert class_entity.methods == ["test_method"]

    # Verify function entity
    func_entity = next(e for e in analysis.entities if e.type == EntityType.FUNCTION)
    assert func_entity.name == "test_function"
    assert func_entity.docstring == "Test function docstring."
    assert func_entity.methods is None


def test_analyze_file_nonexistent(analyzer):
    """Test analyzing a nonexistent file."""
    with pytest.raises(CodeParseError, match="File does not exist"):
        analyzer.analyze_file("nonexistent.py")


def test_analyze_file_empty(analyzer, tmp_path):
    """Test analyzing an empty file."""
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("")

    with pytest.raises(CodeParseError, match="File is empty"):
        analyzer.analyze_file(str(empty_file))


def test_analyze_file_syntax_error(analyzer, tmp_path):
    """Test analyzing a file with syntax errors."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def bad_function(")

    with pytest.raises(CodeParseError, match="Failed to parse"):
        analyzer.analyze_file(str(bad_file))


def test_analyze_file_null_byte(analyzer, tmp_path):
    """A null byte is a parse error on every Python version.

    Python 3.12 reports it as a SyntaxError; 3.10 and 3.11 raise ValueError.
    """
    bad_file = tmp_path / "nul.py"
    bad_file.write_text("x = 1\0\n")

    with pytest.raises(CodeParseError, match="Failed to parse"):
        analyzer.analyze_file(str(bad_file))


def test_analyze_file_does_not_hide_bugs(analyzer, tmp_path):
    """An error in the analyzer itself is not reported as a parse error."""
    good_file = tmp_path / "good.py"
    good_file.write_text("x = 1\n")

    with (
        patch.object(analyzer, "_extract_entities", side_effect=RuntimeError("bug")),
        pytest.raises(RuntimeError, match=r"^bug$"),
    ):
        analyzer.analyze_file(str(good_file))


def test_analyze_directory_skips_a_file_that_fails(analyzer, tmp_path, caplog):
    """One file that cannot be analyzed is skipped; the others still are."""
    (tmp_path / "good.py").write_text("x = 1\n")
    (tmp_path / "bad.py").write_text("x = 1\n")
    real_analyze_file = analyzer.analyze_file

    def analyze_file(file_path):
        if file_path.endswith("bad.py"):
            raise RuntimeError("bug")
        return real_analyze_file(file_path)

    with patch.object(analyzer, "analyze_file", side_effect=analyze_file):
        analyses = analyzer.analyze_directory(str(tmp_path))

    assert [os.path.basename(a.file_path) for a in analyses] == ["good.py"]
    assert "Skipping" in caplog.text
    assert "RuntimeError: bug" in caplog.text


def test_analyze_directory_success(analyzer, tmp_path, sample_python_code):
    """Test successful directory analysis."""
    # Create test files
    (tmp_path / "module1.py").write_text(sample_python_code)
    (tmp_path / "module2.py").write_text(sample_python_code)
    os.makedirs(tmp_path / "subdir")
    (tmp_path / "subdir" / "module3.py").write_text(sample_python_code)

    analyses = analyzer.analyze_directory(str(tmp_path))

    assert len(analyses) == 3
    for analysis in analyses:
        assert len(analysis.entities) == 2  # TestClass and test_function
        assert any(e.name == "TestClass" for e in analysis.entities)
        assert any(e.name == "test_function" for e in analysis.entities)


def test_analyze_directory_no_files(analyzer, tmp_path):
    """Test analyzing a directory with no Python files."""
    os.makedirs(tmp_path / "empty")
    with pytest.raises(CodeParseError, match="No Python files found"):
        analyzer.analyze_directory(str(tmp_path / "empty"))


def test_analyze_directory_nonexistent(analyzer):
    """Test analyzing a nonexistent directory."""
    with pytest.raises(CodeParseError, match="Directory does not exist"):
        analyzer.analyze_directory("nonexistent")


def test_extract_entities(analyzer):
    """Test entity extraction from AST."""
    code = '''
class TestClass:
    """Test class."""
    def method1(self):
        """Method 1."""
        pass

def test_func():
    """Test function."""
    pass
'''
    tree = ast.parse(code)
    entities = analyzer._extract_entities(tree, code)

    assert len(entities) == 2
    assert any(e.name == "TestClass" and e.type == EntityType.CLASS for e in entities)
    assert any(
        e.name == "test_func" and e.type == EntityType.FUNCTION for e in entities
    )


def test_extract_imports(analyzer):
    """Test import extraction from AST."""
    code = """
import os
import sys as system
from typing import List, Optional
from .utils import helper
from . import config
from ..models.entity import Entity
from .. import shared
"""
    tree = ast.parse(code)
    imports = analyzer._extract_imports(tree)

    assert set(imports) == {
        "os",
        "sys",
        "typing.List",
        "typing.Optional",
        ".utils.helper",
        ".config",
        "..models.entity.Entity",
        "..shared",
    }


ASYNC_CODE = """async def fetch():
    return await load()


class Client:
    async def get(self):
        return await fetch()

    def close(self):
        pass
"""


def test_async_functions_are_entities(analyzer, tmp_path):
    """async def functions and methods are found like plain ones."""
    path = tmp_path / "net.py"
    path.write_text(ASYNC_CODE)

    entities = analyzer.analyze_file(str(path)).entities

    assert [(e.name, e.type) for e in entities] == [
        ("fetch", EntityType.FUNCTION),
        ("Client", EntityType.CLASS),
    ]
    assert entities[0].source.startswith("async def fetch():")
    assert entities[1].methods == ["get", "close"]


def test_async_function_calls_are_recorded(analyzer):
    """Calls made inside async functions and methods reach the call graph."""
    analysis = FileAnalysis(
        file_path="net.py",
        entities=[],
        imports=[],
        content=ASYNC_CODE,
        _skip_validation=True,
    )

    call_graph = analyzer.analyze_function_calls([analysis])

    assert call_graph["net.fetch"] == {"load"}
    assert call_graph["net.Client.get"] == {"net.fetch"}


def test_analyze_function_calls(analyzer, tmp_path):
    """Test function call analysis."""
    # Create a test file with function calls
    test_code = """def test_method():
    print('test')
    helper()

def helper():
    pass"""

    # Create a temporary file with the test code
    test_file = tmp_path / "test.py"
    test_file.write_text(test_code)

    analysis = FileAnalysis(
        file_path=str(test_file),
        entities=[
            CodeEntity(
                name="test_method",
                type=EntityType.FUNCTION,
                docstring="",
                start_line=1,
                end_line=3,
                source="def test_method():\n    print('test')\n    helper()",
            ),
            CodeEntity(
                name="helper",
                type=EntityType.FUNCTION,
                docstring="",
                start_line=5,
                end_line=6,
                source="def helper():\n    pass",
            ),
        ],
        imports=[],
        content=test_code,
        _skip_validation=True,
    )

    call_graph = analyzer.analyze_function_calls([analysis], root=str(tmp_path))

    assert isinstance(call_graph, dict)
    assert "test.test_method" in call_graph
    assert "print" in call_graph["test.test_method"]
    assert "test.helper" in call_graph["test.test_method"]
    assert "test.helper" in call_graph
    assert len(call_graph["test.helper"]) == 0


def test_analyze_function_calls_skips_a_file_that_does_not_parse(analyzer, caplog):
    """A file with a syntax error adds no calls, and the others still count."""
    broken = FileAnalysis(
        file_path="broken.py",
        entities=[],
        imports=[],
        content="def broken(",
        _skip_validation=True,
    )
    working = FileAnalysis(
        file_path="working.py",
        entities=[],
        imports=[],
        content="def caller():\n    callee()\n",
        _skip_validation=True,
    )

    call_graph = analyzer.analyze_function_calls([broken, working])

    assert call_graph == {"working.caller": {"callee"}}
    assert "broken.py" in caplog.text


def test_analyze_function_calls_does_not_hide_bugs(analyzer):
    """An error in the call analysis itself reaches the caller."""
    analysis = FileAnalysis(
        file_path="app.py",
        entities=[],
        imports=[],
        content="x = 1",
        _skip_validation=True,
    )

    with (
        patch("docgen.core.analyzer.ast.parse", side_effect=RuntimeError("bug")),
        pytest.raises(RuntimeError, match=r"^bug$"),
    ):
        analyzer.analyze_function_calls([analysis])


def call_graph_of(analyzer, root, files: dict[str, str]) -> dict[str, set[str]]:
    """Write a small project, analyze it, and return its call graph."""
    for name, code in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)
    analyses = analyzer.analyze_directory(str(root))
    return analyzer.analyze_function_calls(analyses, root=str(root))


def test_same_name_in_two_modules_is_kept_apart(analyzer, tmp_path):
    """Each module's run() keeps its own calls (they used to collide)."""
    call_graph = call_graph_of(
        analyzer,
        tmp_path,
        {
            "a.py": "def run():\n    helper()\n\n\ndef helper():\n    pass\n",
            "b.py": "def run():\n    other()\n\n\ndef other():\n    pass\n",
        },
    )

    assert call_graph == {
        "a.run": {"a.helper"},
        "a.helper": set(),
        "b.run": {"b.other"},
        "b.other": set(),
    }


def test_methods_are_named_by_class_and_self_calls_resolved(analyzer, tmp_path):
    """A method is Class.method, and self.method() leads to it."""
    code = """def area(shape):
    return shape.size()


class Square:
    def size(self):
        return self.side() ** 2

    def side(self):
        return area(self)
"""
    call_graph = call_graph_of(analyzer, tmp_path, {"shapes.py": code})

    assert call_graph == {
        "shapes.area": {"size"},
        "shapes.Square.size": {"shapes.Square.side"},
        "shapes.Square.side": {"shapes.area"},
    }


def test_imported_names_resolve_to_the_analyzed_module(analyzer, tmp_path):
    """Absolute, relative, aliased, and module imports all lead to the definition."""
    main = """from . import util
from .util import Store
from pkg.util import tool as run_tool


def run():
    run_tool()
    util.tool()
    return Store()
"""
    call_graph = call_graph_of(
        analyzer,
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/util.py": "def tool():\n    pass\n\n\nclass Store:\n    pass\n",
            "pkg/main.py": main,
        },
    )

    assert call_graph["pkg.main.run"] == {"pkg.util.tool", "pkg.util.Store"}
    assert call_graph["pkg.util.tool"] == set()


def test_absolute_import_resolves_below_the_source_root(analyzer, tmp_path):
    """In a src layout analyzed from the project root, pkg imports still resolve."""
    call_graph = call_graph_of(
        analyzer,
        tmp_path,
        {
            "src/pkg/__init__.py": "",
            "src/pkg/core.py": "def work():\n    pass\n",
            "src/pkg/cli.py": "from pkg.core import work\n\n\ndef main():\n    work()\n",
        },
    )

    assert call_graph["src.pkg.cli.main"] == {"src.pkg.core.work"}


def test_calls_through_the_class_resolve(analyzer, tmp_path):
    """Class.method() and cls.method() lead to the method, Class() to the class."""
    code = """class Config:
    @classmethod
    def load(cls):
        return cls.parse()

    @classmethod
    def parse(cls):
        pass


def main():
    Config.load()
    return Config()
"""
    call_graph = call_graph_of(analyzer, tmp_path, {"config.py": code})

    assert call_graph == {
        "config.Config.load": {"config.Config.parse"},
        "config.Config.parse": set(),
        "config.main": {"config.Config.load", "config.Config"},
    }


def test_calls_the_analyzer_cannot_place_stay_bare(analyzer, tmp_path):
    """Built-ins, other libraries, and methods on other objects keep their bare name."""
    code = """import logging

logger = logging.getLogger(__name__)


def main(items):
    print(len(items))
    logger.info("done")
    items.append(1)
"""
    call_graph = call_graph_of(analyzer, tmp_path, {"app.py": code})

    assert call_graph == {"app.main": {"print", "len", "info", "append"}}


def test_unusual_imports_and_calls_are_handled(analyzer, tmp_path):
    """Aliased, star, and out-of-tree imports, and calls with no name, do not break it."""
    code = """import os.path as osp
from ... import outside
from os import *


def main(factories):
    osp.join("a", "b")
    factories[0]()
    outside()
"""
    call_graph = call_graph_of(analyzer, tmp_path, {"app.py": code})

    assert call_graph == {"app.main": {"join", "outside"}}


def test_package_init_is_named_after_its_package(analyzer, tmp_path):
    """Functions in pkg/__init__.py belong to pkg."""
    call_graph = call_graph_of(
        analyzer, tmp_path, {"pkg/__init__.py": "def setup():\n    pass\n"}
    )

    assert call_graph == {"pkg.setup": set()}


def test_analyze_directory_with_exclude_patterns(
    analyzer, tmp_path, sample_python_code
):
    """Test directory analysis with exclude patterns."""
    # Create test files
    (tmp_path / "module1.py").write_text(sample_python_code)
    (tmp_path / "module1_test.py").write_text(sample_python_code)
    (tmp_path / "module2.py").write_text(sample_python_code)
    os.makedirs(tmp_path / "__pycache__")
    (tmp_path / "__pycache__" / "cached.py").write_text(sample_python_code)

    # Analyze with exclude patterns
    analyses = analyzer.analyze_directory(
        str(tmp_path), exclude_patterns=["*_test.py", "__pycache__"]
    )

    # Should only include module1.py and module2.py
    filenames = [os.path.basename(a.file_path) for a in analyses]
    assert "module1.py" in filenames
    assert "module2.py" in filenames
    assert "module1_test.py" not in filenames
    assert "cached.py" not in filenames
    assert len(analyses) == 2


def test_analyze_directory_with_max_files(analyzer, tmp_path, sample_python_code):
    """Test directory analysis with max_files limit."""
    # Create multiple test files
    for i in range(10):
        (tmp_path / f"module{i}.py").write_text(sample_python_code)

    # Analyze with max_files limit
    analyses = analyzer.analyze_directory(str(tmp_path), max_files=3)

    assert len(analyses) == 3


def test_analyze_directory_exclude_by_path(analyzer, tmp_path, sample_python_code):
    """Test excluding files by relative path pattern."""
    # Create nested structure
    os.makedirs(tmp_path / "tests")
    os.makedirs(tmp_path / "src")
    (tmp_path / "tests" / "test_module.py").write_text(sample_python_code)
    (tmp_path / "src" / "module.py").write_text(sample_python_code)

    # Exclude tests directory
    analyses = analyzer.analyze_directory(str(tmp_path), exclude_patterns=["tests/*"])

    filenames = [os.path.basename(a.file_path) for a in analyses]
    assert "module.py" in filenames
    assert "test_module.py" not in filenames


def test_matches_any_pattern(analyzer):
    """Test the _matches_any_pattern helper method."""
    assert analyzer._matches_any_pattern("test_foo.py", ["test_*.py"])
    assert analyzer._matches_any_pattern("foo_test.py", ["*_test.py"])
    assert analyzer._matches_any_pattern("__pycache__", ["__pycache__"])
    assert not analyzer._matches_any_pattern("module.py", ["*_test.py"])
    assert not analyzer._matches_any_pattern("main.py", ["test_*.py", "__pycache__"])


@pytest.fixture
def project_with_tool_dirs(tmp_path):
    """A project root holding real code next to virtualenvs and tool directories."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("import json\n\ndef run():\n    pass\n")
    (tmp_path / "tool.py").write_text("import yaml\n")
    for name in [
        ".venv/lib/python3.12/site-packages/requests",
        "venv/lib",
        ".git/hooks",
        "node_modules/pkg",
        "__pycache__",
        ".tox/py312",
        "build/lib",
    ]:
        directory = tmp_path / name
        directory.mkdir(parents=True)
        (directory / "vendored.py").write_text("import vendored_dep\n")
    # A virtualenv with a custom name is recognized by its pyvenv.cfg
    custom_env = tmp_path / "py312-env"
    (custom_env / "lib").mkdir(parents=True)
    (custom_env / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (custom_env / "lib" / "vendored.py").write_text("import vendored_dep\n")
    return tmp_path


def test_analyze_directory_skips_virtualenvs_and_tool_dirs(
    analyzer, project_with_tool_dirs
):
    """Virtualenvs, VCS, and tool directories are skipped by default."""
    analyses = analyzer.analyze_directory(str(project_with_tool_dirs))

    analyzed = sorted(
        os.path.relpath(a.file_path, project_with_tool_dirs) for a in analyses
    )
    assert analyzed == [os.path.join("app", "main.py"), "tool.py"]


def test_package_dependencies_skip_excluded_dirs(analyzer, project_with_tool_dirs):
    """Dependencies skip default and user-excluded directories too."""
    analyses = analyzer.analyze_directory(
        str(project_with_tool_dirs), exclude_patterns=["app"]
    )

    dependencies = analyzer.analyze_package_dependencies(
        analyses, root=str(project_with_tool_dirs)
    )

    assert "vendored_dep" not in set().union(*dependencies.values())
    assert "app" not in dependencies
    assert dependencies["tool"] == {"yaml"}


def test_package_dependencies_respect_max_files(analyzer, tmp_path):
    """Only the files that were analyzed count, so --max-files holds."""
    (tmp_path / "a.py").write_text("import json\n")
    (tmp_path / "b.py").write_text("import csv\n")
    analyses = analyzer.analyze_directory(str(tmp_path), max_files=1)

    dependencies = analyzer.analyze_package_dependencies(analyses, root=str(tmp_path))

    assert len(dependencies) == 1


def test_package_dependencies_ignore_the_current_directory(
    analyzer, tmp_path, monkeypatch
):
    """A requirements.txt where codeatlas is run from adds nothing."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("import yaml\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "requirements.txt").write_text("flask==3.0\n")
    monkeypatch.chdir(elsewhere)
    analyses = analyzer.analyze_directory(str(project))

    dependencies = analyzer.analyze_package_dependencies(analyses, root=str(project))

    assert dependencies == {"app": {"yaml"}}


def test_relative_import_adds_no_unnamed_dependency(analyzer, tmp_path):
    """A relative import names no top-level package, so it adds none."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "main.py").write_text(
        "from . import util\nfrom ..models import entity\nimport yaml\n"
    )
    analyses = analyzer.analyze_directory(str(tmp_path))

    dependencies = analyzer.analyze_package_dependencies(analyses, root=str(tmp_path))

    assert dependencies == {"pkg": {"yaml"}}


SHOP_FILES = {
    "shop/__init__.py": "",
    "shop/cli.py": "import argparse\nfrom .orders import place_order\n",
    "shop/orders.py": (
        "import json\nimport requests\nfrom .payments.gateway import charge\n"
    ),
    "shop/catalog.py": "from dataclasses import dataclass\n",
    "shop/payments/__init__.py": "",
    "shop/payments/gateway.py": "import stripe\nfrom ..catalog import Catalog\n",
}


def write_files(root, files: dict[str, str]) -> None:
    """Write a small project's files under root."""
    for name, code in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)


def test_package_dependencies_link_packages_and_skip_the_stdlib(analyzer, tmp_path):
    """Imports become package-to-package links; the standard library is left out."""
    write_files(tmp_path, SHOP_FILES)
    analyses = analyzer.analyze_directory(str(tmp_path))

    dependencies = analyzer.analyze_package_dependencies(analyses, root=str(tmp_path))

    assert dependencies == {
        "shop": {"requests", "shop.payments"},
        "shop.payments": {"shop", "stripe"},
    }


def test_module_imports_link_the_project_modules(analyzer, tmp_path):
    """Each module maps to the analyzed modules it imports, not to libraries."""
    write_files(tmp_path, SHOP_FILES)
    analyses = analyzer.analyze_directory(str(tmp_path))

    module_imports = analyzer.analyze_module_imports(analyses, root=str(tmp_path))

    assert module_imports == {
        "shop": set(),
        "shop.cli": {"shop.orders"},
        "shop.orders": {"shop.payments.gateway"},
        "shop.catalog": set(),
        "shop.payments": set(),
        "shop.payments.gateway": {"shop.catalog"},
    }
