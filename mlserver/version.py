"""
Version management utilities for ML server classifier projects.
"""
import os
import re
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

import yaml
from pydantic import BaseModel, Field, validator


@dataclass
class GitInfo:
    """Git repository information."""
    tag: Optional[str]
    commit: str
    branch: str
    is_dirty: bool


class ClassifierVersion(BaseModel):
    """Classifier version metadata schema."""
    repository: Optional[str] = Field(None, description="Repository name (auto-detected if not provided)")
    name: str = Field(..., description="Classifier name (used in URLs)")
    version: Optional[str] = Field("1.0.0", description="Semantic version (auto-detected from git tags if not provided)")
    description: str = Field("", description="Classifier description")

    @validator('repository')
    def validate_repository(cls, v):
        if v is None:
            return v
        # Ensure repository name is valid for Docker tags
        if not re.match(r'^[a-z0-9][a-z0-9-_.]*$', v):
            raise ValueError('Repository must start with alphanumeric and contain only lowercase letters, numbers, hyphens, underscores, and periods')
        return v

    @validator('name')
    def validate_name(cls, v):
        # Ensure name is URL-safe (allow underscores for compatibility)
        if not re.match(r'^[a-z0-9][a-z0-9_-]*$', v):
            raise ValueError('Name must start with lowercase letter or number, and contain only lowercase letters, numbers, underscores, and hyphens')
        return v

    @validator('version')
    def validate_version(cls, v):
        if v is None:
            return "1.0.0"  # Default version
        # Validate semantic versioning
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Version must follow semantic versioning (e.g., 1.2.3)')
        return v


class ModelVersion(BaseModel):
    """Model artifact version metadata."""
    version: Optional[str] = Field("1.0.0", description="Model version (auto-detected from git tags if not provided)")
    trained_at: Optional[str] = Field(None, description="Training timestamp (ISO format)")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Model performance metrics")


class ApiVersion(BaseModel):
    """API versioning configuration."""
    version: str = Field("v1", description="API version (v1, v2, etc.)")
    endpoints: Dict[str, bool] = Field(
        default_factory=lambda: {
            "predict": True,
            # Note: batch_predict removed - /predict handles both single and batch
            "predict_proba": True
        },
        description="Enabled endpoints"
    )

    @validator('version')
    def validate_api_version(cls, v):
        if not re.match(r'^v\d+$', v):
            raise ValueError('API version must be in format v1, v2, etc.')
        return v


class ClassifierMetadata(BaseModel):
    """Complete classifier project metadata."""
    classifier: ClassifierVersion
    model: ModelVersion
    api: ApiVersion = Field(default_factory=ApiVersion)
    build: Dict[str, Any] = Field(default_factory=dict, description="Build configuration")


def get_git_info(project_path: str) -> Optional[GitInfo]:
    """Get git information for the project."""
    try:
        original_cwd = os.getcwd()
        os.chdir(project_path)

        # Get current commit
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                       stderr=subprocess.DEVNULL).decode().strip()

        # Get current branch
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                       stderr=subprocess.DEVNULL).decode().strip()

        # Check if repository is dirty
        status = subprocess.check_output(['git', 'status', '--porcelain'],
                                       stderr=subprocess.DEVNULL).decode().strip()
        is_dirty = len(status) > 0

        # Get latest tag (if any)
        try:
            tag = subprocess.check_output(['git', 'describe', '--tags', '--exact-match', 'HEAD'],
                                        stderr=subprocess.DEVNULL).decode().strip()
        except subprocess.CalledProcessError:
            tag = None

        return GitInfo(tag=tag, commit=commit[:8], branch=branch, is_dirty=is_dirty)

    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    finally:
        os.chdir(original_cwd)


def get_repository_name(project_path: str = ".") -> str:
    """Get repository name from Git remote or directory name."""
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
            match = re.search(r'[/:]([^/]+?)(?:\.git)?$', remote_url)
            if match:
                return match.group(1).lower()
    except Exception:
        pass

    # Fallback to directory name
    return os.path.basename(os.path.abspath(project_path)).lower()


def load_classifier_metadata(project_path: str) -> ClassifierMetadata:
    """Load classifier metadata from mlserver.yaml or classifier.yaml file."""
    # Try mlserver.yaml first (unified config)
    mlserver_file = Path(project_path) / "mlserver.yaml"
    if mlserver_file.exists():
        with open(mlserver_file, 'r') as f:
            full_config = yaml.safe_load(f)
            # Extract classifier metadata from unified config
            if 'classifier' in full_config:
                # mlserver.yaml has the metadata under 'classifier' key
                metadata_dict = {
                    'classifier': full_config.get('classifier', {}),
                    'model': full_config.get('model', {}),
                    'api': full_config.get('api', {}),
                    'build': full_config.get('build', {})
                }
                return ClassifierMetadata.model_validate(metadata_dict)

    # Fall back to classifier.yaml for backward compatibility
    classifier_file = Path(project_path) / "classifier.yaml"
    if classifier_file.exists():
        with open(classifier_file, 'r') as f:
            data = yaml.safe_load(f)
        return ClassifierMetadata.model_validate(data)

    # If neither exists, raise error
    raise FileNotFoundError(f"Neither mlserver.yaml nor classifier.yaml found in {project_path}")


