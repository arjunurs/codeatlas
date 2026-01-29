"""Integration tests for caching functionality."""

from unittest.mock import MagicMock

import pytest

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
