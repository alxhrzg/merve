# Version information - now dynamically sourced from setuptools-scm
# This file maintains backward compatibility with code that imports from _version_info
#
# The actual version is now automatically derived from git tags via setuptools-scm
# See pyproject.toml [tool.setuptools_scm] section for configuration

import subprocess
from pathlib import Path
from datetime import datetime

# Get version from setuptools-scm's generated file
try:
    from mlserver._version import __version__
    VERSION = __version__
except ImportError:
    # Fallback: try to get version directly from setuptools-scm
    try:
        from setuptools_scm import get_version
        VERSION = get_version(root='..', relative_to=__file__)
    except Exception:
        VERSION = "0.0.0+unknown"

# Get git information dynamically
def _get_git_info():
    """Get current git information."""
    info = {
        'commit': '',
        'tag': '',
        'branch': '',
        'dirty': False
    }

    try:
        # Get git root directory
        repo_root = Path(__file__).parent.parent

        # Get commit hash
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            info['commit'] = result.stdout.strip()

        # Get current tag
        result = subprocess.run(
            ['git', 'describe', '--tags', '--exact-match'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            info['tag'] = result.stdout.strip()

        # Get branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            info['branch'] = result.stdout.strip()

        # Check if dirty
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            info['dirty'] = bool(result.stdout.strip())

    except Exception:
        pass

    return info

# Get git info at import time
_git_info = _get_git_info()
GIT_COMMIT = _git_info['commit']
GIT_TAG = _git_info['tag']
GIT_BRANCH = _git_info['branch']
GIT_DIRTY = _git_info['dirty']
BUILD_TIME = datetime.now().isoformat() + "Z"

# Expose for backward compatibility
__all__ = ['VERSION', 'GIT_COMMIT', 'GIT_TAG', 'GIT_BRANCH', 'GIT_DIRTY', 'BUILD_TIME']
