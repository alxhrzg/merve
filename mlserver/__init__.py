
# Expose version from setuptools-scm
try:
    from ._version import __version__
except ImportError:
    # Fallback for development without installation
    try:
        from setuptools_scm import get_version
        __version__ = get_version(root='..', relative_to=__file__)
    except Exception:
        __version__ = "0.0.0+unknown"

__all__ = [
    "create_app",
    "__version__",
]
from .server import create_app
