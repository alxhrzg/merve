"""
Docker containerization utilities for ML classifier projects.
"""
import os
import subprocess
import shutil
import ast
import importlib.util
from typing import Optional, List, Dict, Any, Set, Tuple
from pathlib import Path
from datetime import datetime

from .config import AppConfig
from .version import (
    ClassifierMetadata,
    load_classifier_metadata,
    get_git_info,
    generate_container_tags,
    get_version_info,
    get_repository_name
)
from .version_control import (
    get_mlserver_commit_hash,
    parse_hierarchical_tag,
    GitVersionManager
)
from .settings import get_settings


class ContainerError(Exception):
    """Container build/push related error."""
    pass


def generate_container_labels(
    project_path: str,
    classifier_name: Optional[str] = None,
    config: Optional['AppConfig'] = None
) -> Dict[str, str]:
    """Generate Docker labels for full container traceability.

    Creates comprehensive labels including:
    - Standard OCI image labels
    - MLServer tool version and commit
    - Classifier version and git information
    - Build timestamp

    Args:
        project_path: Path to classifier project
        classifier_name: Name of classifier being built
        config: AppConfig instance (optional)

    Returns:
        Dictionary of label keys and values for Dockerfile LABEL directives

    Example:
        >>> labels = generate_container_labels("/path/to/project", "sentiment")
        >>> labels["com.mlserver.commit"]
        'b5dff2a'
        >>> labels["com.classifier.git_tag"]
        'sentiment-v1.0.0-mlserver-b5dff2a'
    """
    labels = {}

    # Get current timestamp
    build_time = datetime.utcnow().isoformat() + "Z"

    # ========================================================================
    # MLServer Tool Information
    # ========================================================================

    # Get mlserver commit hash
    mlserver_commit = get_mlserver_commit_hash()
    if mlserver_commit:
        labels["com.mlserver.commit"] = mlserver_commit

    # Get mlserver git URL
    mlserver_git_url = _get_mlserver_git_url()
    if mlserver_git_url:
        labels["com.mlserver.git_url"] = mlserver_git_url

    # Get mlserver version from package
    try:
        import mlserver
        if hasattr(mlserver, '__version__'):
            labels["com.mlserver.version"] = mlserver.__version__
    except Exception:
        pass

    # ========================================================================
    # Classifier Repository Information
    # ========================================================================

    # Get classifier git info
    classifier_git_info = get_git_info(project_path)
    if classifier_git_info:
        labels["com.classifier.git_commit"] = classifier_git_info.commit
        labels["com.classifier.git_branch"] = classifier_git_info.branch

        if classifier_git_info.tag:
            labels["com.classifier.git_tag"] = classifier_git_info.tag

    # Get classifier git remote URL
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            labels["com.classifier.git_url"] = result.stdout.strip()
    except Exception:
        pass

    # ========================================================================
    # Classifier Version Information
    # ========================================================================

    if classifier_name:
        labels["com.classifier.name"] = classifier_name

        # Get version from git tag
        git_mgr = GitVersionManager(project_path)
        version = git_mgr.get_current_version(classifier_name)
        if version:
            labels["com.classifier.version"] = version

        # If on a tagged commit, parse the tag for full info
        if classifier_git_info and classifier_git_info.tag:
            parsed = parse_hierarchical_tag(classifier_git_info.tag)
            if parsed["format"] == "valid" and parsed["classifier"] == classifier_name:
                # Tag matches this classifier
                labels["com.classifier.version"] = parsed["version"]
                labels["com.classifier.tag.mlserver_commit"] = parsed["mlserver_commit"]

    # Repository name
    repo_name = get_repository_name(project_path)
    labels["com.classifier.repository"] = repo_name

    # ========================================================================
    # Standard OCI Labels
    # ========================================================================

    # Image metadata
    if classifier_name:
        labels["org.opencontainers.image.title"] = f"{classifier_name}-classifier"
        labels["org.opencontainers.image.description"] = f"ML classifier: {classifier_name}"

    # Version from classifier
    if "com.classifier.version" in labels:
        labels["org.opencontainers.image.version"] = labels["com.classifier.version"]

    # Build timestamp
    labels["org.opencontainers.image.created"] = build_time

    # Source repository
    if "com.classifier.git_url" in labels:
        labels["org.opencontainers.image.source"] = labels["com.classifier.git_url"]

    # Revision (git commit)
    if "com.classifier.git_commit" in labels:
        labels["org.opencontainers.image.revision"] = labels["com.classifier.git_commit"]

    # ========================================================================
    # Additional Metadata from Config
    # ========================================================================

    if config:
        # Add predictor class information
        if config.predictor and config.predictor.class_name:
            labels["com.classifier.predictor.class"] = config.predictor.class_name
            labels["com.classifier.predictor.module"] = config.predictor.module

    return labels


