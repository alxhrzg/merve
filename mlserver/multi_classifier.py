"""
Multi-Classifier Configuration Support

This module handles loading and managing configurations for repositories
that contain multiple classifiers.
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field

from .config import AppConfig, ServerConfig, ObservabilityConfig


class MultiClassifierConfig(BaseModel):
    """Configuration for repositories with multiple classifiers."""

    # Global configurations (shared by all classifiers)
    server: ServerConfig = ServerConfig()
    observability: ObservabilityConfig = ObservabilityConfig()

    # Repository metadata
    repository: Dict[str, Any] = Field(default_factory=dict)

    # Multiple classifier configurations
    classifiers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Default classifier to use when none specified
    default_classifier: Optional[str] = None

    # Deployment configuration
    deployment: Optional[Dict[str, Any]] = None


def load_multi_classifier_config(config_file: str) -> MultiClassifierConfig:
    """Load a multi-classifier configuration file.

    Args:
        config_file: Path to the YAML configuration file

    Returns:
        MultiClassifierConfig object
    """
    with open(config_file, 'r') as f:
        raw_config = yaml.safe_load(f)

    return MultiClassifierConfig.model_validate(raw_config)


def extract_single_classifier_config(
    multi_config: MultiClassifierConfig,
    classifier_name: str
) -> AppConfig:
    """Extract a single classifier configuration from multi-classifier config.

    Args:
        multi_config: The multi-classifier configuration
        classifier_name: Name of the classifier to extract

    Returns:
        AppConfig for the specified classifier

    Raises:
        ValueError: If classifier not found in configuration
    """
    if classifier_name not in multi_config.classifiers:
        available = list(multi_config.classifiers.keys())
        raise ValueError(
            f"Classifier '{classifier_name}' not found. "
            f"Available classifiers: {available}"
        )

    classifier_config = multi_config.classifiers[classifier_name]

    # Build AppConfig combining global and classifier-specific settings
    app_config_dict = {
        # Use global server and observability settings
        "server": multi_config.server.model_dump(),
        "observability": multi_config.observability.model_dump(),

        # Use classifier-specific predictor settings
        "predictor": classifier_config["predictor"],

        # Use classifier metadata (handle both old 'metadata' and new 'classifier' keys)
        "classifier": {
            **classifier_config.get("classifier", classifier_config.get("metadata", {})),
            "repository": multi_config.repository.get("name", "unknown")
        },

        # Use classifier-specific API settings
        "api": classifier_config.get("api", {}),

        # Model metadata if available (for backward compatibility)
        "model": classifier_config.get("model", {}),

        # Build configuration if available
        "build": classifier_config.get("build")
    }

    return AppConfig.model_validate(app_config_dict)


def list_available_classifiers(config_file: str) -> List[str]:
    """List all available classifiers in a configuration file.

    Args:
        config_file: Path to the configuration file

    Returns:
        List of classifier names
    """
    try:
        with open(config_file, 'r') as f:
            raw_config = yaml.safe_load(f)

        if "classifiers" not in raw_config:
            return []

        classifiers = raw_config["classifiers"]

        # Handle list format (array of classifier configs)
        if isinstance(classifiers, list):
            names = []
            for clf in classifiers:
                if isinstance(clf, dict):
                    # Try to get name from various possible locations
                    if "name" in clf:
                        names.append(clf["name"])
                    elif "classifier" in clf and isinstance(clf["classifier"], dict):
                        if "name" in clf["classifier"]:
                            names.append(clf["classifier"]["name"])
            return names

        # Handle dict format (dict of classifier configs)
        elif isinstance(classifiers, dict):
            return list(classifiers.keys())

        return []
    except Exception:
        # Fall back to single classifier (no list available)
        return []


def detect_multi_classifier_config(config_file: str) -> bool:
    """Detect if a configuration file is multi-classifier format.

    Args:
        config_file: Path to the configuration file

    Returns:
        True if multi-classifier format, False otherwise
    """
    try:
        with open(config_file, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Check for multi-classifier structure (supports both dict and list formats)
        return "classifiers" in raw_config and (
            isinstance(raw_config["classifiers"], dict) or
            isinstance(raw_config["classifiers"], list)
        )
    except Exception:
        return False


def get_default_classifier(config_file: str) -> Optional[str]:
    """Get the default classifier from a multi-classifier config.

    Args:
        config_file: Path to the configuration file

    Returns:
        Default classifier name or None
    """
    try:
        multi_config = load_multi_classifier_config(config_file)

        # Return explicitly set default
        if multi_config.default_classifier:
            return multi_config.default_classifier

        # Return first classifier as fallback
        if multi_config.classifiers:
            return list(multi_config.classifiers.keys())[0]

        return None
    except Exception:
        return None


def generate_dockerfile_for_classifier(
    multi_config: MultiClassifierConfig,
    classifier_name: str,
    output_dir: str = "."
) -> str:
    """Generate a Dockerfile for a specific classifier.

    Args:
        multi_config: The multi-classifier configuration
        classifier_name: Name of the classifier
        output_dir: Directory to write Dockerfile

    Returns:
        Path to the generated Dockerfile
    """
    if classifier_name not in multi_config.classifiers:
        raise ValueError(f"Classifier '{classifier_name}' not found")

    classifier_config = multi_config.classifiers[classifier_name]

    # Use custom template if provided
    if "build" in classifier_config and "dockerfile_template" in classifier_config["build"]:
        dockerfile_content = classifier_config["build"]["dockerfile_template"]
    else:
        # Generate default Dockerfile
        dockerfile_content = f"""FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV MLSERVER_CLASSIFIER={classifier_name}

# Run the server with specific classifier
CMD ["mlserver", "serve", "--classifier", "{classifier_name}"]
"""

    # Write Dockerfile
    dockerfile_path = os.path.join(output_dir, f"Dockerfile.{classifier_name}")
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)

    return dockerfile_path


def build_all_classifiers(
    config_file: str,
    registry: Optional[str] = None,
    parallel: bool = False
) -> Dict[str, Any]:
    """Build containers for all classifiers in a multi-classifier config.

    Args:
        config_file: Path to the configuration file
        registry: Container registry URL
        parallel: Whether to build in parallel

    Returns:
        Build results for each classifier
    """
    multi_config = load_multi_classifier_config(config_file)
    results = {}

    for classifier_name in multi_config.classifiers:
        print(f"\n=== Building classifier: {classifier_name} ===")

        # Generate Dockerfile
        dockerfile_path = generate_dockerfile_for_classifier(
            multi_config, classifier_name
        )

        # Build container (would integrate with existing container.py)
        # For now, just record the intent
        results[classifier_name] = {
            "dockerfile": dockerfile_path,
            "status": "pending",
            "registry": registry
        }

        if not parallel:
            # In real implementation, would call build_container here
            print(f"Would build {classifier_name} with {dockerfile_path}")

    return results