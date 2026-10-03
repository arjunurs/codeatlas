"""Unit tests for the code context the RAG pipeline puts in each prompt."""

from langchain_core.documents import Document

from docgen.core.rag_pipeline import format_excerpts


def test_each_excerpt_is_labeled_with_its_module():
    """The model sees each excerpt's module, named the way imports name it."""
    docs = [
        Document(
            page_content="def wsgi_app(): ...",
            metadata={"source": "/r/src/flask/app.py"},
        ),
        Document(
            page_content="class Scaffold: ...",
            metadata={"source": "/r/src/flask/sansio/scaffold.py"},
        ),
        Document(
            page_content="__version__ = 1",
            metadata={"source": "/r/src/flask/__init__.py"},
        ),
    ]

    context = format_excerpts(docs, root="/r/src")

    assert context.split("\n\n---\n\n") == [
        "Module: flask.app\ndef wsgi_app(): ...",
        "Module: flask.sansio.scaffold\nclass Scaffold: ...",
        "Module: flask\n__version__ = 1",
    ]


def test_an_excerpt_without_a_source_has_no_label():
    """A chunk with no source file is passed through as it is."""
    assert format_excerpts([Document(page_content="x = 1")], root="/r/src") == "x = 1"
