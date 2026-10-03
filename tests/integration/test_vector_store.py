"""The vector stores codeatlas builds, checked against a real Chroma."""

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
        project.mkdir()
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
