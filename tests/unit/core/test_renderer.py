"""Unit tests for DocumentationRenderer."""

import re
from unittest.mock import Mock

import jinja2
import pytest

from docgen.core.renderer import DIAGRAM_PAGES, DocumentationRenderer
from docgen.exceptions.errors import DocumentationError, PathValidationError
from docgen.templates.html import get_template_manager

SAFE_HTML = (
    "<h2>Setup</h2>"
    "<table><thead><tr><th>a</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>"
    "<pre><code>x = 1 &lt; 2</code></pre>"
    '<p><a href="https://example.com">docs</a></p>'
)
INJECTED_HTML = (
    "<script>alert(1)</script>"
    '<img src="x" onerror="alert(2)">'
    '<a href="javascript:alert(3)">click</a>'
)


@pytest.fixture
def rendered(tmp_path):
    """Render docs whose section and diagram contain injected markup."""
    renderer = DocumentationRenderer(get_template_manager())
    documentation = {
        "title": "Docs",
        "generated_date": "2026-10-02 12:00:00",
        "sections": [
            {"title": "Overview", "content": SAFE_HTML + INJECTED_HTML},
            {
                "title": "Dependencies",
                "content": "*Error generating this section: <img src=x onerror=alert(4)>*",
            },
        ],
    }
    diagrams = {"architecture": 'graph TD\n    a["</pre><script>alert(5)</script>"]'}
    renderer.render(documentation, diagrams, str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    "page", ["sections/overview.html", "sections/dependencies.html", "index.html"]
)
def test_section_html_is_sanitized(rendered, page):
    """Scripts, event handlers, and javascript: URLs are stripped from sections."""
    html = (rendered / page).read_text()

    for payload in ("alert(1)", "alert(2)", "alert(3)", "alert(4)"):
        assert payload not in html


def test_ordinary_markdown_html_survives(rendered):
    """Headings, tables, code blocks, and links are kept."""
    html = (rendered / "sections/overview.html").read_text()

    assert "<h2>Setup</h2>" in html
    assert "<td>1</td>" in html
    assert "<pre><code>x = 1 &lt; 2</code></pre>" in html
    assert 'href="https://example.com"' in html


def convert(markdown_text: str) -> str:
    """Convert section Markdown the way the section orchestrator does."""
    renderer = DocumentationRenderer(get_template_manager())
    return renderer.convert_markdown_to_html(markdown_text)


def test_markdown_tables_and_code_blocks_convert():
    """Tables and fenced code blocks become HTML tables and code blocks."""
    html = convert("| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\nx = 1 < 2\n```\n")

    assert "<td>1</td>" in html
    assert re.search(r"<pre><code[^>]*>x = 1 &lt; 2\n</code></pre>", html)


@pytest.mark.parametrize(
    "markdown_text",
    [
        "- a\n  - b\n- c\n",  # two-space indent, as the model writes it
        "1. a\n   - b\n2. c\n",  # under a numbered item
        "- a\n    - b\n- c\n",  # four-space indent
    ],
    ids=["two-space", "numbered-parent", "four-space"],
)
def test_indented_list_item_renders_nested(markdown_text):
    """A sub-item indented to its parent's text is nested, not a sibling."""
    html = convert(markdown_text)

    assert re.search(r"<li>a\s*<ul>\s*<li>b</li>\s*</ul>\s*</li>", html)


def test_code_block_inside_a_list_item_stays_in_the_item():
    """A fenced block indented under a numbered step belongs to that step."""
    html = convert("1. Step\n\n   ```python\n   x = 1\n   ```\n2. Next\n")

    assert re.search(r"<li>\s*<p>Step</p>\s*<pre><code[^>]*>x = 1\n</code></pre>", html)
    assert re.search(r"<li>\s*<p>Next</p>\s*</li>", html)


def test_diagram_code_is_escaped(rendered):
    """Names in diagram code cannot close the <pre> and inject markup."""
    html = (rendered / "diagrams/architecture.html").read_text()

    assert "<script>alert(5)</script>" not in html
    assert "&lt;/pre&gt;&lt;script&gt;alert(5)&lt;/script&gt;" in html


def test_mermaid_uses_strict_security_level(rendered):
    """Mermaid runs in strict mode, which encodes labels and disables click handlers."""
    html = (rendered / "diagrams/architecture.html").read_text()

    assert "securityLevel: 'strict'" in html
    assert "securityLevel: 'loose'" not in html


def test_generate_navigation_passes_titles_active_page_and_base_url():
    """Navigation is rendered from the section titles, the active page, the
    diagram pages, and the base URL."""
    navigation = Mock(render=Mock(return_value="<nav>Test Navigation</nav>"))
    renderer = DocumentationRenderer(Mock(templates={"navigation": navigation}))
    sections = [{"title": "Overview"}, {"title": "Dependencies"}]
    pages = [DIAGRAM_PAGES[0]]

    nav_html = renderer.generate_navigation("Overview", sections, "./", pages)

    assert nav_html == "<nav>Test Navigation</nav>"
    navigation.render.assert_called_once_with(
        active="Overview",
        sections=["Overview", "Dependencies"],
        diagrams=pages,
        base_url="./",
    )


MINIMAL_DOCUMENTATION = {"title": "Docs", "generated_date": "today", "sections": []}


@pytest.fixture
def diagrams_only(tmp_path):
    """Render a site with no sections and only the sequence and class diagrams."""
    renderer = DocumentationRenderer(get_template_manager())
    diagrams = {
        "sequence": "sequenceDiagram\n    participant a as A",
        "class_diagram": "classDiagram\n    class A",
    }
    renderer.render(MINIMAL_DOCUMENTATION, diagrams, str(tmp_path))
    return tmp_path