def _get_mlserver_git_url() -> Optional[str]:
    """
    Detect if mlserver-fastapi-wrapper is installed from git and return the install URL.

    Checks the following in order:
    1. MLSERVER_GIT_URL environment variable (allows manual override)
    2. direct_url.json from pip installation metadata
    3. Editable install source directory
    4. Current package location if it's a git repo

    Returns:
        Git URL in pip-installable format (e.g., 'git+https://github.com/user/repo.git@branch')
        or None if not installed from git
    """
    try:
        import subprocess

        # Strategy 0: Check environment variable override
        env_git_url = os.environ.get('MLSERVER_GIT_URL')
        if env_git_url:
            print(f"Using MLSERVER_GIT_URL from environment: {env_git_url}")
            return env_git_url

        try:
            from importlib.metadata import distribution
        except ImportError:
            # Python < 3.8
            from importlib_metadata import distribution

        # Get the package distribution
        try:
            dist = distribution('mlserver-fastapi-wrapper')
        except Exception:
            return None

        # Try multiple strategies to find the source directory
        source_dir = None

        # Strategy 1: Check if it's installed via pip from git (check direct_url.json)
        try:
            direct_url_file = Path(dist._path) / 'direct_url.json'
            if direct_url_file.exists():
                import json
                with open(direct_url_file, 'r') as f:
                    direct_url_data = json.load(f)
                    if 'url' in direct_url_data and 'git+' in direct_url_data['url']:
                        # This is a git installation, return the URL directly
                        return direct_url_data['url']
                    elif 'vcs_info' in direct_url_data:
                        vcs = direct_url_data['vcs_info']
                        if 'vcs' in vcs and vcs['vcs'] == 'git':
                            url = direct_url_data.get('url', '')
                            commit = vcs.get('commit_id', vcs.get('requested_revision', 'main'))
                            if url:
                                return f"git+{url}@{commit}"
        except Exception:
            pass

        # Strategy 2: Check location for editable installs
        try:
            location = str(dist._path.parent.parent)  # Get site-packages parent
            if '/src/' in location:
                # Editable install - find the git directory
                parts = location.split('/src/')
                if len(parts) > 1:
                    base_path = parts[0] + '/src/mlserver-fastapi-wrapper'
                    if Path(base_path).exists():
                        source_dir = base_path
        except Exception:
            pass

        # Strategy 3: Check if we're running from the git repo itself
        if not source_dir:
            source_path = Path(__file__).parent.parent
            if (source_path / '.git').exists():
                source_dir = str(source_path)

        # If we found a source directory with git, extract the URL
        if source_dir:
            git_config = Path(source_dir) / '.git' / 'config'
            if git_config.exists():
                # Parse git config for remote URL
                with open(git_config, 'r') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if 'url = ' in line:
                            url = line.split('url = ')[1].strip()

                            # Get current branch/commit
                            try:
                                result = subprocess.run(
                                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                    cwd=source_dir,
                                    capture_output=True,
                                    text=True
                                )
                                if result.returncode == 0:
                                    branch = result.stdout.strip()
                                    # Return in pip-installable format
                                    return f"git+{url}@{branch}"
                            except Exception:
                                # Fallback to main branch
                                return f"git+{url}@main"

                            return f"git+{url}@main"

        return None

    except Exception as e:
        # If detection fails, return None and fall back to other methods
        print(f"Note: Could not detect git installation source: {e}")
        return None


def _find_mlserver_source() -> Optional[str]:
    """Find mlserver source directory with multiple detection strategies."""
    # Strategy 1: Check environment variable
    env_path = os.environ.get('MLSERVER_SOURCE_PATH')
    if env_path and Path(env_path).exists():
        return env_path

    # Strategy 2: Original behavior - walk up from package location
    current_path = Path(__file__).parent.parent  # Start from mlserver package parent

    # Look for pyproject.toml that contains mlserver-fastapi-wrapper
    for _ in range(5):  # Don't search too deep
        pyproject_path = current_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib
            except ImportError:
                # Python < {}, use tomli".format(get_settings().container.python_version_threshold)
                try:
                    import tomli as tomllib
                except ImportError:
                    break

            try:
                with open(pyproject_path, "rb") as f:
                    pyproject = tomllib.load(f)
                    if pyproject.get("project", {}).get("name") == "mlserver-fastapi-wrapper":
                        return str(current_path)
            except Exception:
                pass

        current_path = current_path.parent
        if current_path == current_path.parent:  # Reached root
            break

    return None


def _build_mlserver_wheel(mlserver_source_path: str, project_path: str) -> Optional[str]:
    """Build mlserver wheel and copy to project directory."""
    try:
        print(f"Building mlserver wheel from source: {mlserver_source_path}")

        # Build wheel in mlserver source directory
        # Use sys.executable to ensure we use the same Python that's running this script
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel"],
            cwd=mlserver_source_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Warning: Failed to build mlserver wheel: {result.stderr}")
            return None

        # Find the built wheel
        dist_dir = Path(mlserver_source_path) / "dist"
        wheel_files = list(dist_dir.glob("mlserver_fastapi_wrapper-*.whl"))

        if not wheel_files:
            print("Warning: No wheel file found after build")
            return None

        # Get the most recent wheel
        latest_wheel = max(wheel_files, key=lambda p: p.stat().st_mtime)

        # Copy to project directory
        dest_path = Path(project_path) / latest_wheel.name
        import shutil
        shutil.copy2(latest_wheel, dest_path)

        print(f"✓ Built and copied wheel: {latest_wheel.name}")
        return latest_wheel.name

    except Exception as e:
        print(f"Warning: Failed to build mlserver wheel: {e}")
        return None


def _add_file_or_directory(path: str, project_path: str, file_set: set) -> None:
    """Add a file or directory to the file set, handling relative paths."""
    if not path:
        return

    # Resolve relative paths
    if path.startswith('./'):
        file_path = path[2:]
    elif path.startswith('../'):
        # Skip files outside project directory
        return
    else:
        file_path = path

    full_path = os.path.join(project_path, file_path)
    if os.path.exists(full_path):
        if os.path.isfile(full_path):
            file_set.add(file_path)
        elif os.path.isdir(full_path):
            # Add entire directory with relative paths
            for root, dirs, files in os.walk(full_path):
                # Skip __pycache__ directories
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for file in files:
                    # Ensure we get relative paths from project root
                    abs_file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_file_path, project_path)
                    file_set.add(rel_path)


