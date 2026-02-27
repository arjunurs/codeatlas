"""Git operations utility.

Centralises subprocess calls to git so that callers do not duplicate
the same boilerplate.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GitClient:
    """Lightweight wrapper around git CLI commands.

    Args:
        working_dir: Directory in which to run git commands.
    """

    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir

    def is_git_repo(self) -> bool:
        """Check whether *working_dir* is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_current_commit(self) -> str | None:
        """Return the current HEAD commit hash, or *None* on failure."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def get_changed_files(self, from_commit: str, to_commit: str) -> set[str]:
        """Return file paths changed between two commits.

        Args:
            from_commit: Base commit hash.
            to_commit: Target commit hash.

        Returns:
            Set of relative file paths that changed.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", from_commit, to_commit],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return set()
