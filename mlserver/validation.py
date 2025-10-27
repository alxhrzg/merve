"""
Modular validation system for MLServer projects.

This module provides pluggable validators that can be used at different
stages of the MLServer workflow (init, tag, build, etc.).
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    details: dict = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}


class Validator:
    """Base class for validators."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def validate(self, **kwargs) -> ValidationResult:
        """
        Run the validation check.

        Args:
            **kwargs: Context-specific parameters for validation

        Returns:
            ValidationResult indicating success/failure
        """
        raise NotImplementedError("Subclasses must implement validate()")


class ProjectInitializedValidator(Validator):
    """Validates that a project has been properly initialized with mlserver init."""

    def __init__(self):
        super().__init__(
            name="project_initialized",
            description="Verify all required project files exist"
        )

    def validate(self, project_path: str = ".", classifier_name: Optional[str] = None, **kwargs) -> ValidationResult:
        """
        Check if all required files exist for a classifier project.

        Args:
            project_path: Path to project
            classifier_name: Name of classifier (for specific checks)

        Returns:
            ValidationResult with missing files if any
        """
        from .init_project import check_project_files

        files_ok, missing_files = check_project_files(project_path, classifier_name)

        if files_ok:
            return ValidationResult(passed=True)

        error_msg = "Project not properly initialized - required files are missing"
        details = {
            "missing_files": missing_files,
            "solution": "Run 'mlserver init' to create all required files"
        }

        return ValidationResult(
            passed=False,
            error_message=error_msg,
            details=details
        )


class GitWorkingDirectoryCleanValidator(Validator):
    """Validates that git working directory has no uncommitted changes."""

    def __init__(self):
        super().__init__(
            name="git_working_directory_clean",
            description="Verify no uncommitted changes in git"
        )

    def validate(self, project_path: str = ".", **kwargs) -> ValidationResult:
        """
        Check if git working directory is clean.

        Args:
            project_path: Path to project

        Returns:
            ValidationResult indicating if working directory is clean
        """
        from .version_control import GitVersionManager

        try:
            git_mgr = GitVersionManager(project_path)
            is_clean, error_msg = git_mgr.check_working_directory_clean()

            if is_clean:
                return ValidationResult(passed=True)

            details = {
                "solution": "Commit your changes first with: git add . && git commit -m 'message'"
            }

            return ValidationResult(
                passed=False,
                error_message=error_msg,
                details=details
            )
        except Exception as e:
            return ValidationResult(
                passed=False,
                error_message=f"Failed to check git status: {str(e)}"
            )


class GitRepositoryExistsValidator(Validator):
    """Validates that the project is a git repository."""

    def __init__(self):
        super().__init__(
            name="git_repository_exists",
            description="Verify project is a git repository"
        )

    def validate(self, project_path: str = ".", **kwargs) -> ValidationResult:
        """
        Check if project is a git repository.

        Args:
            project_path: Path to project

        Returns:
            ValidationResult indicating if .git directory exists
        """
        git_dir = Path(project_path) / ".git"

        if git_dir.exists():
            return ValidationResult(passed=True)

        details = {
            "solution": "Initialize git repository with: git init"
        }

        return ValidationResult(
            passed=False,
            error_message="Not a git repository",
            details=details
        )


class ConfigurationValidValidator(Validator):
    """Validates that mlserver.yaml is valid and can be parsed."""

    def __init__(self):
        super().__init__(
            name="configuration_valid",
            description="Verify mlserver.yaml is valid"
        )

    def validate(self, project_path: str = ".", **kwargs) -> ValidationResult:
        """
        Check if mlserver.yaml exists and is valid.

        Args:
            project_path: Path to project

        Returns:
            ValidationResult indicating if config is valid
        """
        mlserver_yaml = Path(project_path) / "mlserver.yaml"

        if not mlserver_yaml.exists():
            return ValidationResult(
                passed=False,
                error_message="mlserver.yaml not found",
                details={"solution": "Run 'mlserver init' to create configuration"}
            )

        try:
            from .config import AppConfig
            import yaml

            with open(mlserver_yaml, 'r') as f:
                raw_config = yaml.safe_load(f)

            AppConfig.model_validate(raw_config)

            return ValidationResult(passed=True)

        except Exception as e:
            return ValidationResult(
                passed=False,
                error_message=f"Invalid mlserver.yaml: {str(e)}",
                details={"solution": "Check your mlserver.yaml for syntax errors"}
            )


class GitHubActionsConfiguredValidator(Validator):
    """Validates that GitHub Actions workflow is configured."""

    def __init__(self):
        super().__init__(
            name="github_actions_configured",
            description="Verify GitHub Actions workflow exists"
        )

    def validate(self, project_path: str = ".", **kwargs) -> ValidationResult:
        """
        Check if GitHub Actions workflow file exists.

        Args:
            project_path: Path to project

        Returns:
            ValidationResult indicating if workflow exists
        """
        from .github_actions import check_github_actions_setup

        if check_github_actions_setup(project_path):
            return ValidationResult(passed=True)

        # This is a warning, not an error - workflow is optional
        return ValidationResult(
            passed=True,  # Don't fail validation
            warnings=["GitHub Actions workflow not configured"],
            details={
                "solution": "Run 'mlserver init-github' to add CI/CD automation"
            }
        )


class ValidationSuite:
    """A collection of validators that can be run together."""

    def __init__(self, name: str, validators: List[Validator]):
        """
        Initialize validation suite.

        Args:
            name: Name of this validation suite
            validators: List of validators to run
        """
        self.name = name
        self.validators = validators

    def validate(self, **kwargs) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all validators in the suite.

        Args:
            **kwargs: Context parameters passed to all validators

        Returns:
            Tuple of (all_passed, list_of_results)
        """
        results = []
        all_passed = True

        for validator in self.validators:
            result = validator.validate(**kwargs)
            results.append(result)

            if not result.passed:
                all_passed = False

        return all_passed, results

    def add_validator(self, validator: Validator):
        """Add a validator to this suite."""
        self.validators.append(validator)

    def remove_validator(self, validator_name: str):
        """Remove a validator by name."""
        self.validators = [v for v in self.validators if v.name != validator_name]


# Pre-defined validation suites for common workflows

def get_tag_validation_suite() -> ValidationSuite:
    """Get validation suite for tagging workflow."""
    return ValidationSuite(
        name="tag_validation",
        validators=[
            GitRepositoryExistsValidator(),
            ProjectInitializedValidator(),
            ConfigurationValidValidator(),
            GitWorkingDirectoryCleanValidator(),
        ]
    )


def get_build_validation_suite() -> ValidationSuite:
    """Get validation suite for build workflow."""
    return ValidationSuite(
        name="build_validation",
        validators=[
            ProjectInitializedValidator(),
            ConfigurationValidValidator(),
        ]
    )


def get_init_validation_suite() -> ValidationSuite:
    """Get validation suite for init workflow (pre-init checks)."""
    return ValidationSuite(
        name="init_validation",
        validators=[
            GitRepositoryExistsValidator(),
        ]
    )


def get_deploy_validation_suite() -> ValidationSuite:
    """Get validation suite for deployment workflow."""
    return ValidationSuite(
        name="deploy_validation",
        validators=[
            GitRepositoryExistsValidator(),
            ProjectInitializedValidator(),
            ConfigurationValidValidator(),
            GitWorkingDirectoryCleanValidator(),
            GitHubActionsConfiguredValidator(),
        ]
    )
