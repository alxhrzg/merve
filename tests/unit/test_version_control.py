"""Unit tests for version control functionality."""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from mlserver.version_control import (
    GitVersionManager,
    VersionControlError,
    get_version_for_push,
    safe_push_container
)


class TestGitVersionManager:
    """Test GitVersionManager functionality."""

    @patch("subprocess.run")
    def test_get_current_version_with_tag(self, mock_run):
        """Test getting version from git tag."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="v1.2.3\n"
        )

        mgr = GitVersionManager(".")
        version = mgr.get_current_version()

        assert version == "1.2.3"  # 'v' prefix removed
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_current_version_no_tags(self, mock_run):
        """Test when no tags exist."""
        mock_run.return_value = MagicMock(returncode=128)

        mgr = GitVersionManager(".")
        version = mgr.get_current_version()

        assert version is None

    @patch("subprocess.run")
    def test_get_latest_tag_info_on_tagged_commit(self, mock_run):
        """Test tag info when on a tagged commit."""
        # Mock responses for git commands
        responses = [
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --abbrev=0
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --exact-match HEAD
        ]
        mock_run.side_effect = responses

        mgr = GitVersionManager(".")
        info = mgr.get_latest_tag_info()

        assert info["tag"] == "v1.0.0"
        assert info["on_tagged_commit"] is True
        assert info["commits_since_tag"] == 0

    @patch("subprocess.run")
    def test_get_latest_tag_info_commits_behind(self, mock_run):
        """Test tag info when commits behind tag."""
        responses = [
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --abbrev=0
            MagicMock(returncode=128, stdout=""),  # git describe --tags --exact-match HEAD (fails)
            MagicMock(returncode=0, stdout="v1.0.0-5-g1234567\n"),  # git describe --tags --long
        ]
        mock_run.side_effect = responses

        mgr = GitVersionManager(".")
        info = mgr.get_latest_tag_info()

        assert info["tag"] == "v1.0.0"
        assert info["on_tagged_commit"] is False
        assert info["commits_since_tag"] == 5

    @patch("subprocess.run")
    def test_check_working_directory_clean(self, mock_run):
        """Test checking if working directory is clean."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=""  # Empty means clean
        )

        mgr = GitVersionManager(".")
        is_clean, msg = mgr.check_working_directory_clean()

        assert is_clean is True
        assert msg is None

    @patch("subprocess.run")
    def test_check_working_directory_dirty(self, mock_run):
        """Test checking dirty working directory."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M file.py\n?? newfile.txt\n"
        )

        mgr = GitVersionManager(".")
        is_clean, msg = mgr.check_working_directory_clean()

        assert is_clean is False
        assert "uncommitted changes" in msg

    @patch("subprocess.run")
    def test_tag_version_major(self, mock_run):
        """Test tagging a major version."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout="test-classifier-v1.2.3\n"),  # git tag -l pattern
            MagicMock(returncode=0),  # git tag command
        ]

        mgr = GitVersionManager(".")
        new_version = mgr.tag_version("major", "test-classifier")

        assert new_version == "2.0.0"
        # Check git tag was called with correct arguments
        tag_call = mock_run.call_args_list[-1]
        assert "test-classifier-v2.0.0" in tag_call[0][0]

    @patch("subprocess.run")
    def test_tag_version_minor(self, mock_run):
        """Test tagging a minor version."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout="test-classifier-v1.2.3\n"),  # git tag -l pattern
            MagicMock(returncode=0),  # git tag command
        ]

        mgr = GitVersionManager(".")
        new_version = mgr.tag_version("minor", "test-classifier")

        assert new_version == "1.3.0"

    @patch("subprocess.run")
    def test_tag_version_patch(self, mock_run):
        """Test tagging a patch version."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout="test-classifier-v1.2.3\n"),  # git tag -l pattern
            MagicMock(returncode=0),  # git tag command
        ]

        mgr = GitVersionManager(".")
        new_version = mgr.tag_version("patch", "test-classifier")

        assert new_version == "1.2.4"

    @patch("subprocess.run")
    def test_tag_version_dirty_working_directory(self, mock_run):
        """Test that tagging fails with dirty working directory."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M file.py\n"  # Dirty
        )

        mgr = GitVersionManager(".")
        with pytest.raises(VersionControlError) as exc_info:
            mgr.tag_version("patch", "test-classifier")

        assert "uncommitted changes" in str(exc_info.value)

    @patch("subprocess.run")
    def test_tag_version_no_previous_tags(self, mock_run):
        """Test tagging when no previous tags exist."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout=""),  # git tag -l pattern (no tags)
            MagicMock(returncode=0),  # git tag command
        ]

        mgr = GitVersionManager(".")

        # Major should be 1.0.0
        new_version = mgr.tag_version("major", "test-classifier")
        assert new_version == "1.0.0"

    @patch("subprocess.run")
    def test_check_registry_tag_exists(self, mock_run):
        """Test checking if tag exists in Docker registry."""
        mock_run.return_value = MagicMock(returncode=0)  # Success means exists

        mgr = GitVersionManager(".")
        exists = mgr.check_registry_tag_exists("registry.io", "mlserver", "1.0.0")

        assert exists is True
        mock_run.assert_called_once()
        assert "docker" in mock_run.call_args[0][0][0]

    @patch("subprocess.run")
    def test_validate_push_readiness_clean_and_tagged(self, mock_run):
        """Test validation when repository is clean and on tagged commit."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --abbrev=0
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --exact-match
        ]

        mgr = GitVersionManager(".")
        result = mgr.validate_push_readiness()

        assert result["ready"] is True
        assert len(result["errors"]) == 0
        assert result["tag_info"]["on_tagged_commit"] is True

    @patch("subprocess.run")
    def test_validate_push_readiness_not_on_tag(self, mock_run):
        """Test validation when not on a tagged commit."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # git status --porcelain (clean)
            MagicMock(returncode=0, stdout="v1.0.0\n"),  # git describe --tags --abbrev=0
            MagicMock(returncode=128),  # git describe --tags --exact-match (fails)
            MagicMock(returncode=0, stdout="v1.0.0-3-g1234567\n"),  # git describe --tags --long
        ]

        mgr = GitVersionManager(".")
        result = mgr.validate_push_readiness()

        assert result["ready"] is False
        assert len(result["errors"]) > 0
        assert "not on a tagged commit" in result["errors"][0].lower()


