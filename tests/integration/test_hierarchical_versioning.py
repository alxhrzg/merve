"""Integration tests for hierarchical versioning and tagging system."""

import os
import subprocess
import tempfile
import shutil
import yaml
from pathlib import Path
import pytest


class TestHierarchicalVersioningWorkflow:
    """Test the complete hierarchical versioning workflow."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, check=True)

            yield tmpdir

    @pytest.fixture
    def single_classifier_config(self, temp_git_repo):
        """Create a single classifier configuration."""
        config = {
            "server": {
                "title": "Test ML Server",
                "host": "0.0.0.0",
                "port": 8000
            },
            "predictor": {
                "module": "tests.fixtures.mock_predictor",
                "class_name": "MockPredictor"
            },
            "classifier": {
                "name": "sentiment",
                "version": "1.0.0",
                "description": "Sentiment analysis classifier",
                "repository": "mlserver"
            },
            "api": {
                "version": "v1",
                "adapter": "records",
                "endpoints": {"predict": True}
            }
        }

        config_path = Path(temp_git_repo) / "mlserver.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True)

        return temp_git_repo, config_path

    @pytest.fixture
    def multi_classifier_config(self, temp_git_repo):
        """Create a multi-classifier configuration."""
        config = {
            "classifiers": [
                {
                    "name": "sentiment",
                    "server": {
                        "title": "Sentiment Analysis Server"
                    },
                    "predictor": {
                        "module": "tests.fixtures.mock_predictor",
                        "class_name": "MockPredictor"
                    },
                    "classifier": {
                        "name": "sentiment",
                        "version": "1.0.0",
                        "description": "Sentiment analysis",
                        "repository": "mlserver"
                    },
                    "api": {
                        "adapter": "records",
                        "endpoints": {"predict": True}
                    }
                },
                {
                    "name": "intent",
                    "server": {
                        "title": "Intent Classification Server"
                    },
                    "predictor": {
                        "module": "tests.fixtures.mock_predictor",
                        "class_name": "MockPredictor"
                    },
                    "classifier": {
                        "name": "intent",
                        "version": "2.0.0",
                        "description": "Intent classification",
                        "repository": "mlserver"
                    },
                    "api": {
                        "adapter": "records",
                        "endpoints": {"predict": True}
                    }
                }
            ],
            "default_classifier": "sentiment"
        }

        config_path = Path(temp_git_repo) / "mlserver.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_git_repo, check=True)

        return temp_git_repo, config_path

    def test_single_classifier_tagging(self, single_classifier_config):
        """Test tagging workflow for single classifier."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Initially no tags
        version = git_mgr.get_current_version("sentiment")
        assert version is None

        # Tag the classifier
        new_version = git_mgr.tag_version("minor", "sentiment")
        assert new_version == "0.1.0"

        # Verify tag was created
        version = git_mgr.get_current_version("sentiment")
        assert version == "0.1.0"

        # Check tag info
        tag_info = git_mgr.get_latest_tag_info("sentiment")
        assert tag_info["tag"] == "sentiment-v0.1.0"
        assert tag_info["on_tagged_commit"] is True
        assert tag_info["commits_since_tag"] == 0

    def test_multi_classifier_independent_tagging(self, multi_classifier_config):
        """Test that multiple classifiers can be tagged independently."""
        repo_path, config_path = multi_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag sentiment classifier with patch bump
        sentiment_version = git_mgr.tag_version("patch", "sentiment")
        assert sentiment_version == "0.0.1"

        # Tag intent classifier with minor bump
        intent_version = git_mgr.tag_version("minor", "intent")
        assert intent_version == "0.1.0"

        # Verify both tags exist independently
        assert git_mgr.get_current_version("sentiment") == "0.0.1"
        assert git_mgr.get_current_version("intent") == "0.1.0"

        # Make a new commit
        dummy_file = Path(repo_path) / "update.txt"
        dummy_file.write_text("update")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Update"], cwd=repo_path, check=True)

        # Check that both classifiers show commits since tag
        sentiment_info = git_mgr.get_latest_tag_info("sentiment")
        intent_info = git_mgr.get_latest_tag_info("intent")

        assert sentiment_info["on_tagged_commit"] is False
        assert sentiment_info["commits_since_tag"] == 1

        assert intent_info["on_tagged_commit"] is False
        assert intent_info["commits_since_tag"] == 1

    def test_tag_status_table(self, multi_classifier_config):
        """Test getting status for all classifiers."""
        repo_path, config_path = multi_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag only sentiment classifier
        git_mgr.tag_version("major", "sentiment")

        # Get status for all classifiers
        status = git_mgr.get_all_classifiers_tag_status(str(config_path))

        assert "sentiment" in status
        assert "intent" in status

        # Sentiment should be ready (on tagged commit)
        assert status["sentiment"]["on_tagged_commit"] is True
        assert status["sentiment"]["status"] == "Ready"
        assert status["sentiment"]["current_version"] == "1.0.0"

        # Intent should have no tags
        assert status["intent"]["on_tagged_commit"] is False
        assert status["intent"]["status"] == "No tags"
        assert status["intent"]["recommendation"] == "ml_server tag --classifier intent <major|minor|patch>"

    def test_version_bump_sequence(self, single_classifier_config):
        """Test proper version bumping sequence."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # First tag - patch
        version1 = git_mgr.tag_version("patch", "sentiment")
        assert version1 == "0.0.1"

        # Second tag - minor (should bump minor and reset patch)
        version2 = git_mgr.tag_version("minor", "sentiment")
        assert version2 == "0.1.0"

        # Third tag - patch (should increment patch)
        version3 = git_mgr.tag_version("patch", "sentiment")
        assert version3 == "0.1.1"

        # Fourth tag - major (should bump major and reset others)
        version4 = git_mgr.tag_version("major", "sentiment")
        assert version4 == "1.0.0"

    def test_validate_push_readiness(self, single_classifier_config):
        """Test push validation with hierarchical tags."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Initially not ready (no tags)
        validation = git_mgr.validate_push_readiness("sentiment")
        assert validation["ready"] is False
        assert "No version tags found for classifier 'sentiment'" in validation["errors"][0]

        # Tag the classifier
        git_mgr.tag_version("minor", "sentiment")

        # Now should be ready
        validation = git_mgr.validate_push_readiness("sentiment")
        assert validation["ready"] is True
        assert len(validation["errors"]) == 0

        # Make a new commit
        dummy_file = Path(repo_path) / "newfile.txt"
        dummy_file.write_text("content")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "New commit"], cwd=repo_path, check=True)

        # Should not be ready (commits since tag)
        validation = git_mgr.validate_push_readiness("sentiment")
        assert validation["ready"] is False
        assert "not on a tagged commit" in validation["errors"][0].lower()

    def test_dirty_working_directory_prevents_tagging(self, single_classifier_config):
        """Test that uncommitted changes prevent tagging."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager, VersionControlError

        git_mgr = GitVersionManager(repo_path)

        # Create uncommitted file
        dirty_file = Path(repo_path) / "dirty.txt"
        dirty_file.write_text("uncommitted changes")

        # Should raise error when trying to tag
        with pytest.raises(VersionControlError) as exc_info:
            git_mgr.tag_version("patch", "sentiment")

        assert "uncommitted changes" in str(exc_info.value).lower()

    def test_classifier_name_in_tag_format(self, multi_classifier_config):
        """Test that tags follow the hierarchical format."""
        repo_path, config_path = multi_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag different classifiers
        git_mgr.tag_version("major", "sentiment")
        git_mgr.tag_version("minor", "intent")

        # Get all tags from git
        result = subprocess.run(
            ["git", "tag"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        tags = result.stdout.strip().split('\n')

        assert "sentiment-v1.0.0" in tags
        assert "intent-v0.1.0" in tags

    def test_get_version_for_push(self, single_classifier_config):
        """Test get_version_for_push with hierarchical tags."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import (
            GitVersionManager,
            get_version_for_push,
            VersionControlError
        )

        git_mgr = GitVersionManager(repo_path)

        # Should fail with no tags
        with pytest.raises(VersionControlError):
            get_version_for_push(repo_path, "sentiment", "git-tag")

        # Tag the classifier
        git_mgr.tag_version("minor", "sentiment")

        # Should get version from git tag
        version, source = get_version_for_push(repo_path, "sentiment", "git-tag")
        assert version == "0.1.0"
        assert "git-tag" in source

        # Auto mode should prefer git tag when on tagged commit
        version, source = get_version_for_push(repo_path, "sentiment", "auto")
        assert version == "0.1.0"
        assert "git-tag" in source

        # Make a commit to move off tagged commit
        dummy_file = Path(repo_path) / "update.txt"
        dummy_file.write_text("update")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Update"], cwd=repo_path, check=True)

        # Auto mode should fall back to config
        version, source = get_version_for_push(repo_path, "sentiment", "auto")
        assert version == "1.0.0"  # From config
        assert "config" in source
        assert "not on tagged commit" in source