def detect_required_files(project_path: str, config: AppConfig) -> Dict[str, Any]:
    """
    Intelligently detect files required for containerization.

    Args:
        project_path: Path to the classifier project
        config: Loaded configuration

    Returns:
        Dictionary with detected files and analysis
    """
    required_files = set()
    analysis = {
        "predictor_files": set(),
        "artifact_files": set(),
        "dependency_files": set(),
        "config_files": set(),
        "auto_excludes": set()
    }

    # 1. Add the predictor module file
    predictor_module = config.predictor.module
    predictor_file = f"{predictor_module.replace('.', '/')}.py"
    if os.path.exists(os.path.join(project_path, predictor_file)):
        analysis["predictor_files"].add(predictor_file)
    else:
        # Try with just the module name
        predictor_file = f"{predictor_module}.py"
        if os.path.exists(os.path.join(project_path, predictor_file)):
            analysis["predictor_files"].add(predictor_file)

    # 2. Parse predictor init_kwargs for file paths
    init_kwargs = config.predictor.init_kwargs
    for key, value in init_kwargs.items():
        if isinstance(value, str) and _looks_like_file_path(key, value):
            _add_file_or_directory(value, project_path, analysis["artifact_files"])

    # 2a. Parse API config for file paths (especially feature_order)
    if hasattr(config, 'api') and config.api:
        # Check feature_order - can be a file path string
        if isinstance(config.api.feature_order, str):
            _add_file_or_directory(config.api.feature_order, project_path, analysis["artifact_files"])

    # 2b. Recursively scan ALL config values for potential file paths
    def scan_config_for_paths(obj, path_set):
        """Recursively scan config object for file paths."""
        if isinstance(obj, str):
            # Check if this looks like a file path
            if ('/' in obj or obj.endswith('.json') or obj.endswith('.yaml') or
                obj.endswith('.pkl') or obj.endswith('.txt') or obj.endswith('.csv')):
                _add_file_or_directory(obj, project_path, path_set)
        elif isinstance(obj, dict):
            for value in obj.values():
                scan_config_for_paths(value, path_set)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                scan_config_for_paths(item, path_set)
        elif hasattr(obj, '__dict__'):
            # For Pydantic models and other objects
            scan_config_for_paths(obj.__dict__, path_set)

    # Scan entire config for any file references
    scan_config_for_paths(config, analysis["artifact_files"])

    # 3. Add configuration files
    config_files = ["mlserver.yaml", "config.yaml", "classifier.yaml", "requirements.txt"]
    for config_file in config_files:
        if os.path.exists(os.path.join(project_path, config_file)):
            analysis["config_files"].add(config_file)

    # 4. Detect Python dependencies by parsing imports
    try:
        predictor_deps = _analyze_python_imports(project_path, predictor_file)
        for dep in predictor_deps:
            if dep.endswith('/'):
                # It's a directory - include all Python files in it
                dir_path = os.path.join(project_path, dep.rstrip('/'))
                if os.path.exists(dir_path):
                    for root, dirs, files in os.walk(dir_path):
                        # Skip __pycache__ directories
                        dirs[:] = [d for d in dirs if d != '__pycache__']
                        for file in files:
                            if file.endswith('.py') or file.endswith('.json') or file.endswith('.pkl'):
                                rel_path = os.path.relpath(os.path.join(root, file), project_path)
                                analysis["dependency_files"].add(rel_path)
            else:
                analysis["dependency_files"].add(dep)
    except Exception as e:
        # If import analysis fails, continue without it
        print(f"Warning: Failed to analyze imports: {e}")
        pass

    # 5. Auto-exclude common non-essential files
    auto_excludes = {
        "__pycache__", "*.pyc", "*.pyo", "*.pyd", ".git", ".gitignore",
        ".vscode", ".idea", "*.log", "*.tmp", "catboost_info", "*.swp",
        ".DS_Store", "Thumbs.db", "Dockerfile", ".dockerignore"
    }
    analysis["auto_excludes"] = auto_excludes

    # Combine all required files
    required_files.update(analysis["predictor_files"])
    required_files.update(analysis["artifact_files"])
    required_files.update(analysis["config_files"])
    required_files.update(analysis["dependency_files"])

    return {
        "required_files": sorted(list(required_files)),
        "analysis": {k: sorted(list(v)) if isinstance(v, set) else v for k, v in analysis.items()}
    }


def _looks_like_file_path(key: str, value: str) -> bool:
    """Check if a key-value pair likely represents a file path."""
    path_indicators = ['path', 'file', 'model', 'preprocessor', 'artifact', 'data', 'dir', 'folder']
    key_suggests_path = any(indicator in key.lower() for indicator in path_indicators)

    # Check if value looks like a file path
    is_path_like = (
        '/' in value or '\\' in value or
        value.startswith('./') or value.startswith('../') or
        '.' in value  # Has file extension
    )

    return key_suggests_path and is_path_like


def _analyze_python_imports(project_path: str, python_file: str) -> Set[str]:
    """Analyze Python file for local module imports."""
    local_files = set()

    try:
        file_path = os.path.join(project_path, python_file)
        if not os.path.exists(file_path):
            return local_files

        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_file = _resolve_local_import(project_path, alias.name)
                    if local_file:
                        local_files.add(local_file)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    local_file = _resolve_local_import(project_path, node.module)
                    if local_file:
                        local_files.add(local_file)

    except Exception:
        # If parsing fails, continue without import analysis
        pass

    return local_files


def _resolve_local_import(project_path: str, module_name: str) -> Optional[str]:
    """Resolve a module name to a local file if it exists."""
    # Convert module.submodule to module/submodule.py
    module_path = module_name.replace('.', '/')

    # Try various file patterns
    candidates = [
        f"{module_path}.py",
        f"{module_path}/__init__.py",
        f"{module_name}.py"  # Direct file name
    ]

    for candidate in candidates:
        full_path = os.path.join(project_path, candidate)
        if os.path.exists(full_path):
            return candidate

    return None


