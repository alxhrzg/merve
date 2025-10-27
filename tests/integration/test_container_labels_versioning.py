"""Integration tests for container labels with hierarchical versioning (Phase 5, Task 5.4)."""

import os
import subprocess
import tempfile
import json
from pathlib import Path
import pytest


class TestContainerLabelsWithHierarchicalTags:
    """Test that container labels correctly reflect hierarchical tag information."""

    @pytest.fixture
    def temp_classifier_repo(self):
        """Create a temporary classifier repository with mlserver.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, check=True)

            # Create minimal mlserver.yaml
            config_path = Path(tmpdir) / "mlserver.yaml"
            config_content = """
server:
  title: "Test ML Server"
  host: "0.0.0.0"
  port: 8000

predictor:
  module: "tests.fixtures.mock_predictor"
  class_name: "MockPredictor"

classifier:
  name: "test_classifier"
  version: "1.0.0"
  description: "Test classifier for label verification"
  repository: "mlserver"

api:
  version: "v1"
  adapter: "records"
  endpoints:
    predict: true
"""
            config_path.write_text(config_content)

            # Create predictor file (minimal)
            predictor_dir = Path(tmpdir) / "tests" / "fixtures"
            predictor_dir.mkdir(parents=True, exist_ok=True)

            predictor_file = predictor_dir / "mock_predictor.py"
            predictor_content = '''
class MockPredictor:
    def __init__(self):
        pass

    def predict(self, data):
        return [{"prediction": "mock"}]
'''
            predictor_file.write_text(predictor_content)

            # Initial commit
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir, check=True)

            yield tmpdir

    def test_container_labels_match_hierarchical_tag(self, temp_classifier_repo):
        """Test that built container has correct labels matching the hierarchical tag."""
        repo_path = temp_classifier_repo

        from mlserver.version_control import GitVersionManager, get_mlserver_commit_hash
        from mlserver.container import generate_container_labels

        git_mgr = GitVersionManager(repo_path)

        # Create a hierarchical tag
        result = git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)
        tag_name = result["tag_name"]
        version = result["version"]
        mlserver_commit = result["mlserver_commit"]

        # Get classifier commit
        classifier_commit_result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        classifier_commit = classifier_commit_result.stdout.strip()

        # Generate container labels
        labels = generate_container_labels(
            project_path=repo_path,
            classifier_name="test_classifier"
        )

        # Verify mlserver labels
        assert "com.mlserver.commit" in labels
        # Normalize to 7 chars for comparison
        assert labels["com.mlserver.commit"][:7] == mlserver_commit[:7]

        # Verify classifier labels
        assert "com.classifier.name" in labels
        assert labels["com.classifier.name"] == "test_classifier"

        assert "com.classifier.version" in labels
        assert labels["com.classifier.version"] == version

        assert "com.classifier.git_tag" in labels
        assert labels["com.classifier.git_tag"] == tag_name

        assert "com.classifier.git_commit" in labels
        # Normalize to 7 chars for comparison
        assert labels["com.classifier.git_commit"][:7] == classifier_commit[:7]

        # Verify the tag name includes mlserver commit
        assert "-mlserver-" in tag_name
        assert mlserver_commit[:7] in tag_name

    def test_label_format_and_escaping(self, temp_classifier_repo):
        """Test that labels are properly formatted and escaped."""
        repo_path = temp_classifier_repo

        from mlserver.version_control import GitVersionManager
        from mlserver.container import generate_container_labels

        git_mgr = GitVersionManager(repo_path)

        # Create a tag
        result = git_mgr.tag_version("patch", "test_classifier", allow_missing_mlserver=False)

        # Generate labels
        labels = generate_container_labels(
            project_path=repo_path,
            classifier_name="test_classifier"
        )

        # Verify all label values are strings
        for key, value in labels.items():
            assert isinstance(value, str), f"Label {key} has non-string value: {value}"

        # Verify no newlines or special chars that would break Dockerfile
        for key, value in labels.items():
            assert "\n" not in value, f"Label {key} contains newline"
            assert "\r" not in value, f"Label {key} contains carriage return"

        # Verify OCI standard labels exist
        assert "org.opencontainers.image.version" in labels
        assert "org.opencontainers.image.created" in labels
        assert "org.opencontainers.image.title" in labels

    def test_reproducibility_from_labels(self, temp_classifier_repo):
        """Test that labels contain all info needed for reproducible rebuild."""
        repo_path = temp_classifier_repo

        from mlserver.version_control import GitVersionManager
        from mlserver.container import generate_container_labels

        git_mgr = GitVersionManager(repo_path)

        # Create a tag
        result = git_mgr.tag_version("major", "test_classifier", allow_missing_mlserver=False)

        # Generate labels
        labels = generate_container_labels(
            project_path=repo_path,
            classifier_name="test_classifier"
        )

        # Verify we have all information needed for reproducibility
        required_for_rebuild = [
            "com.classifier.git_tag",        # Full hierarchical tag
            "com.classifier.git_commit",     # Classifier repo commit
            "com.mlserver.commit",            # MLServer tool commit
        ]

        # These are optional (might not be available in temp repos)
        optional_for_rebuild = [
            "com.classifier.git_url",         # Classifier repo URL (if available)
            "com.mlserver.git_url"            # MLServer repo URL (if available)
        ]

        for label in required_for_rebuild:
            assert label in labels, f"Missing required label for reproducibility: {label}"
            assert labels[label] != "", f"Empty value for required label: {label}"

        # Check optional labels (may not exist in temp repos without remotes)
        # Just verify that at least the required ones are present
        # Optional labels like git_url are nice-to-have but not critical for testing

        # Verify the git tag can be used to extract version and commits
        git_tag = labels["com.classifier.git_tag"]
        assert "-v" in git_tag
        assert "-mlserver-" in git_tag

    def test_label_count_and_structure(self, temp_classifier_repo):
        """Test that we generate the expected number of labels."""
        repo_path = temp_classifier_repo

        from mlserver.version_control import GitVersionManager
        from mlserver.container import generate_container_labels

        git_mgr = GitVersionManager(repo_path)

        # Create a tag
        result = git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)

        # Generate labels
        labels = generate_container_labels(
            project_path=repo_path,
            classifier_name="test_classifier"
        )

        # Count label categories
        mlserver_labels = [k for k in labels if k.startswith("com.mlserver.")]
        classifier_labels = [k for k in labels if k.startswith("com.classifier.")]
        oci_labels = [k for k in labels if k.startswith("org.opencontainers.")]

        # Verify we have labels in each category
        assert len(mlserver_labels) >= 3, f"Expected at least 3 mlserver labels, got {len(mlserver_labels)}"
        assert len(classifier_labels) >= 5, f"Expected at least 5 classifier labels, got {len(classifier_labels)}"
        assert len(oci_labels) >= 3, f"Expected at least 3 OCI labels, got {len(oci_labels)}"

        # Total should be at least 15 labels
        assert len(labels) >= 15, f"Expected at least 15 total labels, got {len(labels)}"

    def test_version_extraction_from_hierarchical_tag_in_labels(self, temp_classifier_repo):
        """Test that version in labels matches version extracted from hierarchical tag."""
        repo_path = temp_classifier_repo

        from mlserver.version_control import GitVersionManager, parse_hierarchical_tag
        from mlserver.container import generate_container_labels

        git_mgr = GitVersionManager(repo_path)

        # Create a tag
        result = git_mgr.tag_version("patch", "test_classifier", allow_missing_mlserver=False)
        tag_name = result["tag_name"]

        # Parse the tag
        parsed = parse_hierarchical_tag(tag_name)

        # Generate labels
        labels = generate_container_labels(
            project_path=repo_path,
            classifier_name="test_classifier"
        )

        # Verify version in labels matches parsed version
        assert labels["com.classifier.version"] == parsed["version"]
        assert labels["org.opencontainers.image.version"] == parsed["version"]

        # Verify mlserver commit in labels matches parsed commit (normalize to 7 chars)
        assert labels["com.mlserver.commit"][:7] == parsed["mlserver_commit"][:7]
