"""Integration tests for caching functionality."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document

from docgen.cache import vector_cache
from docgen.cache.metadata import CacheMetadata
from docgen.core.generator import CodeDocumentationGenerator


@pytest.fixture
def sample_python_project(tmp_path):
    """Create a sample Python project for testing."""
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    # Create some Python files
    (project_dir / "module1.py").write_text("""
def hello():
    \"\"\"Say hello.\"\"\"
    return "Hello, World!"

class Greeter:
    \"\"\"A simple greeter.\"\"\"
    def greet(self, name):
        return f"Hello, {name}!"
""")

    (project_dir / "module2.py").write_text("""
class Calculator:
    \"\"\"Simple calculator.\"\"\"
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""")

    return project_dir


@pytest.fixture
def cache_dir(tmp_path):
    """Create a cache directory."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    from langchain_core.runnables import RunnableLambda

    mock_provider = MagicMock()
    # Create a simple runnable that returns mock content
    mock_llm = RunnableLambda(lambda x: "Mock documentation content")
    mock_provider.get_langchain_llm.return_value = mock_llm
    return mock_provider


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    from langchain_core.embeddings import Embeddings

    class MockEmbeddings(Embeddings):
        """Mock embeddings implementation."""

        def embed_documents(self, texts):
            return [[0.1] * 1536 for _ in texts]

        def embed_query(self, text):
            return [0.1] * 1536

    mock_provider = MagicMock()
    mock_provider.get_langchain_embeddings.return_value = MockEmbeddings()
    return mock_provider


def test_cache_created_on_first_run(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that cache is created on first run."""
    output_dir = tmp_path / "output"

    # Create project-specific cache directory
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash

    # First run with caching enabled
    generator = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,  # Pass project-specific cache dir
        skip_diagrams=True,  # Skip diagrams for faster test
    )

    generator.generate_documentation(str(sample_python_project), str(output_dir))

    # Verify cache was created
    assert project_cache_dir.exists()
    assert (project_cache_dir / "file_metadata.json").exists()
    assert (project_cache_dir / "chromadb").exists()


def test_cache_reused_on_second_run(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that cache is reused when files haven't changed."""
    output_dir = tmp_path / "output"

    # Create project-specific cache directory
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash

    # First run
    generator1 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
    )
    generator1.generate_documentation(str(sample_python_project), str(output_dir))

    # Get cache metadata after first run
    metadata1 = CacheMetadata.load(project_cache_dir)

    # Second run (no changes)
    generator2 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
    )
    generator2.generate_documentation(str(sample_python_project), str(output_dir))

    # Cache should still exist
    metadata2 = CacheMetadata.load(project_cache_dir)
    assert metadata2 is not None
    assert len(metadata2.file_metadata) == len(metadata1.file_metadata)


