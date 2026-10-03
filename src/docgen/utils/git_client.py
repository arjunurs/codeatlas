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
