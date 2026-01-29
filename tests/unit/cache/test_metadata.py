"""Unit tests for cache metadata."""

from datetime import datetime

from docgen.cache.metadata import CacheMetadata, FileMetadata


def test_file_metadata_from_file(tmp_path):
    """Test creating FileMetadata from a file."""
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    # Create metadata
    metadata = FileMetadata.from_file(test_file, tmp_path)

    assert metadata.path == "test.py"
    assert len(metadata.content_hash) == 64  # SHA-256
    assert metadata.size == len("print('hello')")
    assert isinstance(metadata.last_analyzed, datetime)


def test_file_metadata_has_changed(tmp_path):
    """Test detecting file changes."""
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("original")

    # Create metadata for original
    metadata = FileMetadata.from_file(test_file, tmp_path)
    assert not metadata.has_changed(test_file)

    # Modify the file
    test_file.write_text("modified")
    assert metadata.has_changed(test_file)


def test_file_metadata_serialization(tmp_path):
    """Test FileMetadata to_dict and from_dict."""
    test_file = tmp_path / "test.py"
    test_file.write_text("content")

    metadata = FileMetadata.from_file(test_file, tmp_path)

    # Serialize and deserialize
    data = metadata.to_dict()
    restored = FileMetadata.from_dict(data)

    assert restored.path == metadata.path
    assert restored.content_hash == metadata.content_hash
    assert restored.mtime == metadata.mtime
    assert restored.size == metadata.size


def test_cache_metadata_create_for_project(tmp_path):
    """Test creating CacheMetadata for a project."""
    metadata = CacheMetadata.create_for_project(tmp_path)

    assert metadata.project_path == str(tmp_path.resolve())
    assert len(metadata.project_hash) == 16
    assert isinstance(metadata.created_at, datetime)
    assert metadata.cache_version == "1.0"


def test_cache_metadata_save_and_load(tmp_path):
    """Test saving and loading CacheMetadata."""
    cache_dir = tmp_path / "cache"
    metadata = CacheMetadata.create_for_project(tmp_path)

    # Add a file
    test_file = tmp_path / "test.py"
    test_file.write_text("content")
    metadata.update_file(test_file, tmp_path)

    # Save
    metadata.save(cache_dir)

    # Load
    loaded = CacheMetadata.load(cache_dir)
    assert loaded is not None
    assert loaded.project_path == metadata.project_path
    assert len(loaded.file_metadata) == 1
    assert "test.py" in loaded.file_metadata


def test_cache_metadata_update_file(tmp_path):
    """Test updating file metadata."""
    metadata = CacheMetadata.create_for_project(tmp_path)

    # Add a file
    test_file = tmp_path / "test.py"
    test_file.write_text("content")
    metadata.update_file(test_file, tmp_path)

    assert "test.py" in metadata.file_metadata
    assert metadata.file_metadata["test.py"].size == len("content")


def test_cache_metadata_remove_file(tmp_path):
    """Test removing file from metadata."""
    metadata = CacheMetadata.create_for_project(tmp_path)

    # Add a file
    test_file = tmp_path / "test.py"
    test_file.write_text("content")
    metadata.update_file(test_file, tmp_path)

    # Remove it
    metadata.remove_file("test.py")
    assert "test.py" not in metadata.file_metadata


def test_cache_metadata_load_nonexistent(tmp_path):
    """Test loading from nonexistent cache."""
    cache_dir = tmp_path / "nonexistent"
    loaded = CacheMetadata.load(cache_dir)
    assert loaded is None


def test_cache_metadata_load_corrupted(tmp_path):
    """Test loading corrupted cache."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Write corrupted JSON
    metadata_file = cache_dir / "file_metadata.json"
    metadata_file.write_text("{invalid json")

    loaded = CacheMetadata.load(cache_dir)
    assert loaded is None  # Should return None on corruption
