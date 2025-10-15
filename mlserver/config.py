
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json
import logging
from pydantic import BaseModel, Field, field_validator

from .version import ClassifierMetadata, load_classifier_metadata
from .settings import get_settings

logger = logging.getLogger(__name__)



class CORSConfig(BaseModel):
    # Security: Default to no CORS instead of wildcard. Require explicit configuration for production.
    allow_origins: List[str] = Field(default_factory=list, description="Allowed origins (empty = CORS disabled)")
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST"], description="Allowed HTTP methods")
    allow_headers: List[str] = Field(default_factory=lambda: ["Content-Type"], description="Allowed headers")
    allow_credentials: bool = Field(default=False, description="Allow credentials in CORS requests")


class LoggerConfig(BaseModel):
    """Logger configuration for structured logging."""
    timestamp: bool = Field(default=False, description="Include timestamps in logs (default: false for container environments)")
    structured: bool = Field(default=True, description="Use structured JSON logging")
    show_tasks: bool = Field(default=False, description="Show async task names (Task-1, Task-2) in logs")
    format: Optional[str] = Field(default=None, description="Custom log format string (overrides other settings)")


class ServerConfig(BaseModel):
    title: str = "ML Server"
    host: str = Field(default_factory=lambda: get_settings().server.default_host)
    port: int = Field(default_factory=lambda: get_settings().server.default_port)
    log_level: str = Field(default_factory=lambda: get_settings().server.default_log_level)
    workers: int = Field(default_factory=lambda: get_settings().server.default_workers if hasattr(get_settings().server, 'default_workers') else 1)
    cors: Optional[CORSConfig] = None
    logger: Optional[LoggerConfig] = Field(default=None, description="Logger configuration")

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError('port must be between 1 and 65535')
        return v

    @field_validator('workers')
    @classmethod
    def validate_workers(cls, v):
        if v < 1:
            raise ValueError('workers must be at least 1')
        return v


class PredictorConfig(BaseModel):
    module: str  # e.g., "examples.predictor_catboost"
    class_name: str  # e.g., "CatBoostPredictor"
    init_kwargs: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('module', 'class_name')
    @classmethod
    def validate_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('field cannot be empty')
        return v


class ObservabilityConfig(BaseModel):
    metrics: bool = Field(default=True, description="Enable Prometheus metrics collection")
    metrics_endpoint: str = Field(default="/metrics", description="Metrics endpoint path")
    structured_logging: bool = Field(default=True, description="Enable structured JSON logging")
    log_payloads: bool = Field(default=False, description="Log request/response payloads")
    correlation_ids: bool = Field(default=True, description="Generate correlation IDs for request tracing")




class ApiConfig(BaseModel):
    """Unified API configuration from mlserver.yaml"""
    version: str = Field(default="v1", description="API version for metadata tracking")
    endpoints: Dict[str, bool] = Field(
        default_factory=lambda: {
            "predict": True,
            # Note: batch_predict removed - /predict handles both single and batch
            "predict_proba": True
        },
        description="Enabled endpoints"
    )
    adapter: str = Field(default="records", description="records|ndarray|auto")
    feature_order: Optional[Union[List[str], str]] = None  # Can be List[str] or str (file path)
    _resolved_feature_order: Optional[List[str]] = None  # Cached resolved value
    thread_safe_predict: bool = False
    max_concurrent_predictions: int = Field(
        default=1,
        description="Maximum concurrent predictions (1 for single model protection in K8s)",
        ge=1
    )
    # Response format configuration
    response_format: str = Field(
        default="standard",
        description="Response format: 'standard' (default), 'custom' (flexible), or 'passthrough' (unmodified)"
    )
    response_validation: bool = Field(
        default=True,
        description="Enable response validation (can be disabled for complex custom responses)"
    )
    extract_values: bool = Field(
        default=False,
        description="For dict responses, extract values into predictions list"
    )

    def get_resolved_feature_order(self, base_path: Optional[Path] = None) -> Optional[List[str]]:
        """Resolve feature_order, loading from file if it's a path.

        Args:
            base_path: Base directory to resolve relative paths from

        Returns:
            List of feature names or None
        """
        # Return cached value if already resolved
        if self._resolved_feature_order is not None:
            return self._resolved_feature_order

        if self.feature_order is None:
            return None

        # If it's already a list, return as-is
        if isinstance(self.feature_order, list):
            self._resolved_feature_order = self.feature_order
            return self.feature_order

        # If it's a string, try to load from file
        if isinstance(self.feature_order, str):
            try:
                # Resolve path relative to base_path if provided
                if base_path:
                    file_path = base_path / self.feature_order
                else:
                    file_path = Path(self.feature_order)

                # Check if file exists
                if not file_path.exists():
                    logger.warning(f"Feature order file not found: {file_path}")
                    return None

                # Load JSON file
                with open(file_path, 'r') as f:
                    features = json.load(f)

                # Validate it's a list of strings
                if not isinstance(features, list):
                    raise ValueError(f"Feature order file must contain a JSON array, got {type(features)}")

                logger.info(f"Loaded {len(features)} features from {file_path}")
                self._resolved_feature_order = features
                return features

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse feature order file as JSON: {e}")
                return None
            except Exception as e:
                logger.error(f"Failed to load feature order from file: {e}")
                return None

        logger.warning(f"Unexpected feature_order type: {type(self.feature_order)}")
        return None


