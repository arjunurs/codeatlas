"""The vector stores codeatlas builds, checked against a real Chroma.

Chroma turns its telemetry off by itself whenever pytest is imported, so the
telemetry tests check the settings each client was created with, not network
traffic.
"""

import logging

import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter

from docgen.config import DEFAULT_CONFIG
from docgen.core.analyzer import CodeAnalyzer
from docgen.core.rag_pipeline import RAGPipelineFactory


@pytest.fixture
def build_store(tmp_path, fake_embeddings, fake_chat_model_with_usage):
    """Index a one-file project the way a run does, and return the store.

    Factories are cleaned up after the test, which drops in-memory stores.
    """
    factories = []

    def build(name: str, code: str, **cache_args):
        project = tmp_path / name
        project.mkdir(exist_ok=True)
        (project / f"{name}.py").write_text(code)

        factory = RAGPipelineFactory(
            llm=fake_chat_model_with_usage,
            embeddings=fake_embeddings,
            config=DEFAULT_CONFIG,
            text_splitter=RecursiveCharacterTextSplitter(
                chunk_size=DEFAULT_CONFIG.CHUNK_SIZE,
                chunk_overlap=DEFAULT_CONFIG.CHUNK_OVERLAP,
            ),
            **cache_args,
        )
        factories.append(factory)
        analyses = CodeAnalyzer().analyze_directory(str(project))
        factory.create_rag_chain(analyses, source_dir=project)
        return factory.vector_store

    yield build
    for factory in factories:
        factory.cleanup()


def test_in_memory_stores_do_not_share_chunks(build_store):
    """Two runs without the cache in one process keep their code apart.

    Chroma keeps one in-memory client per process, so stores that share a
    collection name share their chunks.
    """
    build_store("alpha", "def alpha_only():\n    return 1\n")
    second = build_store("beta", "def beta_only():\n    return 2\n")

    documents = second.get(include=["documents"])["documents"]
    assert documents
    assert not [doc for doc in documents if "alpha_only" in doc]


def telemetry_enabled(store) -> bool:
    """Whether the client behind a langchain Chroma store has telemetry on."""
    return store._client.get_settings().anonymized_telemetry


def test_in_memory_store_has_telemetry_off(build_store):
    """Without the cache, the in-memory store is created with telemetry off."""
    store = build_store("alpha", "def alpha_only():\n    return 1\n")

    assert telemetry_enabled(store) is False


def test_cached_store_has_telemetry_off(build_store, tmp_path):
    """The cached store has telemetry off when created and when reopened."""
    code = "def alpha_only():\n    return 1\n"
    cache_args = {"cache_enabled": True, "cache_dir": tmp_path / "cache"}

    assert telemetry_enabled(build_store("alpha", code, **cache_args)) is False
    assert telemetry_enabled(build_store("alpha", code, **cache_args)) is False


def test_force_refresh_reopens_the_store_with_the_same_settings(
    build_store, tmp_path, caplog
):
    """Rebuilding drops the old collection instead of deleting the directory.

    Chroma refuses a second client on the same directory with different
    settings, so a client opened without them would fall back to deleting
    the directory, with a warning.
    """
    code = "def alpha_only():\n    return 1\n"
    cache_args = {"cache_enabled": True, "cache_dir": tmp_path / "cache"}
    build_store("alpha", code, **cache_args)

    with caplog.at_level(logging.WARNING, logger="docgen.cache.vector_cache"):
        store = build_store("alpha", code, force_refresh=True, **cache_args)

    assert "Could not open existing vector store" not in caplog.text
    assert telemetry_enabled(store) is False
