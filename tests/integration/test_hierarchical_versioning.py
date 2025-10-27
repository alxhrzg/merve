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
        """Test tagging workflow for single classifier with hierarchical tags."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Initially no tags
        version = git_mgr.get_current_version("sentiment")
        assert version is None

        # Tag the classifier (returns dict in Phase 4)
        result = git_mgr.tag_version("minor", "sentiment", allow_missing_mlserver=False)
        assert isinstance(result, dict)
        assert result["version"] == "0.1.0"
        assert result["mlserver_commit"] is not None
        assert result["previous_version"] is None

        # Tag name should include mlserver commit
        assert result["tag_name"].startswith("sentiment-v0.1.0-mlserver-")

        # Verify tag was created
        version = git_mgr.get_current_version("sentiment")
        assert version == "0.1.0"

        # Check tag info
        tag_info = git_mgr.get_latest_tag_info("sentiment")
        assert tag_info["tag"].startswith("sentiment-v0.1.0-mlserver-")
        assert tag_info["on_tagged_commit"] is True
        assert tag_info["commits_since_tag"] == 0

    def test_multi_classifier_independent_tagging(self, multi_classifier_config):
        """Test that multiple classifiers can be tagged independently with hierarchical tags."""
        repo_path, config_path = multi_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag sentiment classifier with patch bump (returns dict)
        sentiment_result = git_mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)
        assert sentiment_result["version"] == "0.0.1"
        assert sentiment_result["mlserver_commit"] is not None

        # Tag intent classifier with minor bump (returns dict)
        intent_result = git_mgr.tag_version("minor", "intent", allow_missing_mlserver=False)
        assert intent_result["version"] == "0.1.0"
        assert intent_result["mlserver_commit"] is not None

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
        git_mgr.tag_version("major", "sentiment", allow_missing_mlserver=False)

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
        assert status["intent"]["recommendation"] == "mlserver tag --classifier intent <major|minor|patch>"

    def test_version_bump_sequence(self, single_classifier_config):
        """Test proper version bumping sequence with hierarchical tags."""
        repo_path, config_path = single_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # First tag - patch (returns dict)
        result1 = git_mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)
        assert result1["version"] == "0.0.1"
        assert result1["previous_version"] is None

        # Second tag - minor (should bump minor and reset patch)
        result2 = git_mgr.tag_version("minor", "sentiment", allow_missing_mlserver=False)
        assert result2["version"] == "0.1.0"
        assert result2["previous_version"] == "0.0.1"

        # Third tag - patch (should increment patch)
        result3 = git_mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)
        assert result3["version"] == "0.1.1"
        assert result3["previous_version"] == "0.1.0"

        # Fourth tag - major (should bump major and reset others)
        result4 = git_mgr.tag_version("major", "sentiment", allow_missing_mlserver=False)
        assert result4["version"] == "1.0.0"
        assert result4["previous_version"] == "0.1.1"

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
        """Test that tags follow the hierarchical format with mlserver commits."""
        repo_path, config_path = multi_classifier_config

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag different classifiers
        sentiment_result = git_mgr.tag_version("major", "sentiment", allow_missing_mlserver=False)
        intent_result = git_mgr.tag_version("minor", "intent", allow_missing_mlserver=False)

        # Get all tags from git
        result = subprocess.run(
            ["git", "tag"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )

        tags = result.stdout.strip().split('\n')

        # Check for hierarchical format with mlserver commits
        sentiment_tag_found = any(tag.startswith("sentiment-v1.0.0-mlserver-") for tag in tags)
        intent_tag_found = any(tag.startswith("intent-v0.1.0-mlserver-") for tag in tags)

        assert sentiment_tag_found, f"Expected sentiment-v1.0.0-mlserver-* in {tags}"
        assert intent_tag_found, f"Expected intent-v0.1.0-mlserver-* in {tags}"

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

        # Tag the classifier with hierarchical format
        result = git_mgr.tag_version("minor", "sentiment", allow_missing_mlserver=False)
        assert result["version"] == "0.1.0"

        # Should get version from git tag (just the version number, not mlserver suffix)
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


class TestValidatePushReadiness:
    """Test validate_push_readiness() function comprehensively."""

    @pytest.fixture
    def temp_git_repo_with_tag(self):
        """Create a temporary git repo with a tagged commit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, check=True)

            # Create initial commit
            dummy_file = Path(tmpdir) / "README.md"
            dummy_file.write_text("# Test Project")
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir, check=True)

            yield tmpdir

    def test_validate_ready_on_tagged_commit(self, temp_git_repo_with_tag):
        """Test validation passes when on tagged commit with clean working directory."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag the commit
        git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)

        # Validate - should be ready
        validation = git_mgr.validate_push_readiness("test_classifier")

        assert validation["ready"] is True
        assert len(validation["errors"]) == 0
        assert validation["tag_info"]["on_tagged_commit"] is True

    def test_validate_not_ready_uncommitted_changes(self, temp_git_repo_with_tag):
        """Test validation fails with uncommitted changes."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag the commit
        git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)

        # Create uncommitted changes
        dirty_file = Path(repo_path) / "dirty.txt"
        dirty_file.write_text("uncommitted")

        # Validate - should not be ready
        validation = git_mgr.validate_push_readiness("test_classifier")

        assert validation["ready"] is False
        assert len(validation["errors"]) > 0
        assert any("uncommitted" in error.lower() for error in validation["errors"])

    def test_validate_force_flag_allows_uncommitted(self, temp_git_repo_with_tag):
        """Test force flag allows push with uncommitted changes (as warning)."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag the commit
        git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)

        # Create uncommitted changes
        dirty_file = Path(repo_path) / "dirty.txt"
        dirty_file.write_text("uncommitted")

        # Validate with force - should be ready with warnings
        validation = git_mgr.validate_push_readiness("test_classifier", force=True)

        assert validation["ready"] is True
        assert len(validation["errors"]) == 0
        assert len(validation["warnings"]) > 0
        assert any("uncommitted" in warning.lower() for warning in validation["warnings"])

    def test_validate_not_ready_commits_since_tag(self, temp_git_repo_with_tag):
        """Test validation fails when there are commits after the tag."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Tag the commit
        git_mgr.tag_version("minor", "test_classifier", allow_missing_mlserver=False)

        # Make a new commit
        new_file = Path(repo_path) / "new_file.txt"
        new_file.write_text("new content")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "New commit"], cwd=repo_path, check=True)

        # Validate - should not be ready
        validation = git_mgr.validate_push_readiness("test_classifier")

        assert validation["ready"] is False
        assert len(validation["errors"]) > 0
        assert any("not on a tagged commit" in error for error in validation["errors"])
        assert validation["tag_info"]["on_tagged_commit"] is False
        assert validation["tag_info"]["commits_since_tag"] == 1

    def test_validate_not_ready_no_tags(self, temp_git_repo_with_tag):
        """Test validation fails when there are no tags."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Don't tag - validate should fail
        validation = git_mgr.validate_push_readiness("test_classifier")

        assert validation["ready"] is False
        assert len(validation["errors"]) > 0
        assert any("No version tags found" in error for error in validation["errors"])
        assert any("mlserver tag" in error for error in validation["errors"])

    def test_validate_error_messages_include_classifier_name(self, temp_git_repo_with_tag):
        """Test error messages include classifier name when provided."""
        repo_path = temp_git_repo_with_tag

        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(repo_path)

        # Validate without tags
        validation = git_mgr.validate_push_readiness("my_classifier")

        assert validation["ready"] is False
        # Should mention the classifier name in error messages
        error_text = " ".join(validation["errors"])
        assert "my_classifier" in error_text
        assert "mlserver tag --classifier my_classifier" in error_text


class TestPhase2HierarchicalTagParsing:
    """Test Phase 2 hierarchical tag parsing functions (integration tests)."""

    @pytest.fixture
    def temp_git_repo_with_tags(self):
        """Create a temporary git repository with hierarchical tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, check=True)

            # Create initial commit
            dummy_file = Path(tmpdir) / "README.md"
            dummy_file.write_text("# Test Project")
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir, check=True)

            yield tmpdir

    def test_parse_hierarchical_tag_from_real_repo(self, temp_git_repo_with_tags):
        """Test parsing hierarchical tags from a real git repository."""
        repo_path = temp_git_repo_with_tags

        from mlserver.version_control import GitVersionManager, parse_hierarchical_tag

        git_mgr = GitVersionManager(repo_path)

        # Create a hierarchical tag
        result = git_mgr.tag_version("minor", "sentiment", allow_missing_mlserver=False)
        tag_name = result["tag_name"]

        # Parse the tag we just created
        parsed = parse_hierarchical_tag(tag_name)

        assert parsed["format"] == "valid"
        assert parsed["classifier"] == "sentiment"
        assert parsed["version"] == "0.1.0"
        assert parsed["mlserver_commit"] is not None
        assert len(parsed["mlserver_commit"]) >= 7

    def test_extract_classifier_name_integration(self, temp_git_repo_with_tags):
        """Test extracting classifier name from full tags in real workflow."""
        repo_path = temp_git_repo_with_tags

        from mlserver.version_control import GitVersionManager, extract_classifier_name

        git_mgr = GitVersionManager(repo_path)

        # Create tags for multiple classifiers
        sentiment_result = git_mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)
        intent_result = git_mgr.tag_version("minor", "intent", allow_missing_mlserver=False)

        # Extract classifier names from full tags
        sentiment_name = extract_classifier_name(sentiment_result["tag_name"])
        intent_name = extract_classifier_name(intent_result["tag_name"])

        assert sentiment_name == "sentiment"
        assert intent_name == "intent"

        # Also test with simple names
        assert extract_classifier_name("fraud") == "fraud"

    def test_get_tag_commits_from_real_repo(self, temp_git_repo_with_tags):
        """Test getting commits from real git tags."""
        repo_path = temp_git_repo_with_tags

        from mlserver.version_control import GitVersionManager, get_tag_commits

        git_mgr = GitVersionManager(repo_path)

        # Create a tag
        result = git_mgr.tag_version("major", "churn", allow_missing_mlserver=False)
        tag_name = result["tag_name"]

        # Get commits from the tag
        tag_commits = get_tag_commits(tag_name, repo_path)

        assert tag_commits["tag_valid"] is True
        assert tag_commits["mlserver_commit"] == result["mlserver_commit"]
        assert tag_commits["classifier_commit"] is not None
        assert len(tag_commits["classifier_commit"]) == 7  # Short hash

    def test_roundtrip_tag_create_parse_validate(self, temp_git_repo_with_tags):
        """Test complete workflow: create tag → parse → validate commits."""
        repo_path = temp_git_repo_with_tags

        from mlserver.version_control import (
            GitVersionManager,
            parse_hierarchical_tag,
            get_tag_commits,
            get_mlserver_commit_hash
        )

        git_mgr = GitVersionManager(repo_path)

        # Get current mlserver commit
        mlserver_commit = get_mlserver_commit_hash()

        # Create a tag
        result = git_mgr.tag_version("patch", "fraud", allow_missing_mlserver=False)
        tag_name = result["tag_name"]

        # Parse the created tag
        parsed = parse_hierarchical_tag(tag_name)
        assert parsed["format"] == "valid"
        assert parsed["mlserver_commit"] == mlserver_commit

        # Get tag commits
        tag_commits = get_tag_commits(tag_name, repo_path)
        assert tag_commits["tag_valid"] is True
        assert tag_commits["mlserver_commit"] == mlserver_commit

        # Verify tag exists in git
        result = subprocess.run(
            ["git", "tag", "-l", tag_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        assert tag_name in result.stdout