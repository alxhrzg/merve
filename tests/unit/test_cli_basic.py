"""Basic tests for CLI module functionality."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from mlserver.cli import (
    resolve_relative_paths,
    _is_likely_file_path,
    _resolve_path,
    main
)


class TestPathResolution:
    """Test path resolution utilities."""

    def test_is_likely_file_path(self):
        """Test file path detection."""
        # Should identify as file paths (relative paths with path indicators)
        assert _is_likely_file_path("model_path", "./model.pkl")
        assert _is_likely_file_path("config_file", "../config.yaml")
        assert _is_likely_file_path("artifact_path", "artifacts/model.joblib")

        # Should not identify as file paths (absolute paths or non-path keys)
        assert not _is_likely_file_path("config_file", "/path/to/config.yaml")  # absolute path
        assert not _is_likely_file_path("port", "8000")
        assert not _is_likely_file_path("name", "my_model")
        assert not _is_likely_file_path("debug", "true")

    def test_resolve_path_relative(self, temp_dir):
        """Test resolving relative paths."""
        config_dir = temp_dir
        relative_path = "./model.pkl"

        resolved = _resolve_path(relative_path, config_dir)
        expected = str(Path(config_dir) / "model.pkl")
        assert resolved == expected

    def test_resolve_path_absolute(self):
        """Test absolute paths remain unchanged."""
        config_dir = "/some/config/dir"
        absolute_path = "/absolute/path/model.pkl"

        resolved = _resolve_path(absolute_path, config_dir)
        assert resolved == absolute_path

    def test_resolve_relative_paths_dict(self, temp_dir):
        """Test resolving paths in init_kwargs dictionary."""
        config_dir = temp_dir
        init_kwargs = {
            "model_path": "./model.pkl",
            "preprocessor_path": "../preprocessor.pkl",
            "config_file": "/absolute/config.yaml",
            "port": "8000",  # Should not be changed
            "name": "test_model"  # Should not be changed
        }

        resolved = resolve_relative_paths(init_kwargs, config_dir)

        # File paths should be resolved
        assert resolved["model_path"] == str(Path(config_dir) / "model.pkl")
        assert resolved["preprocessor_path"] == str(Path(config_dir).parent / "preprocessor.pkl")
        assert resolved["config_file"] == "/absolute/config.yaml"  # Absolute unchanged

        # Non-file paths should remain unchanged
        assert resolved["port"] == "8000"
        assert resolved["name"] == "test_model"


class TestMainFunction:
    """Test main CLI function."""

    @patch('sys.argv')
    @patch('mlserver.cli.cmd_serve')
    def test_main_with_serve_command(self, mock_cmd_serve, mock_argv):
        """Test main function with serve command."""
        mock_argv.__getitem__ = lambda self, index: ['ml_server', 'serve', 'config.yaml'][index]
        mock_argv.__len__ = lambda self: 3

        # Mock the argument parsing
        with patch('mlserver.cli._create_argument_parser') as mock_parser:
            mock_args = MagicMock()
            mock_args.command = 'serve'
            mock_parser.return_value.parse_args.return_value = mock_args

            main()

            mock_cmd_serve.assert_called_once_with(mock_args)

    @patch('sys.argv', ['ml_server'])  # Mock sys.argv properly
    def test_main_exception_propagates(self):
        """Test main function allows exceptions to propagate."""
        with patch('mlserver.cli._create_argument_parser') as mock_parser:
            mock_parser.side_effect = Exception("Test error")

            # The main function doesn't catch exceptions, so they should propagate
            with pytest.raises(Exception, match="Test error"):
                main()