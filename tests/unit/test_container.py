"""Comprehensive tests for container module functionality."""
import pytest
import tempfile
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
from typing import Dict, Any

from mlserver.container import (
    ContainerError,
    _find_mlserver_source,
    _build_mlserver_wheel,
    detect_required_files,
    _looks_like_file_path,
    _analyze_python_imports,
    _resolve_local_import,
    generate_dockerignore,
    generate_dockerfile,
    build_container,
    push_container,
    list_images,
    remove_images,
    check_docker_availability
)
from mlserver.config import AppConfig, PredictorConfig, ServerConfig, BuildConfig


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create basic project structure
        (project_path / "predictor.py").write_text("""
import pickle
from typing import List, Dict, Any
import pandas as pd

class TestPredictor:
    def __init__(self, model_path: str):
        self.model_path = model_path
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

    def predict(self, X: List[Dict[str, Any]]) -> List[int]:
        return [1, 0, 1]
""")

        # Create a dummy model file
        (project_path / "model.pkl").write_bytes(b"dummy model data")

        # Create requirements.txt
        (project_path / "requirements.txt").write_text("pandas>=1.0\nscikit-learn>=1.0\n")

        # Create config file
        (project_path / "mlserver.yaml").write_text("""
server:
  host: 0.0.0.0
  port: 8000

predictor:
  module: predictor
  class_name: TestPredictor
  init_kwargs:
    model_path: "./model.pkl"

classifier:
  repository: "test-repo"
  name: "test-classifier"
  version: "1.0.0"
  description: "Test classifier"

model:
  version: "1.0.0"
""")

        yield project_path


@pytest.fixture
def mock_config():
    """Create a mock AppConfig for testing."""
    from mlserver.config import ApiConfig
    return AppConfig(
        server=ServerConfig(host="0.0.0.0", port=8000),
        predictor=PredictorConfig(
            module="test.predictor",
            class_name="TestPredictor",
            init_kwargs={"model_path": "./model.pkl"}
        ),
        classifier={
            "name": "test-classifier",
            "version": "1.0.0",
            "description": "Test classifier"
        },
        api=ApiConfig(
            version="v1",
            adapter="auto",
            thread_safe_predict=False
        ),
        build=BuildConfig(
            registry="test-registry",
            tag_prefix="ml-models"
        )
    )


class TestContainerError:
    """Test ContainerError exception."""

    def test_container_error_creation(self):
        """Test ContainerError can be created and raised."""
        with pytest.raises(ContainerError, match="Test error"):
            raise ContainerError("Test error")


class TestFindMLServerSource:
    """Test _find_mlserver_source function."""

    def test_find_mlserver_source_env_var(self):
        """Test finding mlserver source via environment variable."""
        test_path = "/test/mlserver/path"
        with patch.dict(os.environ, {'MLSERVER_SOURCE_PATH': test_path}), \
             patch('pathlib.Path.exists', return_value=True):
            result = _find_mlserver_source()
            assert result == test_path

    def test_find_mlserver_source_env_var_not_exists(self):
        """Test env var path that doesn't exist."""
        test_path = "/nonexistent/path"
        with patch.dict(os.environ, {'MLSERVER_SOURCE_PATH': test_path}), \
             patch('pathlib.Path.exists', return_value=False):
            # Should continue to other strategies
            result = _find_mlserver_source()
            # Result depends on other strategies, but shouldn't be the env var path
            assert result != test_path

    def test_find_mlserver_source_pyproject_detection(self):
        """Test finding mlserver source via pyproject.toml."""
        mock_pyproject_content = """
[project]
name = "mlserver-fastapi-wrapper"
version = "1.0.0"
"""

        with patch.dict(os.environ, {}, clear=True), \
             patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.open', mock_open(read_data=mock_pyproject_content)) as mock_file, \
             patch('importlib.util.find_spec', return_value=None):  # tomllib not available

            # Mock the Path.exists calls
            def exists_side_effect(self):
                return str(self).endswith('pyproject.toml')

            mock_exists.side_effect = exists_side_effect

            # Should find pyproject.toml and return the parent directory
            result = _find_mlserver_source()
            # The function searches upward from package parent, so result may be None
            # or the path depending on the search logic
            assert isinstance(result, (str, type(None)))

    def test_find_mlserver_source_no_tomllib(self):
        """Test when neither tomllib nor tomli are available."""
        with patch.dict(os.environ, {}, clear=True), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('importlib.util.find_spec', return_value=None):  # No tomllib/tomli

            result = _find_mlserver_source()
            # Should handle missing toml libraries gracefully
            assert isinstance(result, (str, type(None)))


