"""Unit tests for GitClient utility."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docgen.utils.git_client import GitClient


class TestGitClient:
    """Tests for GitClient."""

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

    @pytest.mark.parametrize(
        "error", [FileNotFoundError("git"), subprocess.TimeoutExpired("git", 5)]
    )
    def test_get_current_commit_without_git(self, tmp_path: Path, error):
        """A missing git binary, or a git that hangs, gives no commit."""
        client = GitClient(tmp_path)
        with patch("docgen.utils.git_client.subprocess.run") as mock_run:
            mock_run.side_effect = error
            assert client.get_current_commit() is None
