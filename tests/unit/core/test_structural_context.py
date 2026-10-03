"""Unit tests for choosing each section's code from the project's structure."""

import textwrap

import pytest

from docgen.core.analyzer import CodeAnalyzer
from docgen.core.modules import module_root
from docgen.core.structural_context import (
    FUNCTION_CAP,
    OUTLINE_CAP,
    StructuralContext,
)

FILES = {
    "pkg/__init__.py": """
        from .app import App
        from .globals import request
        from .helpers import make_thing
    """,
    "pkg/globals.py": """
        request = object()
    """,
    "pkg/base.py": '''
        class Base:
            """Shared behavior."""

            def route(self, path):
                return path
    ''',
    "pkg/session.py": """
        class SessionBase:
            def load(self, environ):
                raise NotImplementedError


        class Session(SessionBase):
            def load(self, environ):
                return environ
    """,
    "pkg/app.py": '''
        import os

        import requests

        from .base import Base
        from .session import Session


        class App(Base):
            """The application.

            A second paragraph that outlines leave out.
            """

            session_class = Session

            def __call__(self, environ):
                self.log(environ)
                return self.handle(environ)

            def log(self, environ):
                return None

            def handle(self, environ):
                """Handle one request.

                A second paragraph that excerpts leave out.
                """
                return self.respond(environ)

            def respond(self, data):
                return requests.compat.quote(data)

            def _private(self):
                return None


        def configure():
            return os.environ.get("APP_DEBUG")
    ''',
    "pkg/helpers.py": """
        def make_thing():
            return 1
    """,
    "pkg/wsgi.py": """
        class _Pending:
            def __init__(self):
                self.items = []


        class Redirected(AssertionError):
            pass


        class Server:
            def serve(self, environ):
                _Pending()
                if not environ:
                    raise Redirected()
                return environ.get("PATH_INFO")


        def main():
            Server().serve({})
    """,
}


@pytest.fixture
def project(tmp_path):
    """Write the package and return its source directory."""
    for name, text in FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip())
    return tmp_path / "pkg"


def structure(source_dir, budget=10_000) -> StructuralContext:
    analyzer = CodeAnalyzer()
    analyses = analyzer.analyze_directory(str(source_dir))
    root = module_root(str(source_dir))
    graph = analyzer.analyze_function_calls(analyses, root=root)
    return StructuralContext(analyses, graph, root, budget=budget)


def texts(context: StructuralContext, section: str) -> list[str]:
    return [doc.page_content for doc in context.for_section(section)]


def test_data_flow_follows_the_entry_points_calls_in_order(project):
    """Data Flow gets the functions the entry point runs, in the order it runs them."""
    joined = "\n".join(texts(structure(project), "Data Flow"))

    order = [joined.find(f"def {name}(") for name in ("__call__", "handle", "respond")]
    assert -1 not in order
    assert order == sorted(order)


def test_data_flow_follows_the_calls_that_reach_the_most_code_first(project):
    """__call__ logs before it handles; handle leads somewhere, so it comes first."""
    joined = "\n".join(texts(structure(project), "Data Flow"))

    assert joined.find("def handle(") < joined.find("def log(")


def test_function_excerpt_keeps_only_the_first_docstring_paragraph(project):
    """Long docstrings are cut to their summary, so more code fits."""
    handle = next(
        t for t in texts(structure(project), "Data Flow") if "def handle(" in t
    )

    assert "Handle one request." in handle
    assert "second paragraph" not in handle
    assert "return self.respond(environ)" in handle


def test_key_classes_are_outlines_of_exported_classes_and_their_bases(project):
    """An outline shows a class's signature, summary, and public methods, not bodies."""
    outlines = texts(structure(project), "Key Classes and Functions")
    app = next(t for t in outlines if t.startswith("class App(Base):"))

    assert '"""The application."""' in app
    assert "def handle(self, environ): ..." in app
    assert "return self.respond" not in app
    assert "_private" not in app
    assert any(t.startswith("class Base:") for t in outlines)