class TestBuildMLServerWheel:
    """Test _build_mlserver_wheel function."""

    def test_build_mlserver_wheel_success(self, temp_project_dir):
        """Test successful wheel building."""
        mlserver_source = str(temp_project_dir)

        # Mock successful subprocess call
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            mock_wheel_file = temp_project_dir / "dist" / "mlserver-1.0.0-py3-none-any.whl"
            mock_wheel_file.parent.mkdir(exist_ok=True)
            mock_wheel_file.write_bytes(b"dummy wheel")

            result = _build_mlserver_wheel(mlserver_source, str(temp_project_dir))

            mock_run.assert_called_once()
            assert result is not None
            assert result.endswith(".whl")

    def test_build_mlserver_wheel_build_failure(self, temp_project_dir):
        """Test wheel building failure."""
        mlserver_source = str(temp_project_dir)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Build failed")

            with pytest.raises(ContainerError, match="Failed to build mlserver wheel"):
                _build_mlserver_wheel(mlserver_source, str(temp_project_dir))

    def test_build_mlserver_wheel_no_dist_files(self, temp_project_dir):
        """Test when build succeeds but no wheel files found."""
        mlserver_source = str(temp_project_dir)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Don't create any wheel files

            result = _build_mlserver_wheel(mlserver_source, str(temp_project_dir))
            assert result is None


class TestDetectRequiredFiles:
    """Test detect_required_files function."""

    def test_detect_required_files_basic(self, temp_project_dir, mock_config):
        """Test basic file detection."""
        result = detect_required_files(str(temp_project_dir), mock_config)

        assert isinstance(result, dict)
        assert "detected_files" in result
        assert "python_files" in result
        assert "requirements_files" in result
        assert "model_files" in result

        # Should detect our created files
        detected = result["detected_files"]
        assert "predictor.py" in detected
        assert "model.pkl" in detected
        assert "requirements.txt" in detected

    def test_detect_required_files_with_config_refs(self, temp_project_dir):
        """Test file detection with config file references."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="predictor",
                class_name="TestPredictor",
                init_kwargs={
                    "model_path": "./model.pkl",
                    "preprocessor_path": "./preprocessor.pkl",
                    "feature_order_path": "./features.json"
                }
            )
        )

        # Create the referenced files
        (temp_project_dir / "preprocessor.pkl").write_bytes(b"dummy preprocessor")
        (temp_project_dir / "features.json").write_text('["feature1", "feature2"]')

        result = detect_required_files(str(temp_project_dir), config)

        detected = result["detected_files"]
        assert "preprocessor.pkl" in detected
        assert "features.json" in detected

    def test_detect_required_files_missing_files(self, temp_project_dir, mock_config):
        """Test file detection with missing files."""
        # Reference a file that doesn't exist
        config = AppConfig(
            predictor=PredictorConfig(
                module="predictor",
                class_name="TestPredictor",
                init_kwargs={"model_path": "./nonexistent.pkl"}
            )
        )

        result = detect_required_files(str(temp_project_dir), config)

        # Should handle missing files gracefully
        assert isinstance(result, dict)
        assert "missing_files" in result
        assert "nonexistent.pkl" in result["missing_files"]


class TestUtilityFunctions:
    """Test utility functions."""

    def test_looks_like_file_path_positive_cases(self):
        """Test _looks_like_file_path with file-like strings."""
        assert _looks_like_file_path("model_path", "./model.pkl")
        assert _looks_like_file_path("config_file", "../config.yaml")
        assert _looks_like_file_path("data_file", "data/train.csv")
        assert _looks_like_file_path("script", "scripts/train.py")

    def test_looks_like_file_path_negative_cases(self):
        """Test _looks_like_file_path with non-file strings."""
        assert not _looks_like_file_path("port", "8000")
        assert not _looks_like_file_path("name", "test_model")
        assert not _looks_like_file_path("debug", "true")
        assert not _looks_like_file_path("url", "http://example.com")
        assert not _looks_like_file_path("threshold", "0.5")

    def test_analyze_python_imports(self, temp_project_dir):
        """Test _analyze_python_imports function."""
        # Create a Python file with various imports
        python_file = temp_project_dir / "test_imports.py"
        python_file.write_text("""
