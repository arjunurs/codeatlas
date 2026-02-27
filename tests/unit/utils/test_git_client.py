"""Unit tests for GitClient utility."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from docgen.utils.git_client import GitClient


class TestGitClient:
    """Tests for GitClient."""

    def test_is_git_repo_true(self, tmp_path: Path):
        """Test is_git_repo returns True for a git repo."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert client.is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path: Path):
        """Test is_git_repo returns False for non-git dir."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            assert client.is_git_repo() is False

    def test_is_git_repo_file_not_found(self, tmp_path: Path):
        """Test is_git_repo handles missing git binary."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError
            assert client.is_git_repo() is False

    def test_get_current_commit(self, tmp_path: Path):
        """Test getting current commit hash."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
            assert client.get_current_commit() == "abc123"

    def test_get_current_commit_failure(self, tmp_path: Path):
        """Test get_current_commit returns None on failure."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            assert client.get_current_commit() is None

    def test_get_changed_files(self, tmp_path: Path):
        """Test getting changed files between commits."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="src/main.py\nREADME.md\ntests/test_foo.py\n",
            )
            result = client.get_changed_files("abc", "def")
            assert result == {"src/main.py", "README.md", "tests/test_foo.py"}

    def test_get_changed_files_failure(self, tmp_path: Path):
        """Test get_changed_files returns empty set on failure."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            assert client.get_changed_files("abc", "def") == set()

    def test_get_changed_files_timeout(self, tmp_path: Path):
        """Test get_changed_files handles timeout."""
        import subprocess

        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
            assert client.get_changed_files("abc", "def") == set()