class TestVersionForPush:
    """Test get_version_for_push functionality."""

    @patch("mlserver.version_control.GitVersionManager")
    def test_get_version_git_tag_source(self, mock_git_class):
        """Test getting version from git tag source."""
        mock_mgr = Mock()
        mock_mgr.get_current_version.return_value = "1.2.3"
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": "test-v1.2.3",
            "on_tagged_commit": True,
            "commits_since_tag": 0
        }
        mock_git_class.return_value = mock_mgr

        version, source = get_version_for_push(".", "test-classifier", "git-tag")

        assert version == "1.2.3"
        assert "git-tag" in source

    @patch("mlserver.version_control.GitVersionManager")
    def test_get_version_git_tag_no_tags(self, mock_git_class):
        """Test error when requesting git-tag but no tags exist."""
        mock_mgr = Mock()
        mock_mgr.get_current_version.return_value = None
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": None,
            "on_tagged_commit": False,
            "commits_since_tag": None
        }
        mock_git_class.return_value = mock_mgr

        with pytest.raises(VersionControlError) as exc_info:
            get_version_for_push(".", "test-classifier", "git-tag")

        assert "no git tags found" in str(exc_info.value).lower()

    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_get_version_config_source(self, mock_git_class, mock_load):
        """Test getting version from config source."""
        mock_mgr = Mock()
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": None,
            "on_tagged_commit": False,
            "commits_since_tag": None
        }
        mock_git_class.return_value = mock_mgr

        mock_metadata = Mock()
        mock_metadata.classifier.version = "2.0.0"
        mock_load.return_value = mock_metadata

        version, source = get_version_for_push(".", None, "config")

        assert version == "2.0.0"
        assert source == "config"

    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_get_version_auto_prefers_tag_when_on_tag(self, mock_git_class, mock_load):
        """Test auto mode prefers git tag when on tagged commit."""
        mock_mgr = Mock()
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": "v1.5.0",
            "on_tagged_commit": True,
            "commits_since_tag": 0
        }
        mock_git_class.return_value = mock_mgr

        version, source = get_version_for_push(".", "auto")

        assert version == "1.5.0"  # 'v' prefix removed
        assert "git-tag" in source

    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_get_version_auto_falls_back_to_config(self, mock_git_class, mock_load):
        """Test auto mode falls back to config when not on tag."""
        mock_mgr = Mock()
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": "v1.5.0",
            "on_tagged_commit": False,
            "commits_since_tag": 3
        }
        mock_git_class.return_value = mock_mgr

        mock_metadata = Mock()
        mock_metadata.classifier.version = "2.0.0"
        mock_load.return_value = mock_metadata

        version, source = get_version_for_push(".", "auto")

        assert version == "2.0.0"
        assert "config" in source
        assert "not on tagged commit" in source