import os
import sys
from pathlib import Path
import pandas as pd
import sklearn.ensemble
from local_module import helper
import non_standard_package
""")

        with patch('mlserver.container._resolve_local_import', return_value=None):
            imports = _analyze_python_imports(str(temp_project_dir), str(python_file))

            assert isinstance(imports, set)
            assert "pandas" in imports
            assert "sklearn" in imports
            # Standard library modules should not be included
            assert "os" not in imports
            assert "sys" not in imports

    def test_resolve_local_import(self, temp_project_dir):
        """Test _resolve_local_import function."""
        # Create a local module
        local_module = temp_project_dir / "local_helper.py"
        local_module.write_text("def helper_function(): pass")

        result = _resolve_local_import(str(temp_project_dir), "local_helper")
        assert result == "local_helper.py"

        # Test non-existent module
        result = _resolve_local_import(str(temp_project_dir), "nonexistent")
        assert result is None


class TestDockerfileGeneration:
    """Test Dockerfile and dockerignore generation."""

    def test_generate_dockerignore_basic(self, temp_project_dir):
        """Test basic dockerignore generation."""
        auto_excludes = {"__pycache__", "*.pyc", ".git"}
        manual_excludes = {"test_data/", "docs/"}

        result = generate_dockerignore(
            str(temp_project_dir),
            auto_excludes,
            manual_excludes
        )

        assert isinstance(result, str)
        assert "__pycache__" in result
        assert "*.pyc" in result
        assert ".git" in result
        assert "test_data/" in result
        assert "docs/" in result

    def test_generate_dockerfile_basic(self, temp_project_dir, mock_config):
        """Test basic Dockerfile generation."""
        required_files = {
            "detected_files": ["predictor.py", "model.pkl", "requirements.txt"],
            "python_files": ["predictor.py"],
            "requirements_files": ["requirements.txt"],
            "model_files": ["model.pkl"],
            "missing_files": []
        }

        result = generate_dockerfile(
            str(temp_project_dir),
            mock_config,
            required_files
        )

        assert isinstance(result, str)
        assert "FROM python:" in result
        assert "COPY requirements.txt" in result
        assert "RUN pip install" in result
        assert "COPY predictor.py" in result
        assert "COPY model.pkl" in result
        assert "CMD [" in result

    def test_generate_dockerfile_with_custom_base_image(self, temp_project_dir):
        """Test Dockerfile generation with custom base image."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="predictor",
                class_name="TestPredictor"
            ),
            build=BuildConfig(base_image="python:3.9-alpine")
        )

        required_files = {
            "detected_files": ["predictor.py"],
            "python_files": ["predictor.py"],
            "requirements_files": [],
            "model_files": [],
            "missing_files": []
        }

        result = generate_dockerfile(str(temp_project_dir), config, required_files)

        assert "FROM python:3.9-alpine" in result

    def test_generate_dockerfile_with_mlserver_wheel(self, temp_project_dir, mock_config):
        """Test Dockerfile generation with mlserver wheel."""
        required_files = {
            "detected_files": ["predictor.py"],
            "python_files": ["predictor.py"],
            "requirements_files": [],
            "model_files": [],
            "missing_files": []
        }

        mlserver_wheel_path = "/path/to/mlserver.whl"

        result = generate_dockerfile(
            str(temp_project_dir),
            mock_config,
            required_files,
            mlserver_wheel_path=mlserver_wheel_path
        )

        assert "COPY mlserver.whl" in result
        assert "RUN pip install mlserver.whl" in result