class BuildConfig(BaseModel):
    """Container build configuration"""
    base_image: str = Field(default_factory=lambda: get_settings().container.default_base_image, description="Base Docker image")
    registry: Optional[str] = Field(default=None, description="Container registry URL")
    tag_prefix: Optional[str] = Field(default=None, description="Tag prefix for container names")
    include_files: Optional[List[str]] = Field(default=None, description="Explicit files to include")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="Patterns to exclude")


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    predictor: PredictorConfig
    observability: ObservabilityConfig = ObservabilityConfig()

    # Modern format (mlserver.yaml)
    classifier: Dict[str, Any]  # Required classifier metadata
    model: Optional[Dict[str, Any]] = Field(default=None)  # Model metadata dict
    api: ApiConfig
    build: Optional[BuildConfig] = Field(default=None)

    # Internal state
    classifier_metadata_internal: Optional[ClassifierMetadata] = Field(default=None, exclude=True)
    project_path_internal: Optional[str] = Field(default=None, exclude=True)

    def model_post_init(self, __context) -> None:
        """Post-initialization processing for modern config format."""
        # Convert classifier dict to ClassifierMetadata format
        try:
            from .version import ClassifierMetadata
            self.classifier_metadata_internal = ClassifierMetadata.model_validate({
                "classifier": self.classifier,
                "model": self.model or {},
                "api": self.api.model_dump()
            })
        except Exception:
            # If validation fails, skip creating classifier metadata
            # This allows tests and minimal configs to work without full metadata
            self.classifier_metadata_internal = None

    def set_project_path(self, project_path: str):
        """Set project path and load classifier metadata if available."""
        self.project_path_internal = project_path
        # Check for mlserver.yaml
        mlserver_file = Path(project_path) / "mlserver.yaml"

        if mlserver_file.exists():
            try:
                self.classifier_metadata_internal = load_classifier_metadata(project_path)
            except Exception:
                # If config file exists but is invalid, silently ignore
                self.classifier_metadata_internal = None

    @property
    def classifier_metadata(self) -> Optional[ClassifierMetadata]:
        """Get classifier metadata if available."""
        return self.classifier_metadata_internal

    @property
    def project_path(self) -> Optional[str]:
        """Get project path."""
        return self.project_path_internal

    def _format_api_title(self, name: str, version: str) -> str:
        """Format API title from name and version."""
        formatted_name = name.replace('-', ' ').title()
        return f"{formatted_name} API v{version}"

    def get_api_title(self) -> str:
        """Get API title with version information."""
        name = self.classifier.get('name', 'ML Classifier')
        version = self.classifier.get('version', '1.0.0')
        return self._format_api_title(name, version)

    def get_base_path(self) -> str:
        """Get base API path for endpoints."""
        # Unified interface - no version or classifier name in URL
        # Each deployment gets its own unique base URL anyway
        return ""

    def is_endpoint_enabled(self, endpoint: str) -> bool:
        """Check if a specific endpoint is enabled."""
        return self.api.endpoints.get(endpoint, False)
