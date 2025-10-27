"""
Project initialization for MLServer classifier projects.
"""
import os
import re
from pathlib import Path
from typing import Dict, Tuple, Optional, List


def sanitize_name(name: str) -> str:
    """Sanitize a name for use in Python identifiers."""
    # Replace spaces and hyphens with underscores
    name = re.sub(r'[-\s]+', '_', name)
    # Remove any non-alphanumeric characters except underscores
    name = re.sub(r'[^\w]', '', name)
    # Ensure it starts with a letter or underscore
    if name and name[0].isdigit():
        name = '_' + name
    return name.lower()


def generate_mlserver_yaml(
    classifier_name: str,
    predictor_module: str,
    predictor_class: str,
    version: str = "1.0.0",
    description: str = ""
) -> str:
    """Generate mlserver.yaml configuration content."""

    if not description:
        description = f"{classifier_name} ML classifier"

    template = f"""# MLServer Configuration
# This file defines your ML classifier and how it should be served

# Server configuration
server:
  host: "0.0.0.0"
  port: 8000
  workers: 1
  log_level: INFO

# Predictor configuration - your ML model/classifier
predictor:
  module: "{predictor_module}"
  class_name: "{predictor_class}"
  init_kwargs: {{}}
    # Add initialization arguments for your predictor here
    # Example:
    # model_path: "model.pkl"
    # feature_order: "features.json"

# Classifier metadata
classifier:
  name: "{classifier_name}"
  version: "{version}"
  description: "{description}"

# Model metadata
model:
  version: "{version}"
  # Add model training information
  # trained_at: "2024-01-01T00:00:00"
  # metrics:
  #   accuracy: 0.95

# API configuration
api:
  version: "v1"
  endpoints:
    predict: true
    predict_proba: true

# Observability
observability:
  metrics: true
  structured_logging: true
  correlation_ids: true
  log_payloads: false  # Set to true for debugging (careful with sensitive data)
"""

    return template


def generate_predictor_skeleton(
    class_name: str,
    classifier_name: str
) -> str:
    """Generate skeleton predictor class."""

    template = f'''"""
{classifier_name} predictor implementation.
"""
import numpy as np
from typing import Dict, Any, List, Union


class {class_name}:
    """
    Predictor for {classifier_name}.

    This class should implement your ML model inference logic.
    """

    def __init__(self, **kwargs):
        """
        Initialize the predictor.

        Args:
            **kwargs: Configuration parameters from mlserver.yaml predictor.init_kwargs
                     Example: model_path, feature_order, preprocessor_path, etc.
        """
        # TODO: Load your model and any required artifacts
        # Example:
        # import pickle
        # with open(kwargs.get('model_path'), 'rb') as f:
        #     self.model = pickle.load(f)

        self.model = None  # Replace with your actual model loading
        self.feature_order = kwargs.get('feature_order', [])

        print(f"{{self.__class__.__name__}} initialized")

    def predict(self, data: Union[List[Dict[str, Any]], np.ndarray]) -> np.ndarray:
        """
        Make predictions on input data.

        Args:
            data: Input data in one of two formats:
                  - List of dictionaries (records format): [{{"feature1": value1, "feature2": value2}}, ...]
                  - NumPy array (ndarray format): shape (n_samples, n_features)

        Returns:
            NumPy array of predictions, shape (n_samples,)
        """
        # TODO: Implement your prediction logic
        # Example:
        # if isinstance(data, list):
        #     # Convert records to numpy array
        #     X = self._records_to_array(data)
        # else:
        #     X = data
        #
        # predictions = self.model.predict(X)
        # return predictions

        raise NotImplementedError("predict method must be implemented")

    def predict_proba(self, data: Union[List[Dict[str, Any]], np.ndarray]) -> np.ndarray:
        """
        Predict class probabilities for input data.

        Args:
            data: Input data (same format as predict method)

        Returns:
            NumPy array of class probabilities, shape (n_samples, n_classes)
        """
        # TODO: Implement probability prediction if your model supports it
        # Example:
        # if isinstance(data, list):
        #     X = self._records_to_array(data)
        # else:
        #     X = data
        #
        # probabilities = self.model.predict_proba(X)
        # return probabilities

        raise NotImplementedError("predict_proba method must be implemented")

    def _records_to_array(self, records: List[Dict[str, Any]]) -> np.ndarray:
        """
        Convert list of dictionaries to numpy array.

        Args:
            records: List of feature dictionaries

        Returns:
            NumPy array with features in correct order
        """
        if not self.feature_order:
            # If no feature order specified, use keys from first record
            self.feature_order = list(records[0].keys())

        # Extract features in correct order
        data = [[record.get(feat, 0) for feat in self.feature_order] for record in records]
        return np.array(data)
'''

    return template


def generate_gitignore() -> str:
    """Generate .gitignore for ML projects."""
    return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Jupyter
.ipynb_checkpoints/
*.ipynb

