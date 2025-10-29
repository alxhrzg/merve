"""Extended config validation tests to improve coverage."""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from pydantic import ValidationError

from mlserver.config import (
    AppConfig, ServerConfig, PredictorConfig, ApiConfig,
    ObservabilityConfig, CORSConfig, BuildConfig
)


class TestAppConfigValidation:
    """Test AppConfig validation and methods."""

    def test_app_config_minimal(self):
        """Test AppConfig with minimal required fields."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.observability.metrics is True

    def test_app_config_full(self):
        """Test AppConfig with all optional fields."""
        config = AppConfig(
            server=ServerConfig(host="127.0.0.1", port=9000),
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor",
                init_kwargs={"param1": "value1"}
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig(
                adapter="records",
                feature_order=["feature1", "feature2"]
            ),
            observability=ObservabilityConfig(
                metrics=False,
                structured_logging=False
            )
        )
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000
        assert config.predictor.init_kwargs["param1"] == "value1"
        assert config.api.adapter == "records"
        assert config.observability.metrics is False

    def test_unified_config_fields(self):
        """Test unified config format fields."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "TestClassifier", "version": "1.0.0"},
            model={"version": "1.0.0", "type": "sklearn"},
            api=ApiConfig(version="v1"),
            build=BuildConfig(include_files=["model.pkl"])
        )
        assert config.classifier["name"] == "TestClassifier"
        assert config.model["version"] == "1.0.0"
        assert config.api.version == "v1"
        assert config.build.include_files == ["model.pkl"]

    def test_set_project_path(self):
        """Test set_project_path method."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        config.set_project_path("/test/path")
        assert config.project_path_internal == "/test/path"

    def test_get_project_path(self):
        """Test project_path property."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        config.set_project_path("/test/path")
        assert config.project_path == "/test/path"

    def test_get_project_path_default(self):
        """Test project_path property with None value."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        assert config.project_path is None

    def test_get_api_title(self):
        """Test get_api_title method."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        assert config.get_api_title() == "Test Classifier API v1.0.0"

    def test_get_base_path(self):
        """Test get_base_path method."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig(version="v2")
        )
        assert config.get_base_path() == "/v2/test-classifier"

    def test_is_endpoint_enabled(self):
        """Test is_endpoint_enabled method."""
        config = AppConfig(
            predictor=PredictorConfig(
                module="test.module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig(
                endpoints={
                    "predict": True,
                    "batch_predict": False,
                    "predict_proba": True
                }
            )
        )
        assert config.is_endpoint_enabled("predict") is True
        assert config.is_endpoint_enabled("batch_predict") is False
        assert config.is_endpoint_enabled("predict_proba") is True
        assert config.is_endpoint_enabled("nonexistent") is False


class TestApiConfigValidation:
    """Test ApiConfig validation."""

    def test_api_config_defaults(self):
        """Test ApiConfig default values."""
        config = ApiConfig()
        assert config.version == "v1"
        assert config.adapter == "records"
        assert config.feature_order is None
        assert config.thread_safe_predict is False
        assert config.endpoints["predict"] is True
        # batch_predict removed - /predict handles batches
        assert config.endpoints["predict_proba"] is True

    def test_api_config_with_feature_order(self):
        """Test ApiConfig with feature order."""
        config = ApiConfig(
            version="v2",
            adapter="ndarray",
            feature_order=["age", "income", "education"],
            thread_safe_predict=True,
            endpoints={
                "predict": True,
                "batch_predict": False,
                "predict_proba": True
            }
        )
        assert config.version == "v2"
        assert config.adapter == "ndarray"
        assert config.feature_order == ["age", "income", "education"]
        assert config.thread_safe_predict is True
        assert config.endpoints["predict"] is True
        assert config.endpoints["batch_predict"] is False
        assert config.endpoints["predict_proba"] is True


class TestObservabilityConfigValidation:
    """Test ObservabilityConfig validation and defaults."""

    def test_observability_defaults(self):
        """Test ObservabilityConfig default values."""
        config = ObservabilityConfig()
        assert config.metrics is True
        assert config.metrics_endpoint == "/metrics"
        assert config.structured_logging is True
        assert config.log_payloads is False
        assert config.correlation_ids is True

    def test_observability_custom_values(self):
        """Test ObservabilityConfig with custom values."""
        config = ObservabilityConfig(
            metrics=False,
            metrics_endpoint="/custom-metrics",
            structured_logging=False,
            log_payloads=True,
            correlation_ids=False
        )
        assert config.metrics is False
        assert config.metrics_endpoint == "/custom-metrics"
        assert config.structured_logging is False
        assert config.log_payloads is True
        assert config.correlation_ids is False


class TestPredictorConfigValidation:
    """Test PredictorConfig validation."""

    def test_predictor_config_minimal(self):
        """Test PredictorConfig with minimal required fields."""
        config = PredictorConfig(
            module="test.module",
            class_name="TestPredictor"
        )
        assert config.module == "test.module"
        assert config.class_name == "TestPredictor"
        assert config.init_kwargs == {}

    def test_predictor_config_with_kwargs(self):
        """Test PredictorConfig with init_kwargs."""
        init_kwargs = {
            "model_path": "/path/to/model.pkl",
            "n_estimators": 100,
            "random_state": 42
        }
        config = PredictorConfig(
            module="sklearn.ensemble",
            class_name="RandomForestClassifier",
            init_kwargs=init_kwargs
        )
        assert config.module == "sklearn.ensemble"
        assert config.class_name == "RandomForestClassifier"
        assert config.init_kwargs == init_kwargs
        assert config.init_kwargs["model_path"] == "/path/to/model.pkl"
        assert config.init_kwargs["n_estimators"] == 100

    def test_predictor_config_empty_strings(self):
        """Test PredictorConfig validation with empty strings."""
        with pytest.raises(ValidationError):
            PredictorConfig(module="", class_name="TestPredictor")

        with pytest.raises(ValidationError):
            PredictorConfig(module="test.module", class_name="")


class TestConfigSchemaModels:
    """Test additional config schema models."""

    def test_build_config(self):
        """Test BuildConfig model."""
        config = BuildConfig(
            registry="docker.io/myregistry",
            tag_prefix="ml-model",
            include_files=["model.pkl", "preprocessor.pkl"],
            exclude_patterns=["*.tmp", "test_*"]
        )
        assert config.registry == "docker.io/myregistry"
        assert config.tag_prefix == "ml-model"
        assert config.include_files == ["model.pkl", "preprocessor.pkl"]
        assert config.exclude_patterns == ["*.tmp", "test_*"]

    def test_build_config_defaults(self):
        """Test BuildConfig with default values."""
        config = BuildConfig()
        assert config.registry is None
        assert config.tag_prefix is None
        assert config.include_files is None
        assert config.exclude_patterns is None

    def test_cors_config(self):
        """Test CORSConfig model."""
        config = CORSConfig(
            allow_origins=["http://localhost:3000", "https://example.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type", "Authorization"]
        )
        assert config.allow_origins == ["http://localhost:3000", "https://example.com"]
        assert config.allow_credentials is True
        assert config.allow_methods == ["GET", "POST", "PUT"]
        assert config.allow_headers == ["Content-Type", "Authorization"]


class TestConfigValidationEdgeCases:
    """Test edge cases in config validation."""

    def test_server_config_validation_edge_cases(self):
        """Test ServerConfig validation edge cases."""
        # Test boundary values
        config = ServerConfig(port=1, workers=1)
        assert config.port == 1
        assert config.workers == 1

        # Test very high but valid values
        config = ServerConfig(port=65535, workers=100)
        assert config.port == 65535
        assert config.workers == 100

    def test_empty_init_kwargs(self):
        """Test PredictorConfig with explicitly empty init_kwargs."""
        config = PredictorConfig(
            module="test.module",
            class_name="TestPredictor",
            init_kwargs={}
        )
        assert config.init_kwargs == {}

    def test_complex_init_kwargs(self):
        """Test PredictorConfig with complex init_kwargs."""
        complex_kwargs = {
            "nested_dict": {"key1": "value1", "key2": 42},
            "list_param": [1, 2, 3, 4, 5],
            "boolean_param": True,
            "none_param": None,
            "float_param": 3.14159
        }
        config = PredictorConfig(
            module="test.module",
            class_name="TestPredictor",
            init_kwargs=complex_kwargs
        )
        assert config.init_kwargs["nested_dict"]["key1"] == "value1"
        assert config.init_kwargs["list_param"] == [1, 2, 3, 4, 5]
        assert config.init_kwargs["boolean_param"] is True
        assert config.init_kwargs["none_param"] is None
        assert config.init_kwargs["float_param"] == 3.14159

    def test_app_config_required_fields(self):
        """Test AppConfig validation with missing required fields."""
        # Missing predictor
        with pytest.raises(ValidationError):
            AppConfig(
                classifier={"name": "test", "version": "1.0.0"},
                api=ApiConfig()
            )

        # Missing classifier
        with pytest.raises(ValidationError):
            AppConfig(
                predictor=PredictorConfig(
                    module="test.module",
                    class_name="TestPredictor"
                ),
                api=ApiConfig()
            )

        # Missing api
        with pytest.raises(ValidationError):
            AppConfig(
                predictor=PredictorConfig(
                    module="test.module",
                    class_name="TestPredictor"
                ),
                classifier={"name": "test", "version": "1.0.0"}
            )