def generate_dockerignore(project_path: str, auto_excludes: Set[str],
                         additional_excludes: Optional[List[str]] = None) -> str:
    """Generate .dockerignore content."""
    excludes = list(auto_excludes)
    if additional_excludes:
        excludes.extend(additional_excludes)

    dockerignore_content = f"""# Auto-generated .dockerignore
# Generated at: {datetime.now().isoformat()}

# Python cache and compiled files
__pycache__/
*.py[cod]
*$py.class
*.so

# Development and IDE files
.git/
.gitignore
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Temporary and log files
*.log
*.tmp
*.temp

# Model training artifacts (keep only final artifacts)
catboost_info/

# Docker files (will be regenerated)
Dockerfile
.dockerignore

# Additional excludes
"""

    if additional_excludes:
        for exclude in additional_excludes:
            dockerignore_content += f"{exclude}\n"

    return dockerignore_content


def generate_dockerfile(project_path: str, config: AppConfig,
                       required_files: List[str], base_image: str = None,
                       has_wheel: bool = False, needs_git: bool = False,
                       classifier_name: Optional[str] = None) -> str:
    """
    Generate Dockerfile content for the classifier project with intelligent file copying.

    Args:
        project_path: Path to the project
        config: AppConfig instance
        required_files: List of files to copy
        base_image: Base Docker image (optional)
        has_wheel: Whether a wheel file is available
        needs_git: Whether git needs to be installed in the container
        classifier_name: Name of classifier being built (for labels)

    Returns:
        Dockerfile content as string
    """

    # Use default base image if not provided
    if base_image is None:
        base_image = get_settings().container.default_base_image

    # Use modern config file format
    config_file = "mlserver.yaml"

    # Check for requirements.txt
    requirements_file = Path(project_path) / "requirements.txt"
    additional_deps = ""
    if requirements_file.exists():
        additional_deps = f"\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt"

    # Generate file copy commands
    copy_commands = []

    # Group files by directory for efficient copying
    dirs_to_copy = set()
    files_to_copy = []

    for file_path in required_files:
        if '/' in file_path:
            # File in subdirectory
            dir_name = os.path.dirname(file_path)
            dirs_to_copy.add(dir_name)
        else:
            # File in root
            files_to_copy.append(file_path)

    # Add copy commands for directories (use relative paths)
    for dir_name in sorted(dirs_to_copy):
        copy_commands.append(f"COPY {dir_name}/ ./{dir_name}/")

    # Add copy commands for individual files
    if files_to_copy:
        file_list = " ".join(files_to_copy)
        copy_commands.append(f"COPY {file_list} ./")

    copy_section = "\n".join(copy_commands) if copy_commands else "COPY . ."

    # Determine system dependencies based on installation method
    base_system_deps = ["gcc", "g++", "curl"]
    if needs_git:
        base_system_deps.insert(0, "git")  # Add git at the beginning if needed

    system_deps_line = " \\\n    ".join(base_system_deps)

    # Generate wheel installation section
    if has_wheel:
        temp_dir = get_settings().container.temp_dir
        wheel_install_section = f"""COPY mlserver_fastapi_wrapper*.whl {temp_dir}/
RUN pip install --no-cache-dir {temp_dir}/mlserver_fastapi_wrapper*.whl && rm {temp_dir}/mlserver_fastapi_wrapper*.whl"""
    else:
        # Try to detect if installed from git
        git_url = _get_mlserver_git_url()
        if git_url and needs_git:
            wheel_install_section = f"""# Installing from git repository (detected from current installation)
# Git is installed in system dependencies to support pip git clone
RUN pip install --no-cache-dir "{git_url}"#egg=mlserver-fastapi-wrapper"""
        elif git_url:
            wheel_install_section = f"""# Installing from git repository (detected from current installation)
# Note: This should not happen - wheel should have been built
RUN pip install --no-cache-dir "{git_url}"#egg=mlserver-fastapi-wrapper"""
        else:
            wheel_install_section = """# No local wheel found, installing from PyPI
RUN pip install --no-cache-dir mlserver-fastapi-wrapper"""

    # Get classifier info for labels
    classifier_name = "unknown"
    classifier_version = "1.0.0"
    classifier_description = "ML Classifier"

    if config.classifier:
        if isinstance(config.classifier, dict):
            classifier_name = config.classifier.get('name', 'unknown')
            classifier_version = config.classifier.get('version', '1.0.0')
            classifier_description = config.classifier.get('description', 'ML Classifier')
        else:
            classifier_name = config.classifier.classifier.name
            classifier_version = config.classifier.classifier.version
            classifier_description = config.classifier.classifier.description
    elif config.classifier_metadata:
        classifier_name = config.classifier_metadata.classifier.name
        classifier_version = config.classifier_metadata.classifier.version
        classifier_description = config.classifier_metadata.classifier.description

    # Capture git info at build time (before containerization)
    from .version import get_git_info
    git_info = get_git_info(project_path)
    git_commit = git_info.commit if git_info else None
    git_tag = git_info.tag if git_info else None
    git_branch = git_info.branch if git_info else None

    # Also capture MLServer framework git info
    from .auto_detect import get_mlserver_git_info
    mlserver_git_info = get_mlserver_git_info()
    mlserver_api_commit = mlserver_git_info.get("api_commit", "")
    mlserver_api_tag = mlserver_git_info.get("api_tag", "")
    mlserver_api_branch = mlserver_git_info.get("api_branch", "")

    dockerfile_content = f'''# Generated Dockerfile for {classifier_name} v{classifier_version}
# Generated at: {datetime.now().isoformat()}

FROM {base_image}

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    {system_deps_line} \\
    && rm -rf /var/lib/apt/lists/*

# Install mlserver-fastapi-wrapper
{wheel_install_section}

# Copy project files (intelligently selected)
{copy_section}
{additional_deps}

# Set PYTHONPATH to include current directory for local modules
ENV PYTHONPATH=/app

# Embed build-time metadata as environment variables
ENV MLSERVER_CONFIG_FILE="{config_file}"
ENV MLSERVER_GIT_COMMIT="{git_commit or ''}"
ENV MLSERVER_GIT_TAG="{git_tag or ''}"
ENV MLSERVER_GIT_BRANCH="{git_branch or ''}"
ENV MLSERVER_API_COMMIT="{mlserver_api_commit or ''}"
ENV MLSERVER_API_TAG="{mlserver_api_tag or ''}"
ENV MLSERVER_API_BRANCH="{mlserver_api_branch or ''}"
ENV MLSERVER_BUILD_TIME="{datetime.now().isoformat()}"

# Create non-root user
RUN useradd --create-home --shell /bin/bash mlserver
RUN chown -R mlserver:mlserver /app
USER mlserver

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f {get_settings().get_health_url()} || exit 1

# Expose port
EXPOSE 8000

# Set labels for metadata (comprehensive traceability)
{_generate_label_directives(project_path, classifier_name, config)}

# Command to run the server
CMD ["mlserver", "serve", "{config_file}"]
'''

    return dockerfile_content