class TestSafePushContainer:
    """Test safe_push_container functionality."""

    @patch("mlserver.container.push_container")
    @patch("mlserver.version.get_git_info")
    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_safe_push_success(self, mock_git_class, mock_load, mock_git_info, mock_push):
        """Test successful safe push."""
        # Setup mocks
        mock_mgr = Mock()
        mock_mgr.validate_push_readiness.return_value = {
            "ready": True,
            "errors": [],
            "warnings": []
        }
        mock_mgr.check_registry_tag_exists.return_value = False
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": "v1.0.0",
            "on_tagged_commit": True,
            "commits_since_tag": 0
        }
        mock_git_class.return_value = mock_mgr

        mock_metadata = Mock()
        mock_metadata.classifier.repository = "mlserver"
        mock_metadata.classifier.version = "1.0.0"
        mock_load.return_value = mock_metadata

        mock_git_info.return_value = Mock()

        mock_push.return_value = {
            "success": True,
            "pushed_tags": ["registry.io/mlserver:1.0.0"]
        }

        # Call function
        result = safe_push_container(".", "registry.io")

        assert result["success"] is True
        assert result["version_used"] == "1.0.0"
        assert "git-tag" in result["version_source"]
        mock_push.assert_called_once()

    @patch("mlserver.version_control.GitVersionManager")
    def test_safe_push_validation_fails(self, mock_git_class):
        """Test push fails when validation fails."""
        mock_mgr = Mock()
        mock_mgr.validate_push_readiness.return_value = {
            "ready": False,
            "errors": ["Not on tagged commit"],
            "warnings": []
        }
        mock_git_class.return_value = mock_mgr

        result = safe_push_container(".", "registry.io", force=False)

        assert result["success"] is False
        assert "validation failed" in result["error"].lower()
        assert "Not on tagged commit" in result["validation_errors"]

    @patch("mlserver.version.get_git_info")
    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_safe_push_tag_exists_no_force(self, mock_git_class, mock_load, mock_git_info):
        """Test push fails when tag exists in registry and no force."""
        mock_mgr = Mock()
        mock_mgr.validate_push_readiness.return_value = {
            "ready": True,
            "errors": [],
            "warnings": []
        }
        mock_mgr.check_registry_tag_exists.return_value = True  # Tag exists!
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": "v1.0.0",
            "on_tagged_commit": True,
            "commits_since_tag": 0
        }
        mock_git_class.return_value = mock_mgr

        mock_metadata = Mock()
        mock_metadata.classifier.repository = "mlserver"
        mock_metadata.classifier.version = "1.0.0"
        mock_load.return_value = mock_metadata

        mock_git_info.return_value = Mock()

        result = safe_push_container(".", "registry.io", force=False)

        assert result["success"] is False
        assert "already exists" in result["error"]
        assert "Use --force" in result["details"]

    @patch("mlserver.container.push_container")
    @patch("mlserver.version.get_git_info")
    @patch("mlserver.version.load_classifier_metadata")
    @patch("mlserver.version_control.GitVersionManager")
    def test_safe_push_force_overrides_checks(self, mock_git_class, mock_load, mock_git_info, mock_push):
        """Test force flag overrides validation checks."""
        mock_mgr = Mock()
        mock_mgr.validate_push_readiness.return_value = {
            "ready": False,  # Would normally fail
            "errors": ["Working directory dirty"],
            "warnings": ["Dirty working directory"]
        }
        mock_mgr.check_registry_tag_exists.return_value = True  # Would normally fail
        mock_mgr.get_latest_tag_info.return_value = {
            "tag": None,
            "on_tagged_commit": False,
            "commits_since_tag": None
        }
        mock_git_class.return_value = mock_mgr

        mock_metadata = Mock()
        mock_metadata.classifier.repository = "mlserver"
        mock_metadata.classifier.version = "1.0.0"
        mock_load.return_value = mock_metadata

        mock_git_info.return_value = Mock()

        mock_push.return_value = {
            "success": True,
            "pushed_tags": ["registry.io/mlserver:1.0.0"]
        }

        # Call with force=True
        result = safe_push_container(".", "registry.io", force=True)

        assert result["success"] is True
        assert len(result["validation_warnings"]) > 0  # Warnings included
        mock_push.assert_called_once()