def test_overview_starts_with_the_public_api(project):
    """The names the package exports, by module, come first in the Overview."""
    first = texts(structure(project), "Overview")[0]

    assert "pkg.app: App" in first
    assert "pkg.helpers: make_thing" in first


def test_the_api_map_includes_exported_objects(project):
    """An exported object, such as a proxy or a signal, is part of the public API too."""
    first = texts(structure(project), "Overview")[0]

    assert "pkg.globals: request" in first


def test_dependencies_get_the_third_party_imports_of_each_module(project):
    """Third-party imports are listed by module; the standard library is not."""
    imports = texts(structure(project), "Dependencies")

    assert len(imports) == 1
    assert "pkg.app: requests" in imports[0]
    assert "os" not in imports[0].split("pkg.app:")[1]


def test_integration_points_get_component_classes_and_environment_readers(project):
    """A class an exported class plugs in (session_class), its base, and code
    that reads environment variables are integration points."""
    found = texts(structure(project), "Integration Points")

    assert any(t.startswith("class Session(SessionBase):") for t in found)
    assert any(t.startswith("class SessionBase:") for t in found)
    assert any("def configure():" in t for t in found)


def test_excerpts_carry_the_file_they_come_from(project):
    """Each excerpt names its file, so the prompt can label it with its module."""
    docs = structure(project).for_section("Key Classes and Functions")
    app = next(d for d in docs if d.page_content.startswith("class App("))

    assert app.metadata["source"].endswith("pkg/app.py")


def test_excerpts_stay_within_the_budget(project):
    """An excerpt that does not fit is skipped, and smaller ones after it still go in."""
    everything = texts(structure(project), "Data Flow")
    budget = sum(len(t) for t in everything) - 1

    kept = texts(structure(project, budget=budget), "Data Flow")

    assert sum(len(t) for t in kept) <= budget
    assert 0 < len(kept) < len(everything)


def test_a_section_without_rules_gets_no_excerpts(project):
    """Optional sections are written from retrieved chunks alone."""
    assert structure(project).for_section("Migration Guidance") == []


def test_private_and_exception_classes_on_the_path_are_not_key_classes(tmp_path):
    """A private helper or an exception the path raises is not a key class."""
    (tmp_path / "wsgi.py").write_text(textwrap.dedent(FILES["pkg/wsgi.py"]).lstrip())

    outlines = texts(structure(tmp_path), "Key Classes and Functions")

    assert any(t.startswith("class Server:") for t in outlines)
    assert not any(
        t.startswith(("class _Pending", "class Redirected")) for t in outlines
    )


def test_a_wsgi_environ_argument_is_not_an_environment_variable(project):
    """Only os.environ and os.getenv count as reading environment variables."""
    found = "\n".join(texts(structure(project), "Integration Points"))

    assert "def configure():" in found
    assert "def serve(" not in found


def test_a_long_function_and_a_long_outline_are_cut_to_their_caps(tmp_path):
    """No single function or class outline can take a section's whole budget."""
    body = "\n".join(f"    value_{i} = {i}" for i in range(400))
    methods = "\n".join(
        f"    def method_{i}(self, argument_{i}): ..." for i in range(100)
    )
    (tmp_path / "big.py").write_text(
        f"def main():\n{body}\n    return helper(Big())\n\n\n"
        f"def helper(big):\n    return big\n\n\nclass Big:\n{methods}\n"
    )
    context = structure(tmp_path)

    main = next(t for t in texts(context, "Data Flow") if "def main(" in t)
    big = next(
        t for t in texts(context, "Key Classes and Functions") if "class Big" in t
    )

    assert len(main) <= FUNCTION_CAP + len("\n    ...\n")
    assert main.endswith("...\n")
    assert len(big) <= OUTLINE_CAP + len("\n    ...")
    assert big.endswith("...")


def test_the_third_party_map_is_cut_to_the_budget(project):
    """A project importing many packages still gets a map within its budget."""
    imports = texts(structure(project, budget=40), "Dependencies")

    assert len(imports) == 1
    assert len(imports[0]) <= 40
