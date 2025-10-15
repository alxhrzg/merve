"""Integration tests for CLI v2 workflow using mock classifier repo."""

import tempfile
import time
import requests
import pytest
from pathlib import Path
import sys
import os

# Add parent directory to path to import fixtures
sys.path.insert(0, str(Path(__file__).parent.parent))
from fixtures.mock_classifier_repo import MockClassifierRepo


class TestCLIv2WorkflowIntegration:
    """Test the complete CLI v2 workflow with mock classifier repo."""

    @pytest.fixture
    def single_classifier_repo(self):
        """Create a single classifier repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = MockClassifierRepo(tmpdir, multi_classifier=False)
            yield repo
            repo.cleanup()

    @pytest.fixture
    def multi_classifier_repo(self):
        """Create a multi-classifier repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = MockClassifierRepo(tmpdir, multi_classifier=True)
            yield repo
            repo.cleanup()

    def test_single_classifier_serve(self, single_classifier_repo):
        """Test serving a single classifier."""
        # Start server in background
        process = single_classifier_repo.serve_in_background(port=8080)

        try:
            # Wait for server to start
            time.sleep(3)

            # Test health endpoint
            response = requests.get("http://localhost:8080/healthz")
            assert response.status_code == 200
            health = response.json()
            assert health["status"] == "ok"

            # Test prediction
            payload = {
                "payload": {
                    "records": [
                        {"f1": 1.0, "f2": 2.0, "f3": 3.0, "f4": 4.0, "f5": 5.0}
                    ]
                }
            }
            response = requests.post("http://localhost:8080/predict", json=payload)
            assert response.status_code == 200
            result = response.json()
            assert "predictions" in result

        finally:
            # Clean up
            process.terminate()
            process.wait(timeout=5)

    def test_multi_classifier_serve(self, multi_classifier_repo):
        """Test serving multiple classifiers."""
        # Test sentiment classifier
        process1 = multi_classifier_repo.serve_in_background(
            classifier_name="sentiment", port=8081
        )

        # Test intent classifier
        process2 = multi_classifier_repo.serve_in_background(
            classifier_name="intent", port=8082
        )

        try:
            # Wait for servers to start
            time.sleep(3)

            # Test sentiment server
            response = requests.get("http://localhost:8081/healthz")
            assert response.status_code == 200

            # Test intent server
            response = requests.get("http://localhost:8082/healthz")
            assert response.status_code == 200

        finally:
            # Clean up
            process1.terminate()
            process1.wait(timeout=5)
            process2.terminate()
            process2.wait(timeout=5)

    def test_version_command(self, single_classifier_repo):
        """Test the version command."""
        result = single_classifier_repo.run_cli_command("version")
        assert result.returncode == 0
        assert "test-classifier" in result.stdout
        assert "1.0.0" in result.stdout

    def test_tag_workflow(self, single_classifier_repo):
        """Test the tagging workflow."""
        # Check initial status (no tags)
        result = single_classifier_repo.run_cli_command("tag")
        assert result.returncode == 0
        assert "test-classifier" in result.stdout

        # Tag with minor bump
        result = single_classifier_repo.run_cli_command(
            "tag", "minor", "--classifier", "test-classifier"
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

        # Check status again (should show tagged)
        result = single_classifier_repo.run_cli_command("tag")
        assert result.returncode == 0
        assert "0.1.0" in result.stdout
        assert "Ready" in result.stdout

    def test_multi_classifier_tagging(self, multi_classifier_repo):
        """Test tagging multiple classifiers independently."""
        # Tag sentiment with patch
        result = multi_classifier_repo.run_cli_command(
            "tag", "patch", "--classifier", "sentiment"
        )
        assert result.returncode == 0
        assert "0.0.1" in result.stdout

        # Tag intent with minor
        result = multi_classifier_repo.run_cli_command(
            "tag", "minor", "--classifier", "intent"
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

        # Check status table
        result = multi_classifier_repo.run_cli_command("tag")
        assert result.returncode == 0
        assert "sentiment" in result.stdout
        assert "0.0.1" in result.stdout
        assert "intent" in result.stdout
        assert "0.1.0" in result.stdout

    def test_build_command(self, single_classifier_repo):
        """Test building Docker container."""
        # Make a change and tag
        single_classifier_repo.make_change()
        single_classifier_repo.run_cli_command(
            "tag", "minor", "--classifier", "test-classifier"
        )

        # Build container
        result = single_classifier_repo.run_cli_command("build")

        # Note: This will fail if Docker is not available
        # Check for either success or Docker-not-found error
        if "docker" in result.stderr.lower() and "not found" in result.stderr.lower():
            pytest.skip("Docker not available")
        else:
            assert result.returncode == 0
            assert "Successfully built" in result.stdout or "Building" in result.stdout

    def test_info_command(self, single_classifier_repo):
        """Test the info command for getting server information."""
        # Start server
        process = single_classifier_repo.serve_in_background(port=8083)

        try:
            # Wait for server to start
            time.sleep(3)

            # Get info
            response = requests.get("http://localhost:8083/info")
            assert response.status_code == 200
            info = response.json()

            assert info["classifier"] == "test-classifier"
            assert info["version"] == "1.0.0"
            assert info["repository"] == "mlserver"

        finally:
            # Clean up
            process.terminate()
            process.wait(timeout=5)

    def test_list_classifiers(self, multi_classifier_repo):
        """Test listing available classifiers."""
        result = multi_classifier_repo.run_cli_command("list")
        assert result.returncode == 0
        assert "sentiment" in result.stdout
        assert "intent" in result.stdout
        assert "Available Classifiers" in result.stdout