def save_classifier_metadata(metadata: ClassifierMetadata, project_path: str):
    """Save classifier metadata to classifier.yaml file."""
    classifier_file = Path(project_path) / "classifier.yaml"

    with open(classifier_file, 'w') as f:
        yaml.dump(metadata.model_dump(exclude_unset=True), f, default_flow_style=False, sort_keys=False)


def generate_container_tags(metadata: ClassifierMetadata, git_info: Optional[GitInfo] = None,
                          predictor_class: Optional[str] = None, project_path: str = ".",
                          classifier_name: Optional[str] = None) -> list[str]:
    """Generate container tags for the classifier using hierarchical naming."""
    # Use the repository/directory name as the base
    repository = get_repository_name(project_path)

    # For multi-classifier setups, use <repo>/<classifier>:version format
    if classifier_name:
        # Version should already be from git tag (e.g., "0.1.0")
        version = metadata.classifier.version

        # Image name includes classifier: repo/classifier
        image_name = f"{repository}/{classifier_name}"

        # Handle missing git tag case
        if version == "missing-git-tag":
            tags = [
                f"{image_name}:latest",  # Latest for this specific classifier
                f"{image_name}:untagged",  # Clear indicator that tagging is needed
            ]

            if git_info and git_info.commit:
                # Add commit hash for identification
                tags.append(f"{image_name}:untagged-{git_info.commit[:7]}")
        else:
            tags = [
                f"{image_name}:latest",  # Latest for this specific classifier
                f"{image_name}:v{version}",  # Version tag
            ]

            if git_info and git_info.commit:
                # Add commit-based tag for exact reproducibility
                tags.append(f"{image_name}:v{version}-{git_info.commit[:7]}")
    else:
        # Single classifier - simpler naming
        version = metadata.classifier.version

        tags = [
            f"{repository}:latest",
            f"{repository}:v{version}",
        ]

        if git_info and git_info.commit:
            tags.append(f"{repository}:v{version}-{git_info.commit[:7]}")

    return tags


def validate_version_consistency(metadata: ClassifierMetadata, project_path: str) -> Dict[str, str]:
    """Validate version consistency across project files."""
    issues = {}

    # Check git tag consistency
    git_info = get_git_info(project_path)
    if git_info and git_info.tag:
        expected_tag = f"v{metadata.classifier.version}"
        if git_info.tag != expected_tag:
            issues['git_tag'] = f"Git tag '{git_info.tag}' doesn't match classifier version 'v{metadata.classifier.version}'"

    # Check if working directory is dirty
    if git_info and git_info.is_dirty:
        issues['git_dirty'] = "Working directory has uncommitted changes"

    return issues


def get_version_info(project_path: str = ".") -> Dict[str, Any]:
    """Get comprehensive version information for a classifier project."""
    try:
        # Try to load from unified config first
        metadata = None
        config_source = None

        # Check for unified config (mlserver.yaml)
        mlserver_config_path = os.path.join(project_path, "mlserver.yaml")
        if os.path.exists(mlserver_config_path):
            try:
                from .config import AppConfig
                import yaml

                with open(mlserver_config_path, 'r') as f:
                    raw_config = yaml.safe_load(f)

                config = AppConfig.model_validate(raw_config)
                if config.classifier:
                    if isinstance(config.classifier, dict):
                        metadata = ClassifierMetadata.model_validate({
                            "classifier": config.classifier,
                            "model": config.model or {},
                            "api": config.api.model_dump() if config.api else {}
                        })
                    else:
                        metadata = config.classifier
                    config_source = "mlserver.yaml"
            except Exception:
                pass

        # Fall back to classifier.yaml
        if metadata is None:
            metadata = load_classifier_metadata(project_path)
            config_source = "classifier.yaml"

        git_info = get_git_info(project_path)
        issues = validate_version_consistency(metadata, project_path)

        return {
            "classifier": metadata.classifier.model_dump(),
            "model": metadata.model.model_dump(),
            "api": metadata.api.model_dump(),
            "git": git_info.__dict__ if git_info else None,
            "container_tags": generate_container_tags(metadata, git_info),
            "validation_issues": issues,
            "timestamp": datetime.now().isoformat(),
            "config_source": config_source
        }

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to get version info: {str(e)}"}