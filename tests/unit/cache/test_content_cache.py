"""Unit tests for section content caching."""

import pytest

from docgen.cache.content_cache import SectionCacheEntry, SectionContentCache
from docgen.models.code_entity import CodeEntity
from docgen.models.file_analysis import FileAnalysis


@pytest.fixture
def sample_analyses():
    """Create sample file analyses."""
    return [
        FileAnalysis(
            file_path="module1.py",
            entities=[
                CodeEntity(
                    name="hello",
                    type="function",
                    docstring="Say hello",
                    start_line=1,
                    end_line=3,
                )
            ],
            imports=["os", "sys"],
            content="def hello():\n    pass\n",
        ),
        FileAnalysis(
            file_path="module2.py",
            entities=[
                CodeEntity(
                    name="Calculator",
                    type="class",
                    docstring="Simple calculator",
                    start_line=1,
                    end_line=5,
                )
            ],
            imports=["math"],
            content="class Calculator:\n    pass\n",
        ),
    ]


def test_section_cache_entry_serialization():
    """Test SectionCacheEntry to_dict and from_dict."""
    entry = SectionCacheEntry(
        section_name="overview",
        content_hash="abc123",
        content="Test content",
        dependency_files={"file1.py", "file2.py"},
    )

    # Serialize
    data = entry.to_dict()
    assert data["section_name"] == "overview"
    assert data["content_hash"] == "abc123"
    assert data["content"] == "Test content"
    assert set(data["dependency_files"]) == {"file1.py", "file2.py"}

    # Deserialize
    restored = SectionCacheEntry.from_dict(data)
    assert restored.section_name == entry.section_name
    assert restored.content_hash == entry.content_hash
    assert restored.content == entry.content
    assert restored.dependency_files == entry.dependency_files


def test_section_cache_get_section_hash(tmp_path, sample_analyses):
    """Test computing section hash based on dependencies."""
    cache = SectionContentCache(tmp_path)

    # Get hash for overview section (depends on all files)
    hash1, deps1 = cache.get_section_hash("overview", sample_analyses)
    assert len(hash1) == 64  # SHA-256
    assert "module1.py" in deps1
    assert "module2.py" in deps1

    # Get hash for imports-based section
    hash2, deps2 = cache.get_section_hash("dependencies", sample_analyses)
    assert len(hash2) == 64
    assert "module1.py" in deps2

    # Different sections should have different hashes
    assert hash1 != hash2


def test_section_cache_cache_and_retrieve(tmp_path, sample_analyses):
    """Test caching and retrieving section content."""
    cache = SectionContentCache(tmp_path)

    # Cache a section
    content = "# Overview\n\nThis is the overview."
    cache.cache_section("overview", content, sample_analyses)

    # Retrieve cached content
    cached = cache.get_cached_section("overview", sample_analyses)
    assert cached == content

    # Non-existent section returns None
    assert cache.get_cached_section("nonexistent", sample_analyses) is None


def test_section_cache_invalidation_on_change(tmp_path, sample_analyses):
    """Test that cache invalidates when content changes."""
    cache = SectionContentCache(tmp_path)

    # Cache a section
    content = "Original content"
    cache.cache_section("overview", content, sample_analyses)

    # Should get cached content
    assert cache.get_cached_section("overview", sample_analyses) == content

    # Modify the analyses
    modified_analyses = sample_analyses.copy()
    modified_analyses[0] = FileAnalysis(
        file_path="module1.py",
        entities=[
            CodeEntity(
                name="goodbye",  # Changed
                type="function",
                docstring="Say goodbye",
                start_line=1,
                end_line=3,
            )
        ],
        imports=["os", "sys"],
        content="def goodbye():\n    pass\n",
    )

    # Cache should miss (hash changed)
    assert cache.get_cached_section("overview", modified_analyses) is None


def test_section_cache_save_and_load(tmp_path, sample_analyses):
    """Test saving and loading cache from disk."""
    cache_dir = tmp_path / "cache"

    # Create cache and add sections
    cache1 = SectionContentCache(cache_dir)
    cache1.cache_section("overview", "Overview content", sample_analyses)
    cache1.cache_section("dependencies", "Deps content", sample_analyses)
    cache1.save_cache()

    # Load cache in new instance
    cache2 = SectionContentCache(cache_dir)
    assert "overview" in cache2.cache
    assert "dependencies" in cache2.cache
    assert cache2.cache["overview"].content == "Overview content"


def test_section_cache_invalidate_sections(tmp_path, sample_analyses):
    """Test invalidating sections based on changed files."""
    cache = SectionContentCache(tmp_path)

    # Cache multiple sections
    cache.cache_section("overview", "Overview", sample_analyses)
    cache.cache_section("dependencies", "Deps", sample_analyses)
    cache.cache_section("classes", "Classes", sample_analyses)

    # Invalidate sections that depend on module1.py
    invalidated = cache.invalidate_sections({"module1.py"})

    # All sections should be invalidated (they all depend on it)
    assert len(invalidated) > 0
    assert "overview" in invalidated


def test_section_cache_clear(tmp_path, sample_analyses):
    """Test clearing the cache."""
    cache = SectionContentCache(tmp_path)

    # Add sections
    cache.cache_section("overview", "Content", sample_analyses)
    cache.save_cache()

    # Clear cache
    cache.clear()
    assert len(cache.cache) == 0
    assert not cache.cache_file.exists()


def test_section_cache_stats(tmp_path, sample_analyses):
    """Test getting cache statistics."""
    cache = SectionContentCache(tmp_path)

    # Add sections
    cache.cache_section("overview", "Overview content", sample_analyses)
    cache.cache_section("dependencies", "Deps content", sample_analyses)

    # Get stats
    stats = cache.get_stats()
    assert stats["total_sections"] == 2
    assert stats["total_size_bytes"] > 0
    assert "overview" in stats["sections"]
    assert "dependencies" in stats["sections"]


def test_section_hash_covers_model_and_prompt(tmp_path, sample_analyses):
    """Changing the model or the prompt changes the section hash."""
    cache = SectionContentCache(tmp_path)

    def section_hash(model: str, prompt: str) -> str:
        return cache.get_section_hash(
            "overview", sample_analyses, model=model, prompt=prompt
        )[0]

    base = section_hash("claude-sonnet-5", "Describe the system")
    assert section_hash("claude-sonnet-5", "Describe the system") == base
    assert section_hash("claude-haiku-4-5", "Describe the system") != base
    assert section_hash("claude-sonnet-5", "Describe the system briefly") != base


def test_cached_section_misses_for_other_model(tmp_path, sample_analyses):
    """A section cached for one model is not returned for another."""
    cache = SectionContentCache(tmp_path)
    cache.cache_section(
        "overview", "Sonnet text", sample_analyses, model="claude-sonnet-5", prompt="p"
    )

    assert (
        cache.get_cached_section(
            "overview", sample_analyses, model="claude-sonnet-5", prompt="p"
        )
        == "Sonnet text"
    )
    assert (
        cache.get_cached_section(
            "overview", sample_analyses, model="claude-haiku-4-5", prompt="p"
        )
        is None
    )