# ============================================================================
# Phase 1-4: New Hierarchical Tag Functionality Tests
# ============================================================================

class TestGetMLServerCommitHash:
    """Test get_mlserver_commit_hash() function (Phase 1)."""

    @patch("subprocess.run")
    @patch("mlserver.version_control.Path")
    def test_get_commit_from_git_repo(self, mock_path, mock_run):
        """Test getting commit hash from git repository."""
        # Mock mlserver package location
        mock_path_instance = Mock()
        mock_path_instance.parent = Mock()
        mock_path_instance.parent.parent = Mock()

        # Mock .git directory exists
        git_dir = Mock()
        git_dir.exists.return_value = True
        git_dir.is_dir.return_value = True
        mock_path_instance.parent.parent.__truediv__.return_value = git_dir

        mock_path.return_value = mock_path_instance

        # Mock git rev-parse output
        mock_run.return_value = Mock(stdout="b5dff2a\n", returncode=0)

        from mlserver.version_control import get_mlserver_commit_hash
        result = get_mlserver_commit_hash()

        assert result == "b5dff2a"
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_get_commit_no_git_repo(self, mock_run):
        """Test when mlserver is not from git repository."""
        mock_run.side_effect = Exception("Not a git repository")

        from mlserver.version_control import get_mlserver_commit_hash
        result = get_mlserver_commit_hash()

        assert result is None


