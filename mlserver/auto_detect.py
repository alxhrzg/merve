"""
Auto-detection utilities for metadata and configuration.

This module provides automatic detection of:
- Git repository information (name, commit, tag, branch)
- Deployment timestamps
- MLServer package version
- Project name from git or directory
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import importlib.metadata


def get_git_project_name(project_path: str = ".") -> Optional[str]:
    """
    Auto-detect project name from git repository.

    Returns:
        Repository name from git remote origin, or None if not a git repo
    """
    try:
        # Try to get remote URL
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=project_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        if remote_url:
            # Extract repository name from URL
            # Handle both HTTPS and SSH URLs
            # https://github.com/user/repo.git -> repo
            # git@github.com:user/repo.git -> repo
            match = re.search(r'[/:]([^/]+?)(?:\.git)?$', remote_url)
            if match:
                return match.group(1).lower()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return None


def get_project_name(project_path: str = ".") -> str:
    """
    Get project name from git or fallback to directory name.

    Returns:
        Project name (guaranteed to return a value)
    """
    # Try git first
    git_name = get_git_project_name(project_path)
    if git_name:
        return git_name

    # Fallback to directory name
    return os.path.basename(os.path.abspath(project_path)).lower()


def get_git_info(project_path: str = ".") -> Dict[str, Any]:
    """
    Get comprehensive git information.

    Returns:
        Dict with repository, commit, tag, branch, dirty status
    """
    info = {
        "repository": get_git_project_name(project_path),
        "commit": None,
        "tag": None,
        "branch": None,
        "dirty": False
    }

    # Check environment variables first (for containerized deployments)
    env_commit = os.environ.get('MLSERVER_GIT_COMMIT')
    env_tag = os.environ.get('MLSERVER_GIT_TAG')
    env_branch = os.environ.get('MLSERVER_GIT_BRANCH')

    if env_commit or env_tag or env_branch:
        # Running in container with embedded metadata
        if env_commit:
            info["commit"] = env_commit
        if env_tag:
            info["tag"] = env_tag
        if env_branch:
            info["branch"] = env_branch
        # In container, we can't determine if dirty
        info["dirty"] = False
        return info

    try:
        original_cwd = os.getcwd()
        os.chdir(project_path)

        # Get current commit (short hash)
        info["commit"] = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # Get current branch
        info["branch"] = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # Check if working directory is dirty
        status = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        info["dirty"] = len(status) > 0

        # Get tag at current commit (if any)
        try:
            info["tag"] = subprocess.check_output(
                ['git', 'describe', '--tags', '--exact-match', 'HEAD'],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except subprocess.CalledProcessError:
            # No tag at current commit
            pass

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repository or git not installed
        pass
    finally:
        if 'original_cwd' in locals():
            os.chdir(original_cwd)

    return info


def get_deployed_timestamp() -> str:
    """
    Generate ISO format deployment timestamp.

    Returns:
        Current time in ISO 8601 format with timezone
    """
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def get_mlserver_package_version() -> str:
    """
    Get installed mlserver package version.

    Returns:
        Package version or 'unknown' if not found
    """
    # Try different possible package names
    possible_names = [
        'mlserver-fastapi-wrapper',
        'mlserver_fastapi_wrapper',
        'mlserver',
        'ml-server',
        'ml_server',
    ]

    # Also check for any package containing 'mlserver' in the name
    try:
        # Get all installed packages
        import pkg_resources
        for dist in pkg_resources.working_set:
            name_lower = dist.project_name.lower()
            if 'mlserver' in name_lower or 'ml-server' in name_lower or 'ml_server' in name_lower:
                # Found a package with mlserver in the name
                try:
                    return importlib.metadata.version(dist.project_name)
                except:
                    pass
    except:
        pass

    # Try the explicit list of names
    for name in possible_names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue

    try:
        # Fallback: try to read from pyproject.toml if in development
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"

        if pyproject_path.exists():
            import tomllib
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
                return data.get('tool', {}).get('poetry', {}).get('version', 'dev')
    except Exception:
        pass

    return "unknown"


def get_mlserver_git_info() -> Dict[str, Any]:
    """
    Get git information for the MLServer package itself.

    Returns:
        Dict with mlserver's git commit, tag, and comprehensive version info
    """
    info = {
        "package_version": get_mlserver_package_version(),
        "api_commit": None,
        "api_tag": None,
        "api_branch": None,
        "api_dirty": False
    }

    # First check if we have embedded version info (from package build)
    try:
        from mlserver import _version_info
        if hasattr(_version_info, 'GIT_COMMIT') and _version_info.GIT_COMMIT:
            info["api_commit"] = _version_info.GIT_COMMIT
        if hasattr(_version_info, 'GIT_TAG') and _version_info.GIT_TAG:
            info["api_tag"] = _version_info.GIT_TAG
        if hasattr(_version_info, 'GIT_BRANCH') and _version_info.GIT_BRANCH:
            info["api_branch"] = _version_info.GIT_BRANCH
        if hasattr(_version_info, 'GIT_DIRTY'):
            info["api_dirty"] = _version_info.GIT_DIRTY

        # If we found embedded info, use it
        if info["api_commit"]:
            return info
    except ImportError:
        pass

    # Check environment variables (for containerized deployments)
    env_api_commit = os.environ.get('MLSERVER_API_COMMIT')
    env_api_tag = os.environ.get('MLSERVER_API_TAG')
    env_api_branch = os.environ.get('MLSERVER_API_BRANCH')

    if env_api_commit or env_api_tag or env_api_branch:
        # Running in container with embedded MLServer metadata
        if env_api_commit:
            info["api_commit"] = env_api_commit
        if env_api_tag:
            info["api_tag"] = env_api_tag
        if env_api_branch:
            info["api_branch"] = env_api_branch
        info["api_dirty"] = False
        return info

    # Get the mlserver package directory
    mlserver_dir = Path(__file__).parent.parent

    # Get git info if mlserver is a git repo (development mode)
    if (mlserver_dir / ".git").exists():
        git_data = get_git_info(str(mlserver_dir))
        info["api_commit"] = git_data["commit"]
        info["api_tag"] = git_data["tag"]
        info["api_branch"] = git_data["branch"]
        info["api_dirty"] = git_data["dirty"]

    return info


def generate_simplified_metadata(config: Dict[str, Any], project_path: str = ".") -> Dict[str, Any]:
    """
    Generate simplified metadata structure from config and auto-detection.

    Args:
        config: The loaded configuration dictionary
        project_path: Path to the project

    Returns:
        Simplified metadata dict for responses
    """
    git_info = get_git_info(project_path)

    # Extract classifier info
    classifier_config = config.get('classifier', {})

    metadata = {
        "project": git_info.get("repository") or get_project_name(project_path),
        "classifier": classifier_config.get("name", "unknown"),
        "description": classifier_config.get("description", ""),
        "git_commit": git_info.get("commit"),
        "git_tag": git_info.get("tag"),
        "git_branch": git_info.get("branch"),
        "git_dirty": git_info.get("dirty", False),
        "deployed_at": get_deployed_timestamp(),
        "mlserver_version": get_mlserver_package_version()
    }

    # Remove None values for cleaner output
    return {k: v for k, v in metadata.items() if v is not None}


def get_simplified_info_response(config: Dict[str, Any], predictor_class_name: str, project_path: str = ".") -> Dict[str, Any]:
    """
    Generate simplified /info endpoint response.

    Args:
        config: The loaded configuration dictionary
        predictor_class_name: Name of the predictor class
        project_path: Path to the project

    Returns:
        Simplified info response dict
    """
    git_info = get_git_info(project_path)
    mlserver_info = get_mlserver_git_info()

    classifier_config = config.get('classifier', {})

    return {
        "project": git_info.get("repository") or get_project_name(project_path),
        "classifier": classifier_config.get("name", "unknown"),
        "description": classifier_config.get("description", ""),
        "predictor_class": predictor_class_name,
        "deployed_at": get_deployed_timestamp(),
        "classifier_repository": {
            "repository": git_info.get("repository"),
            "commit": git_info.get("commit"),
            "tag": git_info.get("tag"),
            "branch": git_info.get("branch"),
            "dirty": git_info.get("dirty")
        },
        "api_service": mlserver_info,
        "endpoints": {
            "predict": "/predict",
            "predict_proba": "/predict_proba",
            "info": "/info",
            "health": "/healthz",
            "metrics": "/metrics"
        }
    }