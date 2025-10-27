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


def get_mlserver_commit_hash() -> Optional[str]:
    """Get the current commit hash of the mlserver tool.

    This function determines the git commit hash of the mlserver-fastapi-wrapper
    package that is currently installed. It handles various installation methods:
    - Editable installs (pip install -e .)
    - Git installs (pip install git+...)
    - Development installs

    Returns:
        7-character short commit hash, or None if not from git
    """
    try:
        # Get the mlserver package location
        import mlserver
        mlserver_file = Path(mlserver.__file__)

        # Try different paths to find the git repository
        # For editable installs: /path/to/mlserver/mlserver/__init__.py -> /path/to/mlserver
        # For package installs: /path/to/site-packages/mlserver/__init__.py -> need to go up more
        search_paths = [
            mlserver_file.parent.parent,  # Standard editable: mlserver/mlserver/__init__.py -> mlserver/
            mlserver_file.parent.parent.parent,  # Some installs might have extra nesting
        ]

        for base_path in search_paths:
            git_dir = base_path / '.git'
            if git_dir.exists() and git_dir.is_dir():
                try:
                    result = subprocess.run(
                        ["git", "rev-parse", "--short=7", "HEAD"],
                        cwd=base_path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    commit_hash = result.stdout.strip()
                    if commit_hash:
                        return commit_hash
                except subprocess.CalledProcessError:
                    continue

        return None

    except Exception:
        return None


def parse_hierarchical_tag(tag: str) -> Dict[str, Optional[str]]:
    """Parse hierarchical tag into its components.

    Parses tags in the format: <classifier-name>-v<X.X.X>-mlserver-<commit-hash>

    Args:
        tag: Full tag string to parse

    Returns:
        Dictionary with keys:
        - classifier: Classifier name (e.g., "sentiment", "rfq-likelihood")
        - version: Semantic version (e.g., "1.0.0")
        - mlserver_commit: MLServer commit hash (e.g., "b5dff2a")
        - format: "valid" if tag matches expected format, "invalid" otherwise

    Examples:
        >>> parse_hierarchical_tag("sentiment-v1.0.0-mlserver-b5dff2a")
        {'classifier': 'sentiment', 'version': '1.0.0', 'mlserver_commit': 'b5dff2a', 'format': 'valid'}

        >>> parse_hierarchical_tag("invalid-tag")
        {'classifier': None, 'version': None, 'mlserver_commit': None, 'format': 'invalid'}
    """
    # Regex for new format: <name>-v<X.X.X>-mlserver-<hash>
    # Classifier names can contain letters, numbers, underscores, hyphens
    # Commit hashes are 7+ hex characters
    pattern = r'^([a-z0-9_-]+)-v(\d+\.\d+\.\d+)-mlserver-([a-f0-9]{3,})$'
    match = re.match(pattern, tag)

    if match:
        return {
            "classifier": match.group(1),
            "version": match.group(2),
            "mlserver_commit": match.group(3),
            "format": "valid"
        }

    # Tag doesn't match expected format
    return {
        "classifier": None,
        "version": None,
        "mlserver_commit": None,
        "format": "invalid"
    }


def extract_classifier_name(name_or_tag: str) -> Optional[str]:
    """Extract classifier name from either a simple name or full hierarchical tag.

    This helper function allows CLI commands to accept both formats:
    - Simple name: "sentiment"
    - Full tag: "sentiment-v1.0.0-mlserver-b5dff2a"

    Args:
        name_or_tag: Either a classifier name or full hierarchical tag

    Returns:
        Classifier name, or None if tag format is invalid

    Examples:
        >>> extract_classifier_name("sentiment")
        'sentiment'

        >>> extract_classifier_name("sentiment-v1.0.0-mlserver-b5dff2a")
        'sentiment'

        >>> extract_classifier_name("rfq_likelihood_model")
        'rfq_likelihood_model'
    """
    # First, try to parse as a full tag
    parsed = parse_hierarchical_tag(name_or_tag)
    if parsed["format"] == "valid":
        return parsed["classifier"]

    # Not a full tag, assume it's just a classifier name
    # Validate it's a reasonable name (alphanumeric, underscore, hyphen)
    if re.match(r'^[a-z0-9_-]+$', name_or_tag):
        return name_or_tag

    # Invalid format
    return None


def get_tag_commits(tag: str, project_path: str = ".") -> Dict[str, Optional[str]]:
    """Get git commit hashes from a hierarchical tag.

    Given a hierarchical tag, returns:
    - The classifier repo commit that the tag points to
    - The mlserver commit encoded in the tag

    Args:
        tag: Full hierarchical tag (e.g., "sentiment-v1.0.0-mlserver-b5dff2a")
        project_path: Path to classifier project

    Returns:
        Dictionary with keys:
        - classifier_commit: Git commit hash in classifier repo
        - mlserver_commit: MLServer commit from tag
        - tag_valid: True if tag exists and can be parsed

    Examples:
        >>> get_tag_commits("sentiment-v1.0.0-mlserver-b5dff2a", "/path/to/project")
        {'classifier_commit': 'a1b2c3d', 'mlserver_commit': 'b5dff2a', 'tag_valid': True}
    """
    result = {
        "classifier_commit": None,
        "mlserver_commit": None,
        "tag_valid": False
    }

    # Parse the tag to extract mlserver commit
    parsed = parse_hierarchical_tag(tag)
    if parsed["format"] != "valid":
        return result

    result["mlserver_commit"] = parsed["mlserver_commit"]

    # Get the git commit that this tag points to
    try:
        cmd_result = subprocess.run(
            ["git", "rev-list", "-n", "1", tag],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = cmd_result.stdout.strip()
        if commit_hash:
            # Get short hash (7 chars)
            short_result = subprocess.run(
                ["git", "rev-parse", "--short=7", commit_hash],
                cwd=project_path,
                capture_output=True,
                text=True,
                check=True
            )
            result["classifier_commit"] = short_result.stdout.strip()
            result["tag_valid"] = True

    except subprocess.CalledProcessError:
        # Tag doesn't exist in repo
        pass

    return result


class GitVersionManager:
    """Manage git-based versioning for ML models."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)

    def get_current_version(self, classifier_name: Optional[str] = None) -> Optional[str]:
        """Get the current version from git tags.

        Parses tags in the format: classifier-v1.0.0-mlserver-hash
        Returns just the version part: 1.0.0

        Args:
            classifier_name: If provided, looks for classifier-specific tags (e.g., 'sentiment-v1.0.0-mlserver-b5dff2a')
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
                        # Parse new format: classifier-v1.0.0-mlserver-hash
                        # Extract version using regex
                        match = re.search(r'-v(\d+\.\d+\.\d+)', latest_tag)
                        if match:
                            return match.group(1)
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
                    # Try to extract version using regex
                    match = re.search(r'-v(\d+\.\d+\.\d+)', tag)
                    if match:
                        return match.group(1)
                    # Fallback: Remove 'v' prefix if present
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
        message: Optional[str] = None,
        allow_missing_mlserver: bool = False
    ) -> Dict[str, str]:
        """Create a new version tag for a specific classifier with mlserver commit hash.

        Args:
            bump_type: Type of version bump
            classifier_name: Name of the classifier to tag
            message: Optional tag message
            allow_missing_mlserver: If True, allow tagging even if mlserver commit cannot be determined (dev/testing only)

        Returns:
            Dict with keys: 'version', 'tag_name', 'mlserver_commit', 'previous_version'

        Raises:
            VersionControlError: If working directory is not clean or mlserver commit cannot be determined
        """
        # Check working directory is clean
        is_clean, error_msg = self.check_working_directory_clean()
        if not is_clean:
            raise VersionControlError(f"Cannot tag version: {error_msg}")

        # Get mlserver commit hash
        mlserver_commit = get_mlserver_commit_hash()
        if not mlserver_commit:
            if not allow_missing_mlserver:
                raise VersionControlError(
                    "Could not determine mlserver commit hash. "
                    "Ensure mlserver-fastapi-wrapper is installed from a git repository. "
                    "For development/testing, use --allow-missing-mlserver flag."
                )
            else:
                # Use placeholder for development
                mlserver_commit = "dev"
                print("⚠️  Warning: Using 'dev' as mlserver commit (--allow-missing-mlserver enabled)")

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

        # Create hierarchical tag with mlserver commit
        tag_name = f"{classifier_name}-v{new_version}-mlserver-{mlserver_commit}"
        tag_message = message or f"Release {classifier_name} {new_version} (mlserver {mlserver_commit})"

        try:
            # Create annotated tag
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", tag_message],
                cwd=self.project_path,
                check=True
            )

            return {
                'version': new_version,
                'tag_name': tag_name,
                'mlserver_commit': mlserver_commit,
                'previous_version': current_version
            }

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
            # Extract version from hierarchical tag using parser (Phase 2)
            if classifier_name and '-mlserver-' in tag:
                # Parse hierarchical tag format
                parsed = parse_hierarchical_tag(tag)
                if parsed["format"] == "valid":
                    version = parsed["version"]
                else:
                    # Fallback for non-hierarchical tags
                    version = tag.split('-v', 1)[1] if '-v' in tag else tag
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