# Data and models (uncomment if you don't want to track)
# *.pkl
# *.joblib
# *.h5
# *.pt
# *.pth
# data/
# models/

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# MLServer specific
coverage.json
coverage.xml
"""


def init_mlserver_project(
    project_path: str = ".",
    classifier_name: Optional[str] = None,
    predictor_file: Optional[str] = None,
    predictor_class: Optional[str] = None,
    include_github_actions: bool = True,
    force: bool = False
) -> Tuple[bool, str, Dict[str, str]]:
    """
    Initialize a new MLServer classifier project.

    Args:
        project_path: Path to initialize project in
        classifier_name: Name of the classifier (if None, derived from directory)
        predictor_file: Name of predictor Python file (without .py)
        predictor_class: Name of predictor class
        include_github_actions: Whether to create GitHub Actions workflow
        force: Overwrite existing files

    Returns:
        Tuple of (success, message, files_created)
    """
    project_path = Path(project_path).resolve()

    # Ensure we're in a directory
    if not project_path.is_dir():
        return False, f"Path does not exist or is not a directory: {project_path}", {}

    files_created = {}
    files_skipped = []

    # Determine classifier name
    if not classifier_name:
        classifier_name = project_path.name

    # Sanitize names
    classifier_name_clean = sanitize_name(classifier_name)

    # Determine predictor file and class names
    if not predictor_file:
        predictor_file = f"{classifier_name_clean}_predictor"

    if not predictor_class:
        # Convert to PascalCase for class name
        predictor_class = ''.join(word.capitalize() for word in classifier_name_clean.split('_')) + 'Predictor'

    predictor_file_clean = sanitize_name(predictor_file)
    predictor_py_path = project_path / f"{predictor_file_clean}.py"

    # 1. Create mlserver.yaml
    mlserver_yaml_path = project_path / "mlserver.yaml"
    if mlserver_yaml_path.exists() and not force:
        files_skipped.append("mlserver.yaml (already exists)")

        # If mlserver.yaml exists, check what predictor it references
        try:
            import yaml
            with open(mlserver_yaml_path, 'r') as f:
                existing_config = yaml.safe_load(f)

            existing_predictor_module = existing_config.get('predictor', {}).get('module')
            if existing_predictor_module:
                # Use the predictor module from existing config
                predictor_file_clean = existing_predictor_module
                predictor_py_path = project_path / f"{predictor_file_clean}.py"
        except Exception:
            # If we can't read it, use the default we calculated
            pass
    else:
        yaml_content = generate_mlserver_yaml(
            classifier_name=classifier_name,
            predictor_module=predictor_file_clean,
            predictor_class=predictor_class,
            version="1.0.0",
            description=""
        )
        with open(mlserver_yaml_path, 'w') as f:
            f.write(yaml_content)
        files_created["mlserver.yaml"] = str(mlserver_yaml_path.relative_to(project_path))

    # 2. Create predictor Python file (if it doesn't exist)
    if predictor_py_path.exists():
        files_skipped.append(f"{predictor_file_clean}.py (already exists)")
    else:
        predictor_content = generate_predictor_skeleton(
            class_name=predictor_class,
            classifier_name=classifier_name
        )
        with open(predictor_py_path, 'w') as f:
            f.write(predictor_content)
        files_created["predictor"] = str(predictor_py_path.relative_to(project_path))

    # 3. Create .gitignore if it doesn't exist
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = generate_gitignore()
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        files_created["gitignore"] = ".gitignore"
    else:
        files_skipped.append(".gitignore (already exists)")

    # 4. Create GitHub Actions workflow if requested
    if include_github_actions:
        from .github_actions import init_github_actions

        gh_success, gh_message, gh_files = init_github_actions(
            project_path=str(project_path),
            python_version="3.11",
            registry="ghcr.io",
            force=force
        )

        if gh_success:
            files_created.update(gh_files)
        elif "already exists" in gh_message.lower():
            files_skipped.append(".github/workflows/ml-classifier-container-build.yml (already exists)")

    # Build success message
    if not files_created and files_skipped:
        message = "✓ Project already initialized! All required files exist."
    else:
        message = "✓ Project initialized successfully!"

    if files_skipped:
        message += f"\n\nSkipped (already exist):\n" + "\n".join(f"  - {f}" for f in files_skipped)

    return True, message, files_created


def check_project_files(
    project_path: str = ".",
    classifier_name: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Check if all required files exist for a classifier project.

    Args:
        project_path: Path to project
        classifier_name: Name of classifier (for specific checks)

    Returns:
        Tuple of (all_present, missing_files)
    """
    project_path = Path(project_path).resolve()
    missing_files = []

    # Check for mlserver.yaml
    mlserver_yaml = project_path / "mlserver.yaml"
    if not mlserver_yaml.exists():
        missing_files.append("mlserver.yaml")
        # Can't check predictor file without config
        return False, missing_files

    # Parse mlserver.yaml to get predictor module
    try:
        import yaml
        with open(mlserver_yaml, 'r') as f:
            config = yaml.safe_load(f)

        # Check if multi-classifier config
        if 'classifiers' in config:
            # Multi-classifier format
            if classifier_name and classifier_name in config['classifiers']:
                predictor_module = config['classifiers'][classifier_name].get('predictor', {}).get('module')
                if predictor_module:
                    predictor_file = project_path / f"{predictor_module}.py"
                    if not predictor_file.exists():
                        missing_files.append(f"{predictor_module}.py (predictor file)")
            # For multi-classifier, we don't fail if no classifier_name provided
        else:
            # Single-classifier format
            predictor_module = config.get('predictor', {}).get('module')
            if predictor_module:
                predictor_file = project_path / f"{predictor_module}.py"
                if not predictor_file.exists():
                    missing_files.append(f"{predictor_module}.py (predictor file)")
    except Exception:
        # If we can't parse, just warn about checking manually
        pass

    # Check for GitHub Actions workflow
    gh_workflow = project_path / ".github" / "workflows" / "ml-classifier-container-build.yml"
    if not gh_workflow.exists():
        missing_files.append(".github/workflows/ml-classifier-container-build.yml")

    return len(missing_files) == 0, missing_files