def diagram_links(html: str) -> list[str]:
    """The diagram pages a page links to, in order."""
    return re.findall(r'href="[./]*diagrams/(\w+)\.html"', html)


def test_only_generated_diagrams_are_linked(diagrams_only):
    """The index and the sidebar link to the diagrams that exist, and no others."""
    index = (diagrams_only / "index.html").read_text()
    page = (diagrams_only / "diagrams" / "sequence.html").read_text()

    # Once in the sidebar and once in the index's diagram list
    assert diagram_links(index) == ["classes", "sequence"] * 2
    assert diagram_links(page) == ["classes", "sequence"]
    assert sorted(p.name for p in (diagrams_only / "diagrams").iterdir()) == [
        "classes.html",
        "sequence.html",
    ]


def test_no_sections_means_no_documentation_list(diagrams_only):
    """With no sections, neither the index nor the sidebar lists documentation."""
    index = (diagrams_only / "index.html").read_text()

    assert ">Documentation<" not in index
    assert "fa-book" not in index


def test_a_diagram_page_is_marked_current_in_the_sidebar(diagrams_only):
    """The sidebar highlights the diagram being viewed, and only that one."""
    page = (diagrams_only / "diagrams" / "sequence.html").read_text()

    current = re.findall(
        r'href="\.\./diagrams/(\w+)\.html"\s+class="nav-item active"', page
    )
    assert current == ["sequence"]
    assert page.count('aria-current="page"') == 1


def test_site_has_no_search(diagrams_only):
    """The site has no search box and no search page."""
    index = (diagrams_only / "index.html").read_text()

    assert not (diagrams_only / "search.html").exists()
    assert 'type="search"' not in index
    assert "search" not in index.lower()


def test_overview_card_shows_only_the_overview(tmp_path):
    """Without an Overview section, the index shows no overview card."""
    renderer = DocumentationRenderer(get_template_manager())
    documentation = {
        **MINIMAL_DOCUMENTATION,
        "sections": [{"title": "Dependencies", "content": "<p>Uses yaml.</p>"}],
    }

    renderer.render(documentation, {}, str(tmp_path))

    index = (tmp_path / "index.html").read_text()
    assert "overview.html" not in index
    assert "Uses yaml." not in index
    assert "sections/dependencies.html" in index


def test_each_diagram_has_one_name(diagrams_only):
    """A diagram is called the same in the sidebar, the index, and its own page."""
    index = (diagrams_only / "index.html").read_text()
    page = (diagrams_only / "diagrams" / "classes.html").read_text()

    assert "<title>Classes · Docs</title>" in page
    assert re.search(r"<h1[^>]*>Classes</h1>", page)
    assert re.findall(r"<span>(Classes|Sequence)</span>", index) == [
        "Classes",
        "Sequence",
    ]
    assert re.findall(r">\s*(Classes|Sequence)\s*</a>", index) == [
        "Classes",
        "Sequence",
    ]


def failing_template_manager(error: Exception) -> Mock:
    """A template manager whose page rendering raises the given error."""
    navigation = Mock(render=Mock(return_value="<nav></nav>"))
    return Mock(
        templates={"navigation": navigation}, render_template=Mock(side_effect=error)
    )


@pytest.mark.parametrize(
    "error",
    [PermissionError("output is read-only"), jinja2.TemplateError("bad template")],
)
def test_write_and_template_failures_are_documentation_errors(tmp_path, error):
    """Failures writing the site are reported as one documentation error."""
    renderer = DocumentationRenderer(failing_template_manager(error))

    with pytest.raises(
        DocumentationError, match=f"^Failed to generate HTML documentation: {error}$"
    ):
        renderer.render(MINIMAL_DOCUMENTATION, {}, str(tmp_path))


def test_renderer_bug_is_not_disguised(tmp_path):
    """An unknown template name is a bug, so it is not reported as a write failure."""
    renderer = DocumentationRenderer(
        failing_template_manager(ValueError("Unknown template: x"))
    )

    with pytest.raises(ValueError, match=r"^Unknown template: x$"):
        renderer.render(MINIMAL_DOCUMENTATION, {}, str(tmp_path))


# A checkout can hold output/ entries that link to files elsewhere; writing the
# site through them would overwrite those files


def test_page_is_not_written_through_a_link_out_of_the_output_directory(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    elsewhere = tmp_path / "notes.txt"
    elsewhere.write_text("keep me\n")
    (output / "index.html").symlink_to(elsewhere)

    with pytest.raises(PathValidationError, match=r"index\.html"):
        DocumentationRenderer(get_template_manager()).render(
            MINIMAL_DOCUMENTATION, {}, str(output)
        )

    assert elsewhere.read_text() == "keep me\n"


def test_output_directory_that_is_a_link_is_refused(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "output"
    output.symlink_to(target)

    with pytest.raises(PathValidationError, match="link"):
        DocumentationRenderer(get_template_manager()).setup_output_directories(
            str(output)
        )

    assert list(target.iterdir()) == []


def test_output_subdirectory_linked_elsewhere_is_refused(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (output / "sections").symlink_to(elsewhere)

    with pytest.raises(PathValidationError, match="sections"):
        DocumentationRenderer(get_template_manager()).setup_output_directories(
            str(output)
        )

    assert list(elsewhere.iterdir()) == []
