"""Path validation utilities for security.

This module provides functions to validate file paths and prevent
path traversal vulnerabilities.
"""

from pathlib import Path

from ..exceptions.errors import PathValidationError

# Allowed extensions for env files
ALLOWED_ENV_EXTENSIONS: set[str] = {".env", ".txt", ""}


# Allowed base directories (relative to these)
def _get_allowed_directories() -> set[Path]:
    """Get the set of allowed base directories.

    Returns:
        Set of allowed directory paths (cwd and home)
    """
    allowed = {Path.cwd().resolve()}

    # Add home directory if available
    try:
        home = Path.home().resolve()
        allowed.add(home)
    except (RuntimeError, OSError):
        # Home directory may not be available in some environments
        pass

    return allowed


def validate_env_file_path(
    path: str, allowed_directories: set[Path] | None = None
) -> Path:
    """Validate that an env file path is safe to read.

    This function prevents path traversal attacks by ensuring:
    1. The path resolves to a location within allowed directories
    2. The file has an allowed extension
    3. The path doesn't contain suspicious patterns

    Args:
        path: The path to validate
        allowed_directories: Optional set of allowed base directories.
            If not provided, uses cwd and home directory.

    Returns:
        The resolved, validated Path object

    Raises:
        PathValidationError: If the path fails validation
    """
    if not path:
        raise PathValidationError("Path cannot be empty")

    # Check for null bytes (common attack vector) - must be done before any path operations
    if "\x00" in path:
        raise PathValidationError("Path contains null bytes")

    if allowed_directories is None:
        allowed_directories = _get_allowed_directories()

    # Convert to Path and resolve to absolute path
    try:
        resolved_path = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise PathValidationError(f"Invalid path format: {path}") from e

    # Check extension
    suffix = resolved_path.suffix.lower()
    # Also handle files without extension (like .env)
    name = resolved_path.name.lower()

    # Allow files that start with .env (like .env, .env.local, .env.production)
    is_env_file = name.startswith(".env")
    has_allowed_suffix = suffix in ALLOWED_ENV_EXTENSIONS

    if not (is_env_file or has_allowed_suffix):
        raise PathValidationError(
            f"File extension '{suffix}' not allowed. "
            f"Allowed extensions: {ALLOWED_ENV_EXTENSIONS}"
        )

    # Check if the path is within an allowed directory
    is_within_allowed = False
    for allowed_dir in allowed_directories:
        try:
            # Check if resolved_path is relative to allowed_dir
            resolved_path.relative_to(allowed_dir)
            is_within_allowed = True
            break
        except ValueError:
            continue

    if not is_within_allowed:
        raise PathValidationError(
            f"Path '{path}' is outside allowed directories. "
            "Env files must be within the current working directory or home directory."
        )

    return resolved_path


def resolves_within(path: str | Path, root: str | Path) -> bool:
    """Check that a path, with every symbolic link followed, stays inside root.

    A repository can hold links to files anywhere on the machine, and to
    files that anyone could replace, so codeatlas reads and writes only
    paths that resolve inside the directory it was given.

    Args:
        path: The path to check
        root: The directory it must stay within

    Returns:
        True if the path resolves to root or to something inside it
    """
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def require_within(path: str | Path, root: str | Path) -> None:
    """Refuse a write to a path that leaves root once its links are followed.

    Called before every write, since a link planted at a path codeatlas
    writes would redirect the write to any file the user can change.

    Args:
        path: The path about to be written
        root: The directory the write must stay within

    Raises:
        PathValidationError: If the path resolves outside root
    """
    if not resolves_within(path, root):
        raise PathValidationError(
            f"Refusing to write {path}: it links to {Path(path).resolve()}, "
            f"outside {root}"
        )


def is_safe_path(path: str, allowed_directories: set[Path] | None = None) -> bool:
    """Check if a path is safe without raising an exception.

    Args:
        path: The path to check
        allowed_directories: Optional set of allowed base directories

    Returns:
        True if the path is safe, False otherwise
    """
    try:
        validate_env_file_path(path, allowed_directories)
        return True
    except PathValidationError:
        return False