def test_cache_updated_when_file_changes(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that cache is updated when files change."""
    output_dir = tmp_path / "output"

    # Create project-specific cache directory
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash

    # First run
    generator1 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
    )
    generator1.generate_documentation(str(sample_python_project), str(output_dir))

    # Get initial file hash
    metadata1 = CacheMetadata.load(project_cache_dir)
    original_hash = metadata1.file_metadata["module1.py"].content_hash

    # Modify a file - make sure content is actually different
    (sample_python_project / "module1.py").write_text("""def hello():
    \"\"\"Say hello differently.\"\"\"
    return "Hi there!"

def goodbye():
    \"\"\"Say goodbye.\"\"\"
    return "Goodbye!"
""")

    # Second run
    generator2 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
    )
    generator2.generate_documentation(str(sample_python_project), str(output_dir))

    # Verify cache was updated
    metadata2 = CacheMetadata.load(project_cache_dir)
    new_hash = metadata2.file_metadata["module1.py"].content_hash
    assert new_hash != original_hash


def _run_cached_generator(
    project_dir,
    project_cache_dir,
    output_dir,
    llm_provider,
    embedding_provider,
    **kwargs,
):
    """Run the generator with caching enabled and diagrams skipped."""
    generator = CodeDocumentationGenerator(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
        **kwargs,
    )
    generator.generate_documentation(str(project_dir), str(output_dir))


def _stored_chunks(project_cache_dir, embedding_provider):
    """Return the ids, metadatas, and documents in the cached vector store."""
    store = Chroma(
        persist_directory=str(project_cache_dir / "chromadb"),
        embedding_function=embedding_provider.get_langchain_embeddings(),
    )
    return store.get(include=["metadatas", "documents"])


def test_incremental_update_refreshes_vector_store(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
    monkeypatch,
):
    """Test that only changed, deleted, and new files are re-embedded."""
    # Force several add batches so batching is exercised
    monkeypatch.setattr(vector_cache, "ADD_BATCH_SIZE", 1)
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash
    run_args = (
        sample_python_project,
        project_cache_dir,
        tmp_path / "output",
        mock_llm_provider,
        mock_embedding_provider,
    )
    (sample_python_project / "untouched.py").write_text(
        'def keep():\n    """Keep."""\n    return 0\n'
    )

    _run_cached_generator(*run_args)
    before = _stored_chunks(project_cache_dir, mock_embedding_provider)
    untouched_ids = {
        doc_id
        for doc_id, meta in zip(before["ids"], before["metadatas"])
        if Path(meta["source"]).name == "untouched.py"
    }
    assert untouched_ids

    # Change one file, delete one, and add one
    (sample_python_project / "module1.py").write_text(
        'def wave():\n    """Wave."""\n    return "o/"\n'
    )
    (sample_python_project / "module2.py").unlink()
    (sample_python_project / "module3.py").write_text(
        'def added():\n    """Added later."""\n    return 3\n'
    )

    _run_cached_generator(*run_args)

    after = _stored_chunks(project_cache_dir, mock_embedding_provider)
    sources = [Path(meta["source"]).name for meta in after["metadatas"]]
    contents = "\n".join(after["documents"])

    assert set(sources) == {"module1.py", "module3.py", "untouched.py"}
    # The untouched file keeps its original chunks rather than being re-added
    assert {
        doc_id
        for doc_id, source in zip(after["ids"], sources)
        if source == "untouched.py"
    } == untouched_ids
    # No chunk is stored twice
    assert len(set(zip(sources, after["documents"]))) == len(after["ids"])
    assert "def wave" in contents
    assert "def added" in contents
    assert "Greeter" not in contents  # old module1.py
    assert "Calculator" not in contents  # deleted module2.py


def test_incremental_update_removes_orphaned_chunks(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that chunks of files missing from the cache metadata are removed."""
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash
    run_args = (
        sample_python_project,
        project_cache_dir,
        tmp_path / "output",
        mock_llm_provider,
        mock_embedding_provider,
    )
    _run_cached_generator(*run_args)

    # Chunks left behind by older cache versions: one for a file that is no
    # longer tracked, and one from outside the source directory
    store = Chroma(
        persist_directory=str(project_cache_dir / "chromadb"),
        embedding_function=mock_embedding_provider.get_langchain_embeddings(),
    )
    store.add_documents(
        [
            Document(
                page_content="orphan inside source",
                metadata={"source": str(sample_python_project / "gone.py")},
            ),
            Document(
                page_content="orphan outside source",
                metadata={"source": str(tmp_path / "elsewhere" / "other.py")},
            ),
        ]
    )
    (sample_python_project / "module1.py").write_text(
        'def wave():\n    """Wave."""\n    return "o/"\n'
    )

    _run_cached_generator(*run_args)

    contents = "\n".join(
        _stored_chunks(project_cache_dir, mock_embedding_provider)["documents"]
    )
    assert "orphan inside source" not in contents
    assert "orphan outside source" not in contents
    assert "def wave" in contents


def test_force_refresh_recovers_unreadable_store(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that force refresh rebuilds a vector store that cannot be opened."""
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash
    vector_dir = project_cache_dir / "chromadb"
    vector_dir.mkdir(parents=True)
    (vector_dir / "chroma.sqlite3").write_bytes(b"not a database" * 512)

    _run_cached_generator(
        sample_python_project,
        project_cache_dir,
        tmp_path / "output",
        mock_llm_provider,
        mock_embedding_provider,
        force_refresh=True,
    )

    stored = _stored_chunks(project_cache_dir, mock_embedding_provider)
    assert {Path(meta["source"]).name for meta in stored["metadatas"]} == {
        "module1.py",
        "module2.py",
    }


def test_cache_disabled(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that no cache is created when caching is disabled."""
    output_dir = tmp_path / "output"

    # Run with caching disabled
    generator = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=False,
        cache_dir=cache_dir,
        dry_run=True,
    )
    generator.generate_documentation(str(sample_python_project), str(output_dir))

    # Verify no cache was created
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash
    assert not (project_cache_dir / "file_metadata.json").exists()


def test_force_refresh_clears_cache(
    sample_python_project,
    cache_dir,
    tmp_path,
    mock_llm_provider,
    mock_embedding_provider,
):
    """Test that force refresh clears and rebuilds cache."""
    output_dir = tmp_path / "output"

    # Create project-specific cache directory
    project_hash = CacheMetadata.create_for_project(sample_python_project).project_hash
    project_cache_dir = cache_dir / project_hash

    # First run
    generator1 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        skip_diagrams=True,
    )
    generator1.generate_documentation(str(sample_python_project), str(output_dir))

    # Get initial timestamp
    metadata1 = CacheMetadata.load(project_cache_dir)

    # Second run with force refresh
    generator2 = CodeDocumentationGenerator(
        llm_provider=mock_llm_provider,
        embedding_provider=mock_embedding_provider,
        cache_enabled=True,
        cache_dir=project_cache_dir,
        force_refresh=True,
        skip_diagrams=True,
    )
    generator2.generate_documentation(str(sample_python_project), str(output_dir))

    # Cache should be recreated
    metadata2 = CacheMetadata.load(project_cache_dir)
    assert metadata2 is not None
    # Note: In force refresh, we clear the vector store but keep metadata
    # The metadata should be updated
    assert metadata2.last_updated >= metadata1.last_updated


def test_force_refresh_regenerates_cached_sections(
    sample_python_project, cache_dir, tmp_path, mock_embedding_provider
):
    """--force-refresh calls the LLM again for sections that are cached."""
    from langchain_core.runnables import RunnableLambda

    llm_calls = []

    def fake_llm(prompt_value):
        llm_calls.append(prompt_value)
        return "Section content"

    llm_provider = MagicMock()
    llm_provider.model_name = "claude-sonnet-5"
    llm_provider.get_langchain_llm.return_value = RunnableLambda(fake_llm)

    def run(force_refresh: bool) -> None:
        CodeDocumentationGenerator(
            llm_provider=llm_provider,
            embedding_provider=mock_embedding_provider,
            cache_enabled=True,
            cache_dir=cache_dir,
            force_refresh=force_refresh,
            sections=["overview"],
            skip_diagrams=True,
        ).generate_documentation(str(sample_python_project), str(tmp_path / "out"))

    run(force_refresh=False)
    run(force_refresh=False)
    assert len(llm_calls) == 1

    run(force_refresh=True)
    assert len(llm_calls) == 2