def _generate_label_directives(project_path: str, classifier_name: Optional[str], config: Optional['AppConfig'] = None) -> str:
    """Generate LABEL directives for Dockerfile from container labels.

    Args:
        project_path: Path to project
        classifier_name: Name of classifier
        config: AppConfig instance

    Returns:
        String containing all LABEL directives, one per line
    """
    labels = generate_container_labels(project_path, classifier_name, config)

    label_lines = []
    for key, value in sorted(labels.items()):
        # Escape double quotes in values
        escaped_value = value.replace('"', '\\"')
        label_lines.append(f'LABEL {key}="{escaped_value}"')

    return "\n".join(label_lines)


def _load_container_config(project_path: str, config_file: Optional[str] = None, classifier_name: Optional[str] = None) -> 'AppConfig':
    """Load and validate configuration for container build."""
    from .cli import detect_config_file
    from .config import AppConfig
    from .multi_classifier import detect_multi_classifier_config, load_multi_classifier_config, extract_single_classifier_config
    import yaml

    if not config_file:
        config_file = detect_config_file(None)

    config_path = os.path.join(project_path, config_file)

    # Check if multi-classifier config
    if detect_multi_classifier_config(config_path):
        # Load multi-classifier config
        multi_config = load_multi_classifier_config(config_path)

        if classifier_name and classifier_name in multi_config.classifiers:
            # Extract specific classifier config
            return extract_single_classifier_config(multi_config, classifier_name)
        else:
            # Use default or first classifier
            if multi_config.default_classifier and multi_config.default_classifier in multi_config.classifiers:
                return extract_single_classifier_config(multi_config, multi_config.default_classifier)
            else:
                # Return first config
                first_classifier = next(iter(multi_config.classifiers.keys()))
                return extract_single_classifier_config(multi_config, first_classifier)
    else:
        # Single classifier config
        with open(config_path, "r") as f:
            raw_config = yaml.safe_load(f)

        # For Docker builds, keep paths relative - don't resolve to absolute paths
        # The paths will be resolved inside the container relative to the WORKDIR /app
        return AppConfig.model_validate(raw_config)


def _find_git_source_directory() -> Optional[str]:
    """
    Find the local git source directory for mlserver-fastapi-wrapper.

    Returns:
        Path to the git source directory, or None if not found
    """
    try:
        try:
            from importlib.metadata import distribution
        except ImportError:
            from importlib_metadata import distribution

        dist = distribution('mlserver-fastapi-wrapper')

        # Check for editable install location
        location = str(dist._path.parent.parent)
        if '/src/' in location:
            parts = location.split('/src/')
            if len(parts) > 1:
                base_path = parts[0] + '/src/mlserver-fastapi-wrapper'
                if Path(base_path).exists() and (Path(base_path) / '.git').exists():
                    return base_path

        # Check if current package is from git repo
        source_path = Path(__file__).parent.parent
        if (source_path / '.git').exists():
            return str(source_path)

    except Exception:
        pass

    return None


def _handle_wheel_preparation(project_path: str, mlserver_source_path: Optional[str] = None,
                              git_url: Optional[str] = None) -> Tuple[Optional[str], bool]:
    """
    Check for existing wheels or build one if needed.

    Args:
        project_path: Path to the project
        mlserver_source_path: Explicit source path (optional)
        git_url: Git URL if detected (optional)

    Returns:
        Tuple of (wheel_filename, needs_git_in_dockerfile)
        - wheel_filename: Name of wheel file if created, None otherwise
        - needs_git_in_dockerfile: True if git needs to be installed in Dockerfile
    """
    existing_wheels = list(Path(project_path).glob("mlserver_fastapi_wrapper-*.whl"))

    if existing_wheels:
        print("✓ Found existing mlserver wheel, will use it")
        return None, False

    # If we have a git URL, try to build a wheel from the local source
    if git_url:
        print("🔍 Git-based installation detected, attempting to build wheel from source...")

        # Try to find the git source directory
        git_source = _find_git_source_directory()

        if git_source:
            print(f"✓ Found git source at: {git_source}")
            wheel_file = _build_mlserver_wheel(git_source, project_path)
            if wheel_file:
                print(f"✓ Successfully built wheel from git source: {wheel_file}")
                return wheel_file, False
            else:
                print("⚠️  Failed to build wheel from git source")
        else:
            print("⚠️  Could not find local git source directory")

        # Couldn't build wheel from git source, will need git in Dockerfile
        print("→ Will install git in Docker container for pip installation")
        return None, True

    # No wheel present and no git URL, try to build one from traditional source
    if mlserver_source_path:
        wheel_file = _build_mlserver_wheel(mlserver_source_path, project_path)
        return wheel_file, False

    # Try to find source automatically
    found_source = _find_mlserver_source()
    if found_source:
        wheel_file = _build_mlserver_wheel(found_source, project_path)
        return wheel_file, False

    print("ℹ️  No mlserver wheel found and source not available. Will use PyPI installation.")
    return None, False