class TestParseHierarchicalTag:
    """Test parse_hierarchical_tag() function (Phase 2)."""

    def test_parse_valid_tag_simple(self):
        """Test parsing valid hierarchical tag."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "sentiment-v1.0.0-mlserver-b5dff2a"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "valid"
        assert result["classifier"] == "sentiment"
        assert result["version"] == "1.0.0"
        assert result["mlserver_commit"] == "b5dff2a"

    def test_parse_valid_tag_with_underscores(self):
        """Test parsing tag with underscores in classifier name."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "rfq_likelihood_model-v2.3.1-mlserver-a3f2c9d"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "valid"
        assert result["classifier"] == "rfq_likelihood_model"
        assert result["version"] == "2.3.1"
        assert result["mlserver_commit"] == "a3f2c9d"

    def test_parse_valid_tag_long_commit(self):
        """Test parsing tag with full commit hash."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "fraud-v1.0.0-mlserver-abc123def456"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "valid"
        assert result["mlserver_commit"] == "abc123def456"

    def test_parse_invalid_tag_missing_mlserver(self):
        """Test parsing tag without mlserver suffix."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "sentiment-v1.0.0"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "invalid"
        assert result["classifier"] is None

    def test_parse_invalid_tag_missing_v_prefix(self):
        """Test parsing tag without 'v' prefix on version."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "sentiment-1.0.0-mlserver-b5dff2a"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "invalid"

    def test_parse_invalid_tag_uppercase(self):
        """Test parsing tag with uppercase (not allowed)."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "Sentiment-v1.0.0-mlserver-b5dff2a"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "invalid"

    def test_parse_invalid_tag_bad_version(self):
        """Test parsing tag with invalid version format."""
        from mlserver.version_control import parse_hierarchical_tag

        tag = "sentiment-v1.0-mlserver-b5dff2a"
        result = parse_hierarchical_tag(tag)

        assert result["format"] == "invalid"


