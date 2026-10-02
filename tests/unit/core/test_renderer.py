"""Unit tests for DocumentationRenderer HTML safety."""

import pytest

from docgen.core.renderer import DocumentationRenderer
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
