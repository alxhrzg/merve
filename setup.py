#!/usr/bin/env python3
"""
Setup script for mlserver-fastapi-wrapper.
This handles build-time operations like embedding git information.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist
from setuptools.command.bdist_wheel import bdist_wheel


def capture_and_embed_git_info():
    """Run build_utils to capture git info during build."""
    try:
        # Add current directory to path to import build_utils
        sys.path.insert(0, str(Path(__file__).parent))
        import build_utils

        print("Capturing git information for build...")
        git_info = build_utils.write_version_info()

        if git_info and git_info.get('commit'):
            print(f"✓ Embedded git info - commit: {git_info['commit']}, "
                  f"branch: {git_info.get('branch', 'unknown')}")
        else:
            print("⚠ No git information available (not a git repository)")

    except Exception as e:
        print(f"⚠ Could not embed git information: {e}")
        # Don't fail the build if git info capture fails
        pass


class CustomBuildPy(build_py):
    """Custom build command that embeds git info before building."""
    def run(self):
        capture_and_embed_git_info()
        super().run()


class CustomSdist(sdist):
    """Custom sdist command that embeds git info before creating source distribution."""
    def run(self):
        capture_and_embed_git_info()
        super().run()


class CustomBdistWheel(bdist_wheel):
    """Custom bdist_wheel command that embeds git info before creating wheel."""
    def run(self):
        capture_and_embed_git_info()
        super().run()


if __name__ == "__main__":
    # Use setup with custom commands
    setup(
        cmdclass={
            'build_py': CustomBuildPy,
            'sdist': CustomSdist,
            'bdist_wheel': CustomBdistWheel,
        }
    )