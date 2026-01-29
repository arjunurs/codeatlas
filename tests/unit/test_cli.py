"""Unit tests for the CLI module."""

from unittest.mock import MagicMock, patch

import pytest

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
    """Tests for the main() function."""

    def test_verbose_quiet_mutually_exclusive(self):
        """Test that --verbose and --quiet together causes error."""
        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = True
            mock_args.quiet = True
            mock_parse.return_value = mock_args

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("docgen.cli.CodeDocumentationGenerator")
    @patch("docgen.cli.get_api_keys")
    @patch("docgen.cli.setup_logging")
    def test_diagrams_only_skips_api_keys(
        self, mock_logging, mock_get_keys, mock_generator
    ):
        """Test that diagrams-only mode doesn't require API keys."""
        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.dry_run = False
            mock_args.diagrams_only = True
            mock_args.source = "./src"
            mock_args.output = "./docs"
            mock_args.temperature = 0.2
            mock_args.anthropic_model = "claude-sonnet-4"
            mock_args.openai_embedding_model = "text-embedding-3-small"
            mock_args.exclude = []
            mock_args.no_diagrams = False
            mock_args.sections = None
            mock_args.diagrams = None
            mock_args.template_dir = None
            mock_args.max_files = None
            mock_args.api_key_env = None
            # Cache-related attributes
            mock_args.cache_dir = None
            mock_args.no_cache = False
            mock_args.force_refresh = False
            mock_args.clear_cache = False
            mock_args.cache_stats = False
            # Phase 4 attributes
            mock_args.quality_mode = "balanced"
            mock_args.no_parallel = False
            mock_args.no_cost_tracking = False
            mock_parse.return_value = mock_args

            mock_gen_instance = MagicMock()
            mock_generator.return_value = mock_gen_instance

            main()

            # get_api_keys should NOT be called in diagrams-only mode
            mock_get_keys.assert_not_called()

            # Generator should be called with placeholder keys
            call_kwargs = mock_generator.call_args[1]
            assert call_kwargs["anthropic_api_key"] == "diagrams-only-placeholder"
            assert call_kwargs["openai_api_key"] == "diagrams-only-placeholder"
            assert call_kwargs["diagrams_only"] is True

    @patch("docgen.cli.CodeDocumentationGenerator")
    @patch("docgen.cli.get_api_keys")
    @patch("docgen.cli.setup_logging")
    def test_dry_run_skips_api_keys(self, mock_logging, mock_get_keys, mock_generator):
        """Test that dry-run mode doesn't require API keys."""
        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.dry_run = True
            mock_args.source = "./src"
            mock_args.output = "./docs"
            mock_args.temperature = 0.2
            mock_args.anthropic_model = "claude-sonnet-4"
            mock_args.openai_embedding_model = "text-embedding-3-small"
            mock_args.exclude = []
            mock_args.no_diagrams = False
            mock_args.sections = None
            mock_args.diagrams = None
            mock_args.template_dir = None
            mock_args.max_files = None
            mock_args.api_key_env = None
            # Cache-related attributes
            mock_args.cache_dir = None
            mock_args.no_cache = False
            mock_args.force_refresh = False
            mock_args.clear_cache = False
            mock_args.cache_stats = False
            # Phase 4 attributes
            mock_args.quality_mode = "balanced"
            mock_args.no_parallel = False
            mock_args.no_cost_tracking = False
            mock_args.diagrams_only = False
            mock_parse.return_value = mock_args

            mock_gen_instance = MagicMock()
            mock_generator.return_value = mock_gen_instance

            main()

            # get_api_keys should NOT be called in dry-run mode
            mock_get_keys.assert_not_called()

            # Generator should be called with placeholder keys
            call_kwargs = mock_generator.call_args[1]
            assert call_kwargs["anthropic_api_key"] == "dry-run-placeholder"
            assert call_kwargs["openai_api_key"] == "dry-run-placeholder"
            assert call_kwargs["dry_run"] is True

    @patch("docgen.cli.CodeDocumentationGenerator")
    @patch("docgen.cli.get_api_keys")
    @patch("docgen.cli.setup_logging")
    def test_sections_parsing(self, mock_logging, mock_get_keys, mock_generator):
        """Test that --sections is correctly parsed."""
        mock_get_keys.return_value = ("key1", "key2")

        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.dry_run = False
            mock_args.source = "./src"
            mock_args.output = "./docs"
            mock_args.temperature = 0.2
            mock_args.anthropic_model = "claude-sonnet-4"
            mock_args.openai_embedding_model = "text-embedding-3-small"
            mock_args.exclude = []
            mock_args.no_diagrams = False
            mock_args.sections = "overview,dependencies"
            mock_args.diagrams = None
            mock_args.template_dir = None
            mock_args.max_files = None
            mock_args.api_key_env = None
            # Cache-related attributes
            mock_args.cache_dir = None
            mock_args.no_cache = False
            mock_args.force_refresh = False
            mock_args.clear_cache = False
            mock_args.cache_stats = False
            # Phase 4 attributes
            mock_args.quality_mode = "balanced"
            mock_args.no_parallel = False
            mock_args.no_cost_tracking = False
            mock_args.diagrams_only = False
            mock_parse.return_value = mock_args

            mock_gen_instance = MagicMock()
            mock_generator.return_value = mock_gen_instance

            main()

            call_kwargs = mock_generator.call_args[1]
            assert call_kwargs["sections"] == ["overview", "dependencies"]

    @patch("docgen.cli.CodeDocumentationGenerator")
    @patch("docgen.cli.get_api_keys")
    @patch("docgen.cli.setup_logging")
    def test_diagrams_parsing(self, mock_logging, mock_get_keys, mock_generator):
        """Test that --diagrams is correctly parsed."""
        mock_get_keys.return_value = ("key1", "key2")

        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.dry_run = False
            mock_args.source = "./src"
            mock_args.output = "./docs"
            mock_args.temperature = 0.2
            mock_args.anthropic_model = "claude-sonnet-4"
            mock_args.openai_embedding_model = "text-embedding-3-small"
            mock_args.exclude = []
            mock_args.no_diagrams = False
            mock_args.sections = None
            mock_args.diagrams = "architecture, class, sequence"
            mock_args.template_dir = None
            mock_args.max_files = None
            mock_args.api_key_env = None
            # Cache-related attributes
            mock_args.cache_dir = None
            mock_args.no_cache = False
            mock_args.force_refresh = False
            mock_args.clear_cache = False
            mock_args.cache_stats = False
            # Phase 4 attributes
            mock_args.quality_mode = "balanced"
            mock_args.no_parallel = False
            mock_args.no_cost_tracking = False
            mock_args.diagrams_only = False
            mock_parse.return_value = mock_args

            mock_gen_instance = MagicMock()
            mock_generator.return_value = mock_gen_instance

            main()

            call_kwargs = mock_generator.call_args[1]
            assert call_kwargs["diagrams"] == ["architecture", "class", "sequence"]

    @patch("docgen.cli.setup_logging")
    def test_no_diagrams_and_diagrams_only_are_mutually_exclusive(self, mock_logging):
        """Test that --no-diagrams and --diagrams-only cannot be used together."""
        with patch("docgen.cli.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.no_diagrams = True
            mock_args.diagrams_only = True
            mock_parse.return_value = mock_args

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1


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
