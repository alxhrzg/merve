"""
Enhanced version control utilities for safe container versioning and registry management.
"""
import subprocess
import re
from typing import Optional, Tuple, Literal, Dict, Any
from pathlib import Path
import semver


class VersionControlError(Exception):
    """Version control related errors."""
    pass


class GitVersionManager:
    """Manage git-based versioning for ML models."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)

    def get_current_version(self, classifier_name: Optional[str] = None) -> Optional[str]:
        """Get the current version from git tags.

        Args:
            classifier_name: If provided, looks for classifier-specific tags (e.g., 'sentiment-v1.0.0')
        """
        try:
            if classifier_name:
                # Look for classifier-specific tags
                pattern = f"{classifier_name}-v*"
                result = subprocess.run(
                    ["git", "tag", "-l", pattern, "--sort=-version:refname"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode == 0 and result.stdout.strip():
                    tags = result.stdout.strip().split('\n')
                    if tags:
                        latest_tag = tags[0]
                        # Extract version from classifier-v1.0.0 format
                        version_part = latest_tag.split('-v', 1)[1] if '-v' in latest_tag else None
                        return version_part
                return None
            else:
                # Legacy: get any tag
                result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode == 0:
                    tag = result.stdout.strip()
                    # Remove 'v' prefix if present
                    return tag[1:] if tag.startswith('v') else tag
                return None

        except Exception:
            return None

    def get_latest_tag_info(self, classifier_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about the latest tag.

        Args:
            classifier_name: If provided, looks for classifier-specific tags
        """
        try:
            # Get the latest tag
            if classifier_name:
                pattern = f"{classifier_name}-v*"
                tag_result = subprocess.run(
                    ["git", "tag", "-l", pattern, "--sort=-version:refname"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if tag_result.returncode == 0 and tag_result.stdout.strip():
                    tags = tag_result.stdout.strip().split('\n')
                    latest_tag = tags[0] if tags else None
                else:
                    latest_tag = None
            else:
                tag_result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                latest_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None

            if not latest_tag:
                return {
                    "tag": None,
                    "commits_since_tag": None,
                    "on_tagged_commit": False,
                    "classifier": classifier_name
                }

            # Check if HEAD is exactly on this tag
            exact_result = subprocess.run(
                ["git", "describe", "--tags", "--exact-match", "HEAD"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=False
            )

            on_tagged_commit = (exact_result.returncode == 0 and
                              exact_result.stdout.strip() == latest_tag)

            # Get commits since last tag
            if not on_tagged_commit:
                describe_result = subprocess.run(
                    ["git", "describe", "--tags", "--long"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

                if describe_result.returncode == 0:
                    # Format: v1.0.0-5-g1234567 (5 commits since tag)
                    parts = describe_result.stdout.strip().split('-')
                    if len(parts) >= 2:
                        commits_since = int(parts[-2])
                    else:
                        commits_since = 0
                else:
                    commits_since = None
            else:
                commits_since = 0

            return {
                "tag": latest_tag,
                "commits_since_tag": commits_since,
                "on_tagged_commit": on_tagged_commit,
                "classifier": classifier_name
            }

        except Exception as e:
            return {
                "tag": None,
                "commits_since_tag": None,
                "on_tagged_commit": False,
                "classifier": classifier_name,
                "error": str(e)
            }

    def check_working_directory_clean(self) -> Tuple[bool, Optional[str]]:
        """Check if working directory is clean."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout.strip():
                return False, "Working directory has uncommitted changes"
            return True, None

        except subprocess.CalledProcessError as e:
            return False, f"Failed to check git status: {e}"

    def tag_version(
        self,
        bump_type: Literal["major", "minor", "patch"],
        classifier_name: str,
        message: Optional[str] = None
    ) -> str:
        """Create a new version tag for a specific classifier.

        Args:
            bump_type: Type of version bump
            classifier_name: Name of the classifier to tag
            message: Optional tag message
        """
        # Check working directory is clean
        is_clean, error_msg = self.check_working_directory_clean()
        if not is_clean:
            raise VersionControlError(f"Cannot tag version: {error_msg}")

        # Get current version for this classifier
        current_version = self.get_current_version(classifier_name)

        if current_version:
            # Parse and bump version
            try:
                version_info = semver.VersionInfo.parse(current_version)
                if bump_type == "major":
                    new_version = str(version_info.bump_major())
                elif bump_type == "minor":
                    new_version = str(version_info.bump_minor())
                else:  # patch
                    new_version = str(version_info.bump_patch())
            except ValueError:
                # Current tag doesn't follow semver, start fresh
                new_version = "1.0.0" if bump_type == "major" else "0.1.0" if bump_type == "minor" else "0.0.1"
        else:
            # No previous tags for this classifier
            new_version = "1.0.0" if bump_type == "major" else "0.1.0" if bump_type == "minor" else "0.0.1"

        # Create hierarchical tag
        tag_name = f"{classifier_name}-v{new_version}"
        tag_message = message or f"Release {classifier_name} {new_version}"

        try:
            # Create annotated tag
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", tag_message],
                cwd=self.project_path,
                check=True
            )

            print(f"✅ Created tag {tag_name}")
            print(f"📝 {classifier_name} version bumped from {current_version or 'none'} to {new_version}")

            return new_version

        except subprocess.CalledProcessError as e:
            raise VersionControlError(f"Failed to create tag: {e}")

    def check_registry_tag_exists(
        self,
        registry: str,
        repository: str,
        tag: str
    ) -> bool:
        """Check if a tag already exists in the Docker registry."""
        full_image = f"{registry}/{repository}:{tag}"

        try:
            # Try to pull just the manifest (lightweight check)
            result = subprocess.run(
                ["docker", "manifest", "inspect", full_image],
                capture_output=True,
                check=False,
                stderr=subprocess.DEVNULL
            )

            return result.returncode == 0

        except Exception:
            # If docker manifest doesn't work, try alternative approach
            try:
                result = subprocess.run(
                    ["docker", "pull", "--disable-content-trust", full_image],
                    capture_output=True,
                    check=False
                )
                return "Downloaded newer image" in result.stdout.decode() or "Image is up to date" in result.stdout.decode()
            except Exception:
                # Assume it doesn't exist if we can't check
                return False

    def get_all_classifiers_tag_status(self, config_path: str) -> Dict[str, Dict[str, Any]]:
        """Get tag status for all classifiers in a configuration.

        Returns:
            Dict mapping classifier names to their tag status
        """
        from .multi_classifier import detect_multi_classifier_config, list_available_classifiers
        from .config import AppConfig
        import yaml

        classifiers_status = {}

        # Determine if it's multi-classifier or single
        if detect_multi_classifier_config(config_path):
            # Multi-classifier config
            classifier_names = list_available_classifiers(config_path)
        else:
            # Single classifier config
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            try:
                config = AppConfig.model_validate(config_data)
                classifier_names = [config.classifier.get('name', 'default')]
            except Exception:
                # Fall back to trying to get classifier name directly
                if 'classifier' in config_data and 'name' in config_data['classifier']:
                    classifier_names = [config_data['classifier']['name']]
                else:
                    classifier_names = ['default']

        # Get status for each classifier
        for classifier_name in classifier_names:
            tag_info = self.get_latest_tag_info(classifier_name)
            current_version = self.get_current_version(classifier_name)

            # Determine readiness
            if tag_info["on_tagged_commit"]:
                status = "Ready"
                recommendation = None
            else:
                if tag_info["tag"]:
                    status = f"{tag_info['commits_since_tag']} commits behind"
                    recommendation = f"mlserver tag --classifier {classifier_name} <major|minor|patch>"
                else:
                    status = "No tags"
                    recommendation = f"mlserver tag --classifier {classifier_name} <major|minor|patch>"

            classifiers_status[classifier_name] = {
                "current_version": current_version,
                "latest_tag": tag_info["tag"],
                "commits_since_tag": tag_info["commits_since_tag"],
                "on_tagged_commit": tag_info["on_tagged_commit"],
                "status": status,
                "recommendation": recommendation
            }

        return classifiers_status

    def validate_push_readiness(self, classifier_name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Validate if the repository is ready for pushing to registry."""
        validation_result = {
            "ready": True,
            "errors": [],
            "warnings": [],
            "tag_info": {}
        }

        # Check if working directory is clean
        is_clean, error_msg = self.check_working_directory_clean()
        if not is_clean and not force:
            validation_result["ready"] = False
            validation_result["errors"].append(error_msg)
        elif not is_clean:
            validation_result["warnings"].append(error_msg)

        # Get tag information
        tag_info = self.get_latest_tag_info(classifier_name)
        validation_result["tag_info"] = tag_info

        # Check if on tagged commit
        if not tag_info["on_tagged_commit"]:
            if tag_info["tag"]:
                commits_since = tag_info.get("commits_since_tag", "unknown")
                if classifier_name:
                    error = f"Classifier '{classifier_name}' not on a tagged commit. Latest tag '{tag_info['tag']}' is {commits_since} commits behind."
                else:
                    error = f"Not on a tagged commit. Latest tag '{tag_info['tag']}' is {commits_since} commits behind."
            else:
                if classifier_name:
                    error = f"No version tags found for classifier '{classifier_name}'."
                else:
                    error = "No version tags found in repository."

            validation_result["ready"] = False
            validation_result["errors"].append(error)

            if classifier_name:
                validation_result["errors"].append(f"Please tag your release with 'mlserver tag --classifier {classifier_name} <major|minor|patch>' before pushing.")
            else:
                validation_result["errors"].append("Please tag your release with 'mlserver tag <major|minor|patch>' before pushing.")

        return validation_result


def get_version_for_push(
    project_path: str = ".",
    classifier_name: Optional[str] = None,
    version_source: Literal["git-tag", "config", "auto"] = "auto"
) -> Tuple[str, str]:
    """
    Get the version to use for container push.

    Args:
        project_path: Path to project
        classifier_name: Optional classifier name for hierarchical tags
        version_source: Source of version ("git-tag", "config", "auto")

    Returns:
        Tuple of (version, source_description)
    """
    git_mgr = GitVersionManager(project_path)

    if version_source == "git-tag":
        version = git_mgr.get_current_version(classifier_name)
        if not version:
            if classifier_name:
                raise VersionControlError(f"No git tags found for classifier '{classifier_name}'. Please tag your release first.")
            else:
                raise VersionControlError("No git tags found. Please tag your release first.")
        return version, f"git-tag ({classifier_name})" if classifier_name else "git-tag"

    elif version_source == "config":
        # Load from config file
        from .version import load_classifier_metadata
        metadata = load_classifier_metadata(project_path)
        return metadata.classifier.version, "config"

    else:  # auto
        # Prefer git tag if on tagged commit
        tag_info = git_mgr.get_latest_tag_info(classifier_name)
        if tag_info["on_tagged_commit"] and tag_info["tag"]:
            tag = tag_info["tag"]
            # Extract version from hierarchical tag if needed
            if classifier_name and '-v' in tag:
                version = tag.split('-v', 1)[1]
            else:
                version = tag[1:] if tag.startswith('v') else tag
            return version, f"git-tag ({tag})"

        # Fall back to config
        from .version import load_classifier_metadata
        metadata = load_classifier_metadata(project_path)
        return metadata.classifier.version, f"config (not on tagged commit for {classifier_name})" if classifier_name else "config (not on tagged commit)"


def safe_push_container(
    project_path: str,
    registry: str,
    classifier_name: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    force: bool = False,
    version_source: Literal["git-tag", "config", "auto"] = "auto"
) -> Dict[str, Any]:
    """
    Safely push container to registry with version validation.

    Args:
        project_path: Path to project
        registry: Registry URL
        classifier_name: Optional classifier name for hierarchical tags
        tag_prefix: Optional tag prefix
        force: Force push even with warnings
        version_source: Source of version

    Returns:
        Push result dictionary
    """
    git_mgr = GitVersionManager(project_path)

    # Validate push readiness
    validation = git_mgr.validate_push_readiness(classifier_name, force)

    if not validation["ready"] and not force:
        return {
            "success": False,
            "error": "Push validation failed",
            "validation_errors": validation["errors"]
        }

    # Get version for push
    try:
        version, version_source_desc = get_version_for_push(project_path, classifier_name, version_source)
    except VersionControlError as e:
        return {
            "success": False,
            "error": str(e)
        }

    # Load metadata for repository name
    from .version import load_classifier_metadata, get_git_info
    metadata = load_classifier_metadata(project_path)
    git_info = get_git_info(project_path)

    # Build repository path
    repository = metadata.classifier.repository if hasattr(metadata.classifier, 'repository') else 'mlserver'
    if tag_prefix:
        repository = f"{tag_prefix}/{repository}"

    # Check if tag exists in registry
    tag_exists = git_mgr.check_registry_tag_exists(registry, repository, version)

    if tag_exists and not force:
        return {
            "success": False,
            "error": f"Tag '{version}' already exists in registry",
            "details": f"Image {registry}/{repository}:{version} already exists. Use --force to overwrite."
        }

    # Proceed with push using existing push_container function
    from .container import push_container

    result = push_container(
        project_path=project_path,
        registry=registry,
        tag_prefix=tag_prefix
    )

    # Add version info to result
    result["version_used"] = version
    result["version_source"] = version_source_desc
    result["validation_warnings"] = validation.get("warnings", [])

    return result