class TestExtractClassifierName:
    """Test extract_classifier_name() function (Phase 2)."""

    def test_extract_from_simple_name(self):
        """Test extracting classifier name from simple name."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("sentiment")
        assert result == "sentiment"

    def test_extract_from_full_tag(self):
        """Test extracting classifier name from full hierarchical tag."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("sentiment-v1.0.0-mlserver-b5dff2a")
        assert result == "sentiment"

    def test_extract_with_underscores(self):
        """Test extracting name with underscores."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("fraud_detection")
        assert result == "fraud_detection"

    def test_extract_with_hyphens(self):
        """Test extracting name with hyphens."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("rfq-likelihood")
        assert result == "rfq-likelihood"

    def test_extract_invalid_uppercase(self):
        """Test that uppercase names are rejected."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("Sentiment")
        assert result is None

    def test_extract_invalid_special_chars(self):
        """Test that special characters are rejected."""
        from mlserver.version_control import extract_classifier_name

        result = extract_classifier_name("sentiment@model")
        assert result is None


class TestGetTagCommits:
    """Test get_tag_commits() function (Phase 2)."""

    @patch("subprocess.run")
    def test_get_commits_from_valid_tag(self, mock_run):
        """Test getting commits from a valid hierarchical tag."""
        from mlserver.version_control import get_tag_commits

        # Mock git operations: git rev-list, then git rev-parse --short
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123def456789\n"),  # git rev-list
            Mock(returncode=0, stdout="abc123d\n"),  # git rev-parse --short=7
        ]

        tag = "sentiment-v1.0.0-mlserver-b5dff2a"
        result = get_tag_commits(tag, ".")

        assert result["tag_valid"] is True
        assert result["mlserver_commit"] == "b5dff2a"
        assert result["classifier_commit"] == "abc123d"  # Shortened to 7 chars

    @patch("subprocess.run")
    def test_get_commits_from_invalid_tag(self, mock_run):
        """Test handling invalid tag format."""
        from mlserver.version_control import get_tag_commits

        tag = "invalid-tag-format"
        result = get_tag_commits(tag, ".")

        assert result["tag_valid"] is False
        assert result["mlserver_commit"] is None
        assert result["classifier_commit"] is None

    @patch("subprocess.run")
    def test_get_commits_tag_not_exists(self, mock_run):
        """Test handling non-existent tag."""
        from mlserver.version_control import get_tag_commits

        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        tag = "sentiment-v1.0.0-mlserver-b5dff2a"
        result = get_tag_commits(tag, ".")

        assert result["tag_valid"] is False


class TestTagVersionEnhanced:
    """Test enhanced tag_version() with dict return (Phase 4)."""

    @patch("mlserver.version_control.get_mlserver_commit_hash")
    @patch("subprocess.run")
    def test_tag_version_returns_dict(self, mock_run, mock_commit):
        """Test that tag_version returns dict with all information."""
        mock_commit.return_value = "b5dff2a"

        # Mock git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # Working directory clean
            Mock(returncode=0, stdout="sentiment-v1.0.0-mlserver-b5dff2a\n"),  # Existing tags
            Mock(returncode=0),  # Tag creation
        ]

        mgr = GitVersionManager(".")
        result = mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)

        assert isinstance(result, dict)
        assert "version" in result
        assert "tag_name" in result
        assert "mlserver_commit" in result
        assert "previous_version" in result
        assert result["mlserver_commit"] == "b5dff2a"

    @patch("mlserver.version_control.get_mlserver_commit_hash")
    @patch("subprocess.run")
    def test_tag_version_with_allow_missing_mlserver(self, mock_run, mock_commit):
        """Test tag creation when mlserver commit unavailable."""
        mock_commit.return_value = None

        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # Working directory clean
            Mock(returncode=128),  # No existing tags
            Mock(returncode=0),  # Tag creation
        ]

        mgr = GitVersionManager(".")
        result = mgr.tag_version("minor", "sentiment", allow_missing_mlserver=True)

        assert result["mlserver_commit"] == "dev"
        assert result["version"] == "0.1.0"  # First minor version

    @patch("mlserver.version_control.get_mlserver_commit_hash")
    @patch("subprocess.run")
    def test_tag_version_error_without_mlserver_commit(self, mock_run, mock_commit):
        """Test that error is raised when mlserver commit unavailable and not allowed."""
        mock_commit.return_value = None

        mock_run.return_value = Mock(returncode=0, stdout="")

        mgr = GitVersionManager(".")

        with pytest.raises(VersionControlError, match="Could not determine mlserver commit"):
            mgr.tag_version("patch", "sentiment", allow_missing_mlserver=False)


class TestHierarchicalTagIntegration:
    """Integration tests for hierarchical tag workflow."""

    @patch("mlserver.version_control.get_mlserver_commit_hash")
    @patch("subprocess.run")
    def test_create_and_parse_tag_roundtrip(self, mock_run, mock_commit):
        """Test creating a tag and parsing it back."""
        from mlserver.version_control import parse_hierarchical_tag

        mock_commit.return_value = "b5dff2a"

        # Mock successful tag creation
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # Working directory clean
            Mock(returncode=128),  # No existing tags
            Mock(returncode=0),  # Tag creation success
        ]

        mgr = GitVersionManager(".")
        result = mgr.tag_version("minor", "sentiment")

        # Parse the created tag
        parsed = parse_hierarchical_tag(result["tag_name"])

        assert parsed["format"] == "valid"
        assert parsed["classifier"] == "sentiment"
        assert parsed["version"] == result["version"]
        assert parsed["mlserver_commit"] == "b5dff2a"

    @patch("mlserver.version_control.get_mlserver_commit_hash")
    @patch("subprocess.run")
    def test_version_bumping_sequence(self, mock_run, mock_commit):
        """Test sequence of version bumps."""
        mock_commit.return_value = "b5dff2a"

        # Simulate patch -> minor -> major bumps
        existing_versions = [
            "sentiment-v1.0.0-mlserver-b5dff2a",
            "sentiment-v1.0.1-mlserver-b5dff2a",
            "sentiment-v1.1.0-mlserver-b5dff2a"
        ]

        mgr = GitVersionManager(".")

        for idx, bump_type in enumerate(["patch", "minor", "major"]):
            mock_run.side_effect = [
                Mock(returncode=0, stdout=""),  # Working directory clean
                Mock(returncode=0, stdout=existing_versions[idx] + "\n"),  # Previous tag
                Mock(returncode=0),  # Tag creation
            ]

            result = mgr.tag_version(bump_type, "sentiment")

            if bump_type == "patch":
                assert result["version"] == "1.0.1"
            elif bump_type == "minor":
                assert result["version"] == "1.1.0"
            elif bump_type == "major":
                assert result["version"] == "2.0.0"