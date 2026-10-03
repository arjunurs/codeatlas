"""Unit tests for path validation utilities."""

import pytest

from docgen.utils.path_validation import (
    PathValidationError,
    is_safe_path,
    validate_env_file_path,
)


class TestValidateEnvFilePath:
    """Test cases for validate_env_file_path function."""

    def test_valid_env_file_in_cwd(self, tmp_path, monkeypatch):
        """Test valid .env file in current working directory."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create a .env file
        env_file = tmp_path / ".env"
        env_file.write_text("TEST=value")

        # Should succeed
        result = validate_env_file_path(".env")
        assert result == env_file.resolve()

    def test_valid_env_file_absolute_path(self, tmp_path, monkeypatch):
        """Test valid .env file with absolute path."""
        monkeypatch.chdir(tmp_path)

        env_file = tmp_path / ".env.local"
        env_file.write_text("TEST=value")

        result = validate_env_file_path(str(env_file))
        assert result == env_file.resolve()

    def test_valid_txt_file(self, tmp_path, monkeypatch):
        """Test valid .txt file."""
        monkeypatch.chdir(tmp_path)

        txt_file = tmp_path / "config.txt"
        txt_file.write_text("TEST=value")

        result = validate_env_file_path(str(txt_file))
        assert result == txt_file.resolve()

    def test_path_traversal_attempt_parent(self, tmp_path, monkeypatch):
        """Test that path traversal with .. is rejected."""
        monkeypatch.chdir(tmp_path)

        # Try to escape current directory
        with pytest.raises(PathValidationError, match="outside allowed directories"):
            validate_env_file_path("../../../etc/passwd")

    def test_path_traversal_attempt_absolute(self, tmp_path, monkeypatch):
        """Test that absolute paths outside allowed dirs are rejected."""
        monkeypatch.chdir(tmp_path)

        # Try to access system file
        with pytest.raises(PathValidationError, match="outside allowed directories"):
            validate_env_file_path("/etc/passwd")

    def test_path_traversal_with_encoded_dots(self, tmp_path, monkeypatch):
        """Test that path traversal with encoded chars is rejected."""
        monkeypatch.chdir(tmp_path)

        # Create the subdirectory structure
        subdir = tmp_path / "sub"
        subdir.mkdir()

        # The resolved path would go outside allowed directories
        with pytest.raises(PathValidationError, match="outside allowed directories"):
            validate_env_file_path("sub/../../..")

    def test_null_byte_injection(self, tmp_path, monkeypatch):
        """Test that null byte injection is rejected."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(PathValidationError, match="null bytes"):
            validate_env_file_path(".env\x00.txt")

    def test_empty_path(self):
        """Test that empty path is rejected."""
        with pytest.raises(PathValidationError, match="cannot be empty"):
            validate_env_file_path("")

    def test_invalid_extension(self, tmp_path, monkeypatch):
        """Test that non-allowed extensions are rejected."""
        monkeypatch.chdir(tmp_path)

        py_file = tmp_path / "config.py"
        py_file.write_text("# Python file")

        with pytest.raises(PathValidationError, match="not allowed"):
            validate_env_file_path(str(py_file))

    def test_env_file_variations(self, tmp_path, monkeypatch):
        """Test various .env file name patterns."""
        monkeypatch.chdir(tmp_path)

        valid_names = [".env", ".env.local", ".env.production", ".env.test"]

        for name in valid_names:
            env_file = tmp_path / name
            env_file.write_text("TEST=value")

            result = validate_env_file_path(str(env_file))
            assert result == env_file.resolve()

    def test_custom_allowed_directories(self, tmp_path):
        """Test with custom allowed directories."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()

        env_file = custom_dir / ".env"
        env_file.write_text("TEST=value")

        # Should succeed with custom_dir in allowed directories
        result = validate_env_file_path(
            str(env_file), allowed_directories={custom_dir.resolve()}
        )
        assert result == env_file.resolve()

    def test_home_directory_allowed(self, tmp_path, monkeypatch):
        """An env file in the home directory is allowed by default."""
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        monkeypatch.setenv("HOME", str(home))
        # Work elsewhere, so only the home rule can allow the file
        monkeypatch.chdir(work)

        test_env = home / ".test_docgen_env"
        test_env.write_text("TEST=value")

        assert validate_env_file_path(str(test_env)) == test_env.resolve()

    def test_symlink_traversal(self, tmp_path, monkeypatch):
        """Test that symlink traversal is handled safely."""
        monkeypatch.chdir(tmp_path)

        # Create a subdirectory
        safe_dir = tmp_path / "safe"
        safe_dir.mkdir()

        env_file = safe_dir / ".env"
        env_file.write_text("TEST=value")

        # Create symlink pointing outside
        try:
            symlink = tmp_path / "link_to_root"
            symlink.symlink_to("/etc")

            # Symlink itself is in allowed directory but resolves outside
            with pytest.raises(
                PathValidationError, match="outside allowed directories"
            ):
                validate_env_file_path(str(symlink / "passwd"))
        except OSError:
            pytest.skip("Cannot create symlinks on this system")


class TestIsSafePath:
    """Test cases for is_safe_path function."""

    def test_safe_path_returns_true(self, tmp_path, monkeypatch):
        """Test that safe paths return True."""
        monkeypatch.chdir(tmp_path)

        env_file = tmp_path / ".env"
        env_file.write_text("TEST=value")

        assert is_safe_path(str(env_file)) is True

    def test_unsafe_path_returns_false(self, tmp_path, monkeypatch):
        """Test that unsafe paths return False."""
        monkeypatch.chdir(tmp_path)

        assert is_safe_path("../../../etc/passwd") is False

    def test_empty_path_returns_false(self):
        """Test that empty path returns False."""
        assert is_safe_path("") is False

    def test_invalid_extension_returns_false(self, tmp_path, monkeypatch):
        """Test that invalid extension returns False."""
        monkeypatch.chdir(tmp_path)

        py_file = tmp_path / "config.py"
        py_file.write_text("# Python file")

        assert is_safe_path(str(py_file)) is False
