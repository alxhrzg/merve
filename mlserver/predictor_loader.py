
from importlib import import_module
from typing import Any, Optional
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _validate_model_files(init_kwargs: dict) -> None:
    """Validate model file sizes before loading to prevent memory issues."""
    file_size_limit_mb = 2000  # 2GB limit

    # Common model file parameters to check
    file_params = ['model_path', 'preprocessor_path', 'weights_path', 'checkpoint_path']

    for param in file_params:
        if param in init_kwargs:
            file_path = init_kwargs[param]
            if isinstance(file_path, str) and os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                size_mb = size_bytes / (1024 * 1024)

                if size_mb > file_size_limit_mb:
                    raise ValueError(
                        f"Model file {file_path} is too large: {size_mb:.1f}MB "
                        f"(limit: {file_size_limit_mb}MB). Consider using a smaller model "
                        f"or increase system resources."
                    )
                elif size_mb > 100:  # Warn for files > 100MB
                    logger.warning(f"Loading large model file: {file_path} ({size_mb:.1f}MB)")


def resolve_module_path(module_spec: str, config_dir: Optional[str] = None) -> str:
    """Resolve module path intelligently.

    Handles three cases:
    1. Full module path (e.g., 'examples.predictor_catboost') - use as-is
    2. Relative path with .py (e.g., 'predictor_catboost.py') - resolve relative to config
    3. Simple name (e.g., 'predictor_catboost') - try to resolve relative to config

    Args:
        module_spec: Module specification (can be full path, filename, or simple name)
        config_dir: Directory containing the configuration file

    Returns:
        Full module path that can be imported
    """
    # Case 1: Already a full module path (contains dots but not .py extension)
    if '.' in module_spec and not module_spec.endswith('.py'):
        return module_spec

    # Case 2 & 3: Simple name or filename - try to resolve relative to config
    if config_dir:
        # Remove .py extension if present
        module_name = module_spec.replace('.py', '')

        # Check if the file exists in the config directory
        module_file = Path(config_dir) / f"{module_name}.py"
        if module_file.exists():
            # Add config directory to Python path if not already there
            # Add at the beginning to prioritize local modules
            config_dir_abs = str(Path(config_dir).resolve())
            if config_dir_abs not in sys.path:
                sys.path.insert(0, config_dir_abs)
                logger.info(f"Added '{config_dir_abs}' to Python path")

            # Try to import it directly by name after adding to path
            try:
                # Force reimport in case module was previously loaded
                if module_name in sys.modules:
                    del sys.modules[module_name]
                import_module(module_name)
                logger.info(f"Resolved module '{module_spec}' to '{module_name}' (local import from {config_dir})")
                return module_name
            except ImportError as e:
                logger.debug(f"Direct import of '{module_name}' failed: {e}")
                # If direct import fails, try to construct the full path
                # This handles cases where the config is in a package subdirectory
                try:
                    # Try to determine package structure by looking for __init__.py files
                    current_path = Path(config_dir).resolve()
                    module_parts = []

                    # Walk up the directory tree to find the package root
                    while current_path.parent != current_path:
                        if (current_path / '__init__.py').exists():
                            module_parts.insert(0, current_path.name)
                            current_path = current_path.parent
                        else:
                            break

                    if module_parts:
                        # We're in a package structure
                        full_module = '.'.join(module_parts) + '.' + module_name
                        try:
                            import_module(full_module)
                            logger.info(f"Resolved module '{module_spec}' to '{full_module}' (package import)")
                            return full_module
                        except ImportError:
                            pass
                except Exception as e:
                    logger.debug(f"Failed to construct package path: {e}")

    # Fallback: return as-is and let the import fail with a clear error
    logger.warning(f"Could not resolve module '{module_spec}', using as-is")
    return module_spec


def load_predictor(module: str, class_name: str, init_kwargs: dict, config_dir: Optional[str] = None) -> Any:
    """Load a predictor class with intelligent module resolution.

    Args:
        module: Module specification (can be full path, filename, or simple name)
        class_name: Name of the predictor class
        init_kwargs: Keyword arguments for the predictor constructor
        config_dir: Directory containing the configuration file (for relative imports)
    """
    # Validate model file sizes before loading
    _validate_model_files(init_kwargs or {})

    # Resolve the module path
    resolved_module = resolve_module_path(module, config_dir)

    # Import the module
    try:
        mod = import_module(resolved_module)
    except ImportError as e:
        # Provide helpful error message
        error_msg = f"Failed to import module '{resolved_module}' (original: '{module}')"
        if config_dir:
            error_msg += f" from config directory '{config_dir}'"

        suggestions = []
        if '.' not in module:
            suggestions.append(f"Try using just the filename: '{module}.py'")
            suggestions.append(f"Or specify the full module path")

        if suggestions:
            error_msg += "\n" + "\n".join(suggestions)

        raise ImportError(error_msg) from e

    # Get the class from the module
    try:
        cls = getattr(mod, class_name)
    except AttributeError as e:
        raise ImportError(f"Class {class_name!r} not found in module {resolved_module!r}") from e

    # Instantiate the predictor
    return cls(**(init_kwargs or {}))
