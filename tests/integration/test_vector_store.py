"""The vector stores codeatlas builds, checked against a real Chroma.

Chroma turns its telemetry off by itself whenever pytest is imported, so the
telemetry tests check the settings each client was created with, not network
traffic.
"""

import logging
from typing import ClassVar

import pytest
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from docgen.config import DEFAULT_CONFIG, GeneratorConfig
from docgen.core.analyzer import CodeAnalyzer
from docgen.core.rag_pipeline import RAGPipelineFactory
from docgen.exceptions.errors import DocumentationError, VectorStoreError


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


def test_in_memory_store_writes_nothing_to_disk(build_store, tmp_path, monkeypatch):
    """Without the cache, nothing is written to the working directory.

    Older langchain-chroma releases persist any store given client settings,
    to ./chroma by default.
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    build_store("alpha", "def alpha_only():\n    return 1\n")

    assert list(workdir.iterdir()) == []


def test_in_memory_store_stays_in_memory_after_a_cached_store(build_store, tmp_path):
    """A cached store does not turn a later in-memory store into an on-disk one.

    Chroma writes the directory into the settings object a persistent client
    is given, so settings shared between clients carry one store's directory
    into the next.
    """
    cache_args = {"cache_enabled": True, "cache_dir": tmp_path / "cache"}
    build_store("alpha", "def alpha_only():\n    return 1\n", **cache_args)

    store = build_store("beta", "def beta_only():\n    return 2\n")

    assert store._client.get_settings().is_persistent is False


class FailingEmbeddings(Embeddings):
    """An embeddings model whose service is down."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding service down")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("embedding service down")


@pytest.mark.parametrize("cache_enabled", [False, True])
def test_embedding_failure_is_reported_once(
    tmp_path, fake_chat_model_with_usage, cache_enabled
):
    """An embedding failure names the stage once, with or without the cache."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("def app():\n    return 1\n")
    factory = RAGPipelineFactory(
        llm=fake_chat_model_with_usage,
        embeddings=FailingEmbeddings(),
        config=DEFAULT_CONFIG,
        text_splitter=RecursiveCharacterTextSplitter(),
        cache_enabled=cache_enabled,
        cache_dir=tmp_path / "cache",
    )
    analyses = CodeAnalyzer().analyze_directory(str(project))

    with pytest.raises(
        VectorStoreError,
        match=r"^Failed to create vector store: RuntimeError: embedding service down$",
    ):
        factory.create_rag_chain(analyses, source_dir=project)


def test_no_content_error_is_not_wrapped(fake_chat_model_with_usage, fake_embeddings):
    """An error codeatlas raised itself keeps its own message."""
    factory = RAGPipelineFactory(
        llm=fake_chat_model_with_usage,
        embeddings=fake_embeddings,
        config=DEFAULT_CONFIG,
        text_splitter=RecursiveCharacterTextSplitter(),
    )

    with pytest.raises(
        DocumentationError, match=r"^No documentation content could be generated$"
    ):
        factory.create_rag_chain([])


class KeywordEmbeddings(Embeddings):
    """Embeds each chunk by the function it mentions.

    Queries sit closest to alpha_function (relevance 0.86) and further from
    beta_function (0.72). Each file gives two chunks with the same vector, so
    alpha's two chunks are exact near-duplicates of each other.
    """

    VECTORS: ClassVar[dict[str, list[float]]] = {
        "alpha_function": [0.9, 0.43589, 0.0],
        "beta_function": [0.8, 0.0, 0.6],
    }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def _vector(self, text: str) -> list[float]:
        for name, vector in self.VECTORS.items():
            if name in text:
                return vector
        raise ValueError(f"No vector for chunk: {text!r}")


@pytest.fixture
def retrieved_prompt(tmp_path, fake_chat_model_with_usage):
    """Run the RAG chain with given retriever settings; return the prompt sent."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "alpha.py").write_text("def alpha_function():\n    return 1\n")
    (project / "beta.py").write_text("def beta_function():\n    return 2\n")
    factories = []

    def run(**retriever_settings) -> str:
        factory = RAGPipelineFactory(
            llm=fake_chat_model_with_usage,
            embeddings=KeywordEmbeddings(),
            config=GeneratorConfig(**retriever_settings),
            text_splitter=RecursiveCharacterTextSplitter(
                chunk_size=DEFAULT_CONFIG.CHUNK_SIZE,
                chunk_overlap=DEFAULT_CONFIG.CHUNK_OVERLAP,
            ),
        )
        factories.append(factory)
        analyses = CodeAnalyzer().analyze_directory(str(project))
        factory.create_rag_chain(analyses, source_dir=project).invoke(
            "Describe the project"
        )
        return fake_chat_model_with_usage.prompts[-1]

    yield run
    for factory in factories:
        factory.cleanup()


def test_similarity_search_returns_the_nearest_chunks(retrieved_prompt):
    """With k=2, similarity search returns alpha's two near-duplicate chunks."""
    prompt = retrieved_prompt(RETRIEVER_K=2)

    assert "alpha_function" in prompt
    assert "beta_function" not in prompt


def test_mmr_trades_a_near_duplicate_for_a_different_chunk(retrieved_prompt):
    """With k=2, MMR returns one alpha chunk and the more different beta chunk."""
    prompt = retrieved_prompt(
        RETRIEVER_K=2, RETRIEVER_SEARCH_TYPE="mmr", RETRIEVER_FETCH_K=4
    )

    assert "alpha_function" in prompt
    assert "beta_function" in prompt


def test_score_threshold_drops_chunks_below_it(retrieved_prompt):
    """With room for all four chunks, a 0.8 threshold still drops beta's."""
    prompt = retrieved_prompt(RETRIEVER_SCORE_THRESHOLD=0.8)

    assert "alpha_function" in prompt
    assert "beta_function" not in prompt