def _prepare_container_metadata(config: 'AppConfig', project_path: str) -> 'ClassifierMetadata':
    """Extract or create container metadata from configuration."""
    from .version import ClassifierMetadata, ClassifierVersion, ModelVersion, ApiVersion
    from .auto_detect import get_git_info, get_project_name
    from .version_control import parse_hierarchical_tag

    # Get git info for auto-detection
    git_info = get_git_info(project_path)

    # Extract version from hierarchical tag if present
    version_from_tag = '1.0.0'
    if git_info.get('tag'):
        tag = git_info.get('tag')
        parsed = parse_hierarchical_tag(tag)
        if parsed['format'] == 'valid':
            version_from_tag = parsed['version']
        else:
            # Fallback: try to extract version with simpler regex
            import re
            match = re.search(r'-v(\d+\.\d+\.\d+)', tag)
            if match:
                version_from_tag = match.group(1)
            elif re.match(r'^\d+\.\d+\.\d+$', tag):
                # Tag is already just a version
                version_from_tag = tag

    if config.classifier:
        # Use classifier metadata from unified config
        if isinstance(config.classifier, dict):
            # Ensure required fields have defaults
            classifier_data = config.classifier.copy()
            if 'repository' not in classifier_data or not classifier_data['repository']:
                classifier_data['repository'] = git_info.get('repository') or get_project_name(project_path)
            if 'version' not in classifier_data or not classifier_data['version']:
                classifier_data['version'] = version_from_tag

            model_data = config.model or {}
            if 'version' not in model_data or not model_data['version']:
                model_data['version'] = version_from_tag

            return ClassifierMetadata.model_validate({
                "classifier": classifier_data,
                "model": model_data,
                "api": config.api.model_dump() if config.api else {}
            })
        else:
            return config.classifier

    # Try to load from separate classifier.yaml
    try:
        return load_classifier_metadata(project_path)
    except FileNotFoundError:
        # Create minimal metadata from config with auto-detected values
        return ClassifierMetadata(
            classifier=ClassifierVersion(
                repository=git_info.get('repository') or get_project_name(project_path),
                name="classifier",
                version=version_from_tag
            ),
            model=ModelVersion(version=version_from_tag),
            api=ApiVersion()
        )


def _generate_container_tags(metadata: 'ClassifierMetadata', config: 'AppConfig',
                            project_path: str, tag_prefix: Optional[str] = None,
                            registry: Optional[str] = None, classifier_name: Optional[str] = None) -> List[str]:
    """Generate final container tags with prefixes and registry."""
    from .version_control import GitVersionManager

    git_info = get_git_info(project_path)

    # Use hierarchical git tags if available
    if classifier_name:
        git_mgr = GitVersionManager(project_path)
        git_version = git_mgr.get_current_version(classifier_name)

        if git_version:
            # Override metadata version with git tag version
            metadata.classifier.version = git_version
        else:
            # No git tag found - use placeholder to make it clear
            metadata.classifier.version = "missing-git-tag"
            print(f"⚠️  Warning: No git tag found for classifier '{classifier_name}'")
            print(f"   Run 'mlserver tag --classifier {classifier_name} <major|minor|patch>' to create a version tag")

    predictor_class = config.predictor.class_name if config.predictor else None
    base_tags = generate_container_tags(metadata, git_info, predictor_class, project_path, classifier_name)

    final_tags = []
    for tag in base_tags:
        final_tag = tag
        if tag_prefix:
            final_tag = f"{tag_prefix}/{final_tag}"
        if registry:
            final_tag = f"{registry}/{final_tag}"
        final_tags.append(final_tag)

    return final_tags


def _prepare_docker_build_command(final_tags: List[str], build_args: Optional[Dict[str, str]] = None,
                                 no_cache: bool = False) -> List[str]:
    """Prepare Docker build command with all arguments."""
    build_cmd = ["docker", "build", ".", "-f", "Dockerfile"]

    # Add tags
    for tag in final_tags:
        build_cmd.extend(["-t", tag])

    # Add build args
    if build_args:
        for key, value in build_args.items():
            build_cmd.extend(["--build-arg", f"{key}={value}"])

    # Add no-cache flag
    if no_cache:
        build_cmd.append("--no-cache")

    return build_cmd


