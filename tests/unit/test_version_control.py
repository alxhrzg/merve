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