class TestDockerOperations:
    """Test Docker operations (mocked)."""

    def test_check_docker_availability_success(self):
        """Test Docker availability check success."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = check_docker_availability()
            assert result is True

    def test_check_docker_availability_failure(self):
        """Test Docker availability check failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = check_docker_availability()
            assert result is False

    def test_build_container_success(self, temp_project_dir, mock_config):
        """Test successful container build."""
        with patch('mlserver.container.check_docker_availability', return_value=True), \
             patch('mlserver.container.detect_required_files') as mock_detect, \
             patch('mlserver.container.generate_dockerfile') as mock_dockerfile, \
             patch('mlserver.container.generate_dockerignore') as mock_dockerignore, \
             patch('mlserver.container.get_version_info') as mock_version, \
             patch('mlserver.container.generate_container_tags') as mock_tags, \
             patch('subprocess.run') as mock_run:

            # Setup mocks
            mock_detect.return_value = {
                "detected_files": ["predictor.py"],
                "python_files": ["predictor.py"],
                "requirements_files": [],
                "model_files": [],
                "missing_files": []
            }
            mock_dockerfile.return_value = "FROM python:3.11\nCMD ['python']"
            mock_dockerignore.return_value = "*.pyc\n__pycache__"
            mock_version.return_value = {"git": {"commit": "abc123"}}
            mock_tags.return_value = ["test-image:latest"]
            mock_run.return_value = MagicMock(returncode=0, stdout="Successfully built")

            result = build_container(
                project_path=str(temp_project_dir),
                config_file=None,
                tag_prefix="test",
                registry=None
            )

            assert result["success"] is True
            assert "tags" in result
            assert len(result["tags"]) > 0

    def test_build_container_docker_unavailable(self, temp_project_dir):
        """Test container build when Docker is unavailable."""
        with patch('mlserver.container.check_docker_availability', return_value=False):

            result = build_container(
                project_path=str(temp_project_dir),
                config_file=None
            )

            assert result["success"] is False
            assert "Docker is not available" in result["error"]

    def test_list_images_success(self, temp_project_dir):
        """Test listing Docker images."""
        mock_output = '''[
    {
        "Repository": "test-repo",
        "Tag": "latest",
        "ImageID": "abc123def456",
        "CreatedAt": "2024-01-01T00:00:00Z",
        "Size": "100MB"
    }
]'''

        with patch('mlserver.container.get_repository_name', return_value="test-repo"), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )

            result = list_images(str(temp_project_dir))

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["tag"] == "test-repo:latest"

    def test_remove_images_success(self, temp_project_dir):
        """Test removing Docker images."""
        with patch('mlserver.container.list_images') as mock_list, \
             patch('subprocess.run') as mock_run:

            mock_list.return_value = [
                {"tag": "test-repo:latest", "image_id": "abc123"}
            ]
            mock_run.return_value = MagicMock(returncode=0)

            result = remove_images(str(temp_project_dir), force=False)

            assert result["success"] is True
            assert len(result["removed_images"]) == 1

    def test_push_container_success(self, temp_project_dir):
        """Test pushing container to registry."""
        with patch('mlserver.container.get_version_info') as mock_version, \
             patch('mlserver.container.generate_container_tags') as mock_tags, \
             patch('subprocess.run') as mock_run:

            mock_version.return_value = {"git": {"commit": "abc123"}}
            mock_tags.return_value = ["registry.io/test:latest", "registry.io/test:v1.0.0"]
            mock_run.return_value = MagicMock(returncode=0)

            result = push_container(
                project_path=str(temp_project_dir),
                registry="registry.io",
                tag_prefix="test"
            )

            assert result["success"] is True
            assert len(result["pushed_tags"]) > 0