def _write_docker_files(project_path: str, config: 'AppConfig', required_files: List[str],
                       analysis: Dict[str, Any], has_wheel: bool, needs_git: bool,
                       classifier_name: Optional[str] = None) -> Tuple[Path, Path]:
    """Generate and write Dockerfile and .dockerignore files.

    Args:
        project_path: Path to the project
        config: AppConfig for the specific classifier
        required_files: List of files to copy to container
        analysis: File analysis results
        has_wheel: Whether a wheel is available
        needs_git: Whether git needs to be installed in container
        classifier_name: Name of specific classifier (for multi-classifier configs)
    """
    # Get base image from config
    base_image = get_settings().container.default_base_image
    if config.build and config.build.base_image:
        base_image = config.build.base_image

    # For multi-classifier configs, write a single-classifier mlserver.yaml
    temp_config_file = None
    if classifier_name:
        # Check if original is a multi-classifier config
        from .multi_classifier import detect_multi_classifier_config
        from .cli import detect_config_file

        original_config = detect_config_file(None)
        original_path = Path(project_path) / original_config

        if original_path.exists() and detect_multi_classifier_config(str(original_path)):
            # Write a temporary single-classifier config
            import yaml
            temp_config_file = Path(project_path) / f".mlserver.{classifier_name}.yaml"

            # Convert AppConfig to dict for the single classifier
            config_dict = {
                "server": config.server.model_dump(exclude_none=True),
                "predictor": config.predictor.model_dump(exclude_none=True),
                "observability": config.observability.model_dump(exclude_none=True) if config.observability else {},
                "api": config.api.model_dump(exclude_none=True) if config.api else {}
            }

            # Handle classifier field (could be dict or object)
            if hasattr(config, 'classifier') and config.classifier:
                if isinstance(config.classifier, dict):
                    config_dict["classifier"] = config.classifier
                else:
                    config_dict["classifier"] = config.classifier.model_dump(exclude_none=True)

            # Remove empty sections
            config_dict = {k: v for k, v in config_dict.items() if v}

            with open(temp_config_file, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

            # Update required_files to include the temp config instead of original
            if "mlserver.yaml" in required_files:
                required_files.remove("mlserver.yaml")
            required_files.append(f".mlserver.{classifier_name}.yaml")

    # Generate Dockerfile
    dockerfile_content = generate_dockerfile(project_path, config, required_files, base_image, has_wheel, needs_git, classifier_name)

    # If we created a temp config, update Dockerfile to rename it to mlserver.yaml
    if temp_config_file:
        # Find the COPY line for the temp config and replace it
        temp_filename = f".mlserver.{classifier_name}.yaml"
        # Look for the pattern in various formats
        for pattern in [
            f"COPY {temp_filename} ./",
            f"{temp_filename} ./",
            f"{temp_filename}"
        ]:
            if pattern in dockerfile_content:
                # Replace just the destination part to rename to mlserver.yaml
                if pattern == f"COPY {temp_filename} ./":
                    dockerfile_content = dockerfile_content.replace(
                        f"COPY {temp_filename} ./",
                        f"COPY {temp_filename} ./mlserver.yaml"
                    )
                elif " ./" in dockerfile_content and temp_filename in dockerfile_content:
                    # Handle case where it's part of a multi-file COPY
                    lines = dockerfile_content.split('\n')
                    for i, line in enumerate(lines):
                        if 'COPY ' in line and temp_filename in line:
                            # Replace the temp file with proper renaming
                            if temp_filename + ' ./' in line:
                                # Multiple files in one COPY - split them
                                other_files = line.replace('COPY ', '').replace('./', '').strip().split()
                                other_files.remove(temp_filename)
                                if other_files:
                                    lines[i] = f"COPY {' '.join(other_files)} ./"
                                    lines.insert(i+1, f"COPY {temp_filename} ./mlserver.yaml")
                                else:
                                    lines[i] = f"COPY {temp_filename} ./mlserver.yaml"
                            break
                    dockerfile_content = '\n'.join(lines)
                break

    dockerfile_path = Path(project_path) / "Dockerfile"
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)

    # Generate .dockerignore
    dockerignore_content = generate_dockerignore(
        project_path,
        analysis["auto_excludes"],
        config.build.exclude_patterns if config.build else None
    )
    dockerignore_path = Path(project_path) / ".dockerignore"
    with open(dockerignore_path, 'w') as f:
        f.write(dockerignore_content)

    return dockerfile_path, dockerignore_path, temp_config_file


