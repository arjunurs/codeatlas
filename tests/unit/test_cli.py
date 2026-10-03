"""Unit tests for the CLI module."""

import importlib.metadata
from unittest.mock import patch

import pytest

import docgen
from docgen import cli
from docgen.cli import __version__, main, parse_args


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_source_required(self):
        """Test that --source is required."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_source_only(self):
        """Test parsing with only --source."""
        args = parse_args(["--source", "./my_project"])
        assert args.source == "./my_project"
        assert args.output == "output"  # default

    def test_output_short_alias(self):
        """Test -o alias for --output."""
        args = parse_args(["--source", "./src", "-o", "./my_docs"])
        assert args.output == "./my_docs"

    def test_verbose_short_alias(self):
        """Test -v alias for --verbose."""
        args = parse_args(["--source", "./src", "-v"])
        assert args.verbose is True

    def test_quiet_short_alias(self):
        """Test -q alias for --quiet."""
        args = parse_args(["--source", "./src", "-q"])
        assert args.quiet is True

    def test_exclude_patterns(self):
        """Test --exclude can be repeated."""
        args = parse_args(
            ["--source", "./src", "--exclude", "*_test.py", "--exclude", "__pycache__"]
        )
        assert args.exclude == ["*_test.py", "__pycache__"]

    def test_no_diagrams_flag(self):
        """Test --no-diagrams flag."""
        args = parse_args(["--source", "./src", "--no-diagrams"])
        assert args.no_diagrams is True

    def test_sections_argument(self):
        """Test --sections argument."""
        args = parse_args(["--source", "./src", "--sections", "overview,dependencies"])
        assert args.sections == "overview,dependencies"

    def test_diagrams_argument(self):
        """Test --diagrams argument."""
        args = parse_args(["--source", "./src", "--diagrams", "architecture,class"])
        assert args.diagrams == "architecture,class"

    def test_template_dir(self):
        """Test --template-dir argument."""
        args = parse_args(["--source", "./src", "--template-dir", "./templates"])
        assert args.template_dir == "./templates"

    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        args = parse_args(["--source", "./src", "--dry-run"])
        assert args.dry_run is True

    def test_max_files_argument(self):
        """Test --max-files argument."""
        args = parse_args(["--source", "./src", "--max-files", "50"])
        assert args.max_files == 50

    def test_api_key_env_argument(self):
        """Test --api-key-env argument."""
        args = parse_args(["--source", "./src", "--api-key-env", "./.env"])
        assert args.api_key_env == "./.env"

    def test_temperature_argument(self):
        """Test --temperature argument."""
        args = parse_args(["--source", "./src", "--temperature", "0.5"])
        assert args.temperature == 0.5

    def test_anthropic_model_defaults_to_none(self):
        """Without --anthropic-model, the quality mode picks the model."""
        args = parse_args(["--source", "./src", "--quality-mode", "fast"])
        assert args.anthropic_model is None
        assert args.quality_mode == "fast"

    def test_anthropic_model_argument(self):
        """Test --anthropic-model argument."""
        args = parse_args(["--source", "./src", "--anthropic-model", "claude-3-opus"])
        assert args.anthropic_model == "claude-3-opus"

    def test_openai_embedding_model_argument(self):
        """Test --openai-embedding-model argument."""
        args = parse_args(
            ["--source", "./src", "--openai-embedding-model", "text-embedding-ada-002"]
        )
        assert args.openai_embedding_model == "text-embedding-ada-002"

    def test_no_direct_api_key_args(self):
        """Test that direct API key arguments were removed."""
        # These arguments should not exist
        args = parse_args(["--source", "./src"])
        assert not hasattr(args, "anthropic_api_key")
        assert not hasattr(args, "openai_api_key")

    def test_defaults(self):
        """Test default values."""
        args = parse_args(["--source", "./src"])
        assert args.output == "output"
        assert args.verbose is False
        assert args.quiet is False
        assert args.exclude == []
        assert args.no_diagrams is False
        assert args.sections is None
        assert args.diagrams is None
        assert args.template_dir is None
        assert args.dry_run is False
        assert args.max_files is None
        assert args.api_key_env is None


class TestMain:
    """Tests for main() with real argument lists and a mocked generator."""

    @pytest.fixture(autouse=True)
    def no_logging_setup(self):
        """Keep main() from reconfiguring logging for the rest of the run."""
        with patch("docgen.cli.setup_logging"):
            yield

    @pytest.fixture
    def generator_cls(self):
        """The generator class as main() sees it."""
        with patch("docgen.cli.CodeDocumentationGenerator") as cls:
            yield cls

    @pytest.fixture
    def get_api_keys(self):
        """API key loading, returning fixed keys."""
        with patch(
            "docgen.cli.get_api_keys", return_value=("anthropic-key", "openai-key")
        ) as get_keys:
            yield get_keys

    def test_verbose_quiet_mutually_exclusive(self, capsys):
        """--verbose and --quiet together exit with an error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--source", "./src", "--verbose", "--quiet"])

        assert exc_info.value.code == 1
        assert "--verbose and --quiet are mutually exclusive" in capsys.readouterr().err

    def test_no_diagrams_and_diagrams_only_are_mutually_exclusive(self, capsys):
        """--no-diagrams and --diagrams-only together exit with an error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--source", "./src", "--no-diagrams", "--diagrams-only"])

        assert exc_info.value.code == 1
        assert (
            "--no-diagrams and --diagrams-only are mutually exclusive"
            in capsys.readouterr().err
        )

    def test_keys_are_loaded_and_passed_to_generator(self, generator_cls, get_api_keys):
        """A normal run loads keys from --api-key-env and generates once."""
        main(["--source", "./src", "-o", "./docs", "--api-key-env", "test.env"])

        get_api_keys.assert_called_once_with("test.env")
        kwargs = generator_cls.call_args.kwargs
        assert kwargs["anthropic_api_key"] == "anthropic-key"
        assert kwargs["openai_api_key"] == "openai-key"
        generator_cls.return_value.generate_documentation.assert_called_once_with(
            "./src", "./docs"
        )

    def test_diagrams_only_skips_api_keys(self, generator_cls, get_api_keys):
        """Diagrams-only mode needs no API keys."""
        main(["--source", "./src", "--diagrams-only"])

        get_api_keys.assert_not_called()
        kwargs = generator_cls.call_args.kwargs
        assert kwargs["anthropic_api_key"] == "diagrams-only-placeholder"
        assert kwargs["openai_api_key"] == "diagrams-only-placeholder"
        assert kwargs["diagrams_only"] is True

    def test_dry_run_skips_api_keys(self, generator_cls, get_api_keys):
        """Dry-run mode needs no API keys and turns the cache off."""
        main(["--source", "./src", "--dry-run"])

        get_api_keys.assert_not_called()
        kwargs = generator_cls.call_args.kwargs
        assert kwargs["anthropic_api_key"] == "dry-run-placeholder"
        assert kwargs["openai_api_key"] == "dry-run-placeholder"
        assert kwargs["dry_run"] is True
        assert kwargs["cache_enabled"] is False

    def test_sections_parsing(self, generator_cls, get_api_keys):
        """--sections is split on commas."""
        main(["--source", "./src", "--sections", "overview,dependencies"])

        assert generator_cls.call_args.kwargs["sections"] == [
            "overview",
            "dependencies",
        ]

    def test_diagrams_parsing(self, generator_cls, get_api_keys):
        """--diagrams is split on commas, with surrounding spaces removed."""
        main(["--source", "./src", "--diagrams", "architecture, class, sequence"])

        assert generator_cls.call_args.kwargs["diagrams"] == [
            "architecture",
            "class",
            "sequence",
        ]


class TestVersion:
    """Tests for version information."""

    def test_version_exists(self):
        """Test that version string exists."""
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_version_format(self):
        """Test that version follows semver format."""
        parts = __version__.split(".")
        assert len(parts) >= 2  # At least major.minor
        assert all(part.isdigit() for part in parts[:2])

    def test_version_comes_from_package_metadata(self):
        """The version is read from the installed package, set in pyproject.toml."""
        assert __version__ == importlib.metadata.version("codeatlas")

    def test_package_exports_the_cli_version(self):
        """docgen.__version__ and the --version output come from one lookup."""
        assert docgen.__version__ == __version__

    def test_version_flag_prints_version(self, capsys):
        """--version prints the program name and version, then exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])

        assert exc_info.value.code == 0
        assert capsys.readouterr().out.strip().endswith(__version__)

    def test_version_falls_back_when_package_not_installed(self, monkeypatch):
        """Importing from a source tree without installing still gives a version."""

        def not_installed(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(cli.importlib.metadata, "version", not_installed)

        assert cli._package_version() == "0.0.0+unknown"
