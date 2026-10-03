"""Unit tests for cache metadata."""

import os
import time
from datetime import datetime
from unittest.mock import patch

from docgen.cache.metadata import CacheMetadata, FileMetadata
from docgen.models.file_analysis import FileSnapshot


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


def test_file_metadata_has_changed_same_size_edit_in_same_mtime_tick(tmp_path):
    """Test that a same-size edit keeping the recorded mtime is detected."""
    test_file = tmp_path / "test.py"
    test_file.write_text("original")
    recorded_mtime_ns = test_file.stat().st_mtime_ns
    metadata = FileMetadata.from_file(test_file, tmp_path)

    # Simulate a second write landing in the same timestamp tick: same size
    # and the same mtime the metadata recorded
    test_file.write_text("modified")
    os.utime(test_file, ns=(recorded_mtime_ns, recorded_mtime_ns))

    assert metadata.has_changed(test_file)


def test_file_metadata_has_changed_trusts_mtime_for_older_files(tmp_path):
    """Test that files modified well before analysis skip the content hash."""
    test_file = tmp_path / "test.py"
    test_file.write_text("original")
    an_hour_ago = time.time() - 3600
    os.utime(test_file, (an_hour_ago, an_hour_ago))
    metadata = FileMetadata.from_file(test_file, tmp_path)

    with patch.object(
        FileMetadata, "_compute_file_hash", side_effect=AssertionError("hashed")
    ):
        assert not metadata.has_changed(test_file)


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


def test_cache_metadata_records_a_snapshot(tmp_path):
    """A file is recorded as it was read, with its read time as the capture time."""
    metadata = CacheMetadata.create_for_project(tmp_path)
    read_at = datetime(2026, 10, 3, 12, 0, 0)

    metadata.record_file(
        "pkg/mod.py",
        FileSnapshot(content_hash="abc", mtime=1.5, size=7, read_at=read_at),
    )

    recorded = metadata.file_metadata["pkg/mod.py"]
    assert (recorded.content_hash, recorded.mtime, recorded.size) == ("abc", 1.5, 7)
    assert recorded.last_analyzed == read_at


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