def build_container(
    project_path: str = ".",
    config_file: Optional[str] = None,
    classifier_name: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    registry: Optional[str] = None,
    build_args: Optional[Dict[str, str]] = None,
    no_cache: bool = False,
    mlserver_source_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build Docker container for the classifier project with intelligent file detection.

    Args:
        project_path: Path to the classifier project
        config_file: Config file to use (auto-detected if None)
        tag_prefix: Optional prefix for container tags
        registry: Optional registry URL prefix
        build_args: Optional build arguments
        no_cache: Whether to use Docker cache
        mlserver_source_path: Path to mlserver source for wheel building

    Returns:
        Build result with tags and metadata
    """
    try:
        # Load configuration
        config = _load_container_config(project_path, config_file, classifier_name)

        # Detect if installed from git
        git_url = _get_mlserver_git_url()

        # Handle wheel preparation with git URL awareness
        wheel_file, needs_git = _handle_wheel_preparation(project_path, mlserver_source_path, git_url)
        existing_wheels = list(Path(project_path).glob("mlserver_fastapi_wrapper-*.whl"))
        has_wheel = bool(existing_wheels) or wheel_file is not None

        # Detect required files using intelligent analysis
        file_detection = detect_required_files(project_path, config)
        required_files = file_detection["required_files"]
        analysis = file_detection["analysis"]

        print(f"Intelligent file detection results:")
        print(f"  Predictor files: {analysis['predictor_files']}")
        print(f"  Artifact files: {len(analysis['artifact_files'])} files")
        print(f"  Config files: {analysis['config_files']}")
        print(f"  Total files to copy: {len(required_files)}")

        # Write Docker files (Dockerfile and .dockerignore)
        dockerfile_path, dockerignore_path, temp_config_file = _write_docker_files(
            project_path, config, required_files, analysis, has_wheel, needs_git, classifier_name
        )

        # Prepare container metadata and tags
        metadata = _prepare_container_metadata(config, project_path)
        final_tags = _generate_container_tags(metadata, config, project_path, tag_prefix, registry, classifier_name)

        # Prepare Docker build command
        build_cmd = _prepare_docker_build_command(final_tags, build_args, no_cache)

        # Execute build
        print(f"Building container for {metadata.classifier.name} v{metadata.classifier.version}...")
        print(f"Tags: {', '.join(final_tags)}")

        # Run Docker build with real-time output (verbose)
        print("\n" + "="*60)
        print("Docker build output:")
        print("="*60)

        process = subprocess.Popen(
            build_cmd,
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Stream output in real-time
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            print(line.rstrip())  # Print to console in real-time
            output_lines.append(line)

        process.wait()
        full_output = ''.join(output_lines)

        print("="*60)
        print(f"Build completed with exit code: {process.returncode}")
        print("="*60 + "\n")

        # Always clean up wheel files (even on failure)
        try:
            # Clean up auto-built wheel if we created it
            if wheel_file:
                wheel_path = Path(project_path) / wheel_file
                if wheel_path.exists():
                    wheel_path.unlink()
                    print(f"✓ Cleaned up temporary wheel: {wheel_file}")

            # Also clean up any other wheel files that might be left over
            for old_wheel in Path(project_path).glob("mlserver_fastapi_wrapper-*.whl"):
                try:
                    old_wheel.unlink()
                    print(f"✓ Cleaned up wheel: {old_wheel.name}")
                except Exception as e:
                    print(f"Warning: Could not remove {old_wheel.name}: {e}")

            # Clean up temp config file if we created it
            if temp_config_file and temp_config_file.exists():
                temp_config_file.unlink()
        except Exception as cleanup_error:
            print(f"Warning: Error during cleanup: {cleanup_error}")

        if process.returncode != 0:
            raise ContainerError(f"Docker build failed with exit code {process.returncode}")

        return {
            "success": True,
            "tags": final_tags,
            "dockerfile": str(dockerfile_path),
            "dockerignore": str(dockerignore_path),
            "required_files": required_files,
            "file_analysis": analysis,
            "metadata": metadata.model_dump(),
            "git_info": get_git_info(project_path).__dict__ if get_git_info(project_path) else None,
            "build_output": full_output
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def push_container(
    project_path: str = ".",
    registry: Optional[str] = None,
    tag_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Push container to registry.

    Args:
        project_path: Path to the classifier project
        registry: Registry URL (required for push)
        tag_prefix: Optional prefix for container tags

    Returns:
        Push result with status and pushed tags
    """
    try:
        if not registry:
            raise ContainerError("Registry URL is required for push operation")

        # Load classifier metadata
        metadata = load_classifier_metadata(project_path)
        git_info = get_git_info(project_path)

        # Generate container tags
        base_tags = generate_container_tags(metadata, git_info)

        # Apply prefix and registry
        push_tags = []
        for tag in base_tags:
            final_tag = tag
            if tag_prefix:
                final_tag = f"{tag_prefix}/{final_tag}"
            final_tag = f"{registry}/{final_tag}"
            push_tags.append(final_tag)

        pushed_tags = []
        push_errors = []

        for tag in push_tags:
            print(f"Pushing {tag}...")
            result = subprocess.run(
                ["docker", "push", tag],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                pushed_tags.append(tag)
                print(f"✓ Successfully pushed {tag}")
            else:
                error_msg = f"Failed to push {tag}: {result.stderr}"
                push_errors.append(error_msg)
                print(f"✗ {error_msg}")

        return {
            "success": len(pushed_tags) > 0,
            "pushed_tags": pushed_tags,
            "failed_tags": push_errors,
            "registry": registry,
            "metadata": metadata.model_dump()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def list_images(project_path: str = ".") -> List[Dict[str, Any]]:
    """List Docker images for the classifier project."""
    try:
        metadata = load_classifier_metadata(project_path)
        # Get repository name from metadata or auto-detect
        if hasattr(metadata.classifier, 'repository') and metadata.classifier.repository:
            repository = metadata.classifier.repository
        else:
            repository = get_repository_name(project_path)

        # Use simpler Docker format without table to avoid parsing issues
        # Format: REPOSITORY:TAG|IMAGE_ID|CREATED|SIZE
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}|{{.ID}}|{{.CreatedAt}}|{{.Size}}"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return []

        images = []
        lines = result.stdout.strip().split('\n')

        for line in lines:
            if not line:  # Skip empty lines
                continue

            # Parse using pipe delimiter
            parts = line.split('|')
            if len(parts) >= 4:
                repo_tag = parts[0]
                # Check if this image belongs to our repository
                if repo_tag.startswith(repository):
                    images.append({
                        "tag": repo_tag,
                        "image_id": parts[1],
                        "created": parts[2],
                        "size": parts[3]
                    })

        return images

    except Exception as e:
        # Log the error for debugging (in real usage, use proper logging)
        import traceback
        import sys
        print(f"Error in list_images: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []


def remove_images(project_path: str = ".", force: bool = False) -> Dict[str, Any]:
    """Remove Docker images for the classifier project."""
    try:
        images = list_images(project_path)

        if not images:
            return {"success": True, "message": "No images found to remove"}

        removed_images = []
        removal_errors = []

        for image in images:
            cmd = ["docker", "rmi"]
            if force:
                cmd.append("-f")
            cmd.append(image["image_id"])

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                removed_images.append(image["tag"])
            else:
                removal_errors.append(f"Failed to remove {image['tag']}: {result.stderr}")

        return {
            "success": len(removed_images) > 0,
            "removed_images": removed_images,
            "errors": removal_errors
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def check_docker_availability() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False