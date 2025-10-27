#!/usr/bin/env python3
"""
Build utilities for embedding version information into the package.
This is called during package build (setup.py, poetry build, etc.)
"""

import subprocess
import os
from pathlib import Path
from datetime import datetime, timezone


def capture_git_info():
    """Capture git information from the repository."""
    info = {
        "commit": None,
        "tag": None,
        "branch": None,
        "dirty": False
    }

    try:
        # Get commit hash
        info["commit"] = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()

        # Get current branch
        info["branch"] = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()

        # Check if dirty
        status = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        info["dirty"] = len(status) > 0

        # Get tag at current commit (if any)
        try:
            info["tag"] = subprocess.check_output(
                ['git', 'describe', '--tags', '--exact-match', 'HEAD'],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
        except subprocess.CalledProcessError:
            pass

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo or git not available
        pass

    return info


def write_version_info():
    """Write version information to _version_info.py file."""
    # Get package version from pyproject.toml or setup.py
    version = "0.2.0"  # This should be read from pyproject.toml

    try:
        # Python 3.11+ has tomllib in stdlib
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # fallback for older Python

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
            # Try different locations for version
            version = data.get("project", {}).get("version", version)
            if not version:
                version = data.get("tool", {}).get("poetry", {}).get("version", "0.2.0")
    except:
        pass

    # Capture git info
    git_info = capture_git_info()

    # Generate the version info file
    now_utc = datetime.now(timezone.utc).isoformat()
    version_file_content = f'''# Auto-generated version information
# This file is created during package build to embed git information
# Generated at: {now_utc}Z
# DO NOT EDIT MANUALLY - it will be overwritten during build

VERSION = "{version}"
GIT_COMMIT = "{git_info['commit'] or ''}"
GIT_TAG = "{git_info['tag'] or ''}"
GIT_BRANCH = "{git_info['branch'] or ''}"
GIT_DIRTY = {git_info['dirty']}
BUILD_TIME = "{now_utc}Z"

# This file is populated during package build
# These values are embedded at build time and available at runtime
'''

    # Write to file
    version_file = Path(__file__).parent / "mlserver" / "_version_info.py"
    version_file.write_text(version_file_content)

    print(f"✓ Embedded version info: v{version}, commit: {git_info['commit']}")
    return git_info


if __name__ == "__main__":
    write_version_info()