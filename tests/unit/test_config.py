import pytest
from pydantic import ValidationError

from mlserver.config import (
    AppConfig, ServerConfig, PredictorConfig, ApiConfig,
    ObservabilityConfig, CORSConfig
)


class TestServerConfig:
    """Test ServerConfig validation and defaults"""

    def test_default_values(self):
        config = ServerConfig()
        assert config.title == "ML Server"
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.log_level == "INFO"
        assert config.workers == 1
        assert config.cors is None

    def test_custom_values(self):
        config = ServerConfig(
            title="Custom Server",
            host="127.0.0.1",
            port=9000,
            log_level="DEBUG",
            workers=4
        )
        assert config.title == "Custom Server"
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.log_level == "DEBUG"
        assert config.workers == 4

    def test_cors_config(self):
        cors_config = CORSConfig(
            allow_origins=["http://localhost:3000"],
            allow_credentials=True
        )
        config = ServerConfig(cors=cors_config)
        assert config.cors.allow_origins == ["http://localhost:3000"]
        assert config.cors.allow_credentials is True

    def test_invalid_port(self):
        with pytest.raises(ValidationError):
            ServerConfig(port=-1)

    def test_invalid_workers(self):
        with pytest.raises(ValidationError):
            ServerConfig(workers=0)


class TestCORSConfig:
    """Test CORS configuration"""

    def test_default_values(self):
        config = CORSConfig()
        # Security fix: Default to no CORS instead of wildcard
        assert config.allow_origins == []
        assert config.allow_methods == ["GET", "POST"]
        assert config.allow_headers == ["Content-Type"]
        assert config.allow_credentials is False

    def test_custom_values(self):
        config = CORSConfig(
            allow_origins=["http://localhost:3000", "https://app.example.com"],
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=True
        )
        assert config.allow_origins == ["http://localhost:3000", "https://app.example.com"]
        assert config.allow_methods == ["GET", "POST"]
        assert config.allow_headers == ["Authorization", "Content-Type"]
        assert config.allow_credentials is True


class TestPredictorConfig:
    """Test PredictorConfig validation"""

    def test_minimal_config(self):
        config = PredictorConfig(
            module="my_module",
            class_name="MyPredictor"
        )
        assert config.module == "my_module"
        assert config.class_name == "MyPredictor"
        assert config.init_kwargs == {}

    def test_with_init_kwargs(self):
        init_kwargs = {
            "model_path": "/path/to/model.pkl",
            "batch_size": 32,
            "device": "cuda"
        }
        config = PredictorConfig(
            module="my_module",
            class_name="MyPredictor",
            init_kwargs=init_kwargs
        )
        assert config.init_kwargs == init_kwargs

    def test_missing_module(self):
        with pytest.raises(ValidationError):
            PredictorConfig(class_name="MyPredictor")

    def test_missing_class_name(self):
        with pytest.raises(ValidationError):
            PredictorConfig(module="my_module")


class TestApiConfig:
    """Test ApiConfig validation and defaults"""

    def test_default_values(self):
        config = ApiConfig()
        assert config.version == "v1"
        assert config.adapter == "records"
        assert config.feature_order is None
        assert config.endpoints["predict"] is True
        assert config.endpoints["batch_predict"] is True
        assert config.endpoints["predict_proba"] is True
        assert config.thread_safe_predict is False

    def test_custom_values(self):
        feature_order = ["feature1", "feature2", "feature3"]
        config = ApiConfig(
            version="v2",
            adapter="ndarray",
            feature_order=feature_order,
            endpoints={
                "predict": True,
                "batch_predict": False,
                "predict_proba": False
            },
            thread_safe_predict=True
        )
        assert config.version == "v2"
        assert config.adapter == "ndarray"
        assert config.feature_order == feature_order
        assert config.endpoints["predict"] is True
        assert config.endpoints["batch_predict"] is False
        assert config.endpoints["predict_proba"] is False
        assert config.thread_safe_predict is True


class TestObservabilityConfig:
    """Test ObservabilityConfig validation and defaults"""

    def test_default_values(self):
        config = ObservabilityConfig()
        assert config.metrics is True
        assert config.metrics_endpoint == "/metrics"
        assert config.structured_logging is True
        assert config.log_payloads is False
        assert config.correlation_ids is True

    def test_custom_values(self):
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

    def test_custom_metrics_endpoint(self):
        config = ObservabilityConfig(metrics_endpoint="/api/v1/metrics")
        assert config.metrics_endpoint == "/api/v1/metrics"


class TestAppConfig:
    """Test main AppConfig validation"""

    def test_minimal_config(self):
        config = AppConfig(
            predictor=PredictorConfig(
                module="test_module",
                class_name="TestPredictor"
            ),
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=ApiConfig()
        )
        # Should use defaults for server, observability
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.predictor, PredictorConfig)
        assert isinstance(config.api, ApiConfig)
        assert isinstance(config.observability, ObservabilityConfig)

    def test_full_config(self):
        server_config = ServerConfig(title="Test Server", port=9000)
        predictor_config = PredictorConfig(
            module="test_module",
            class_name="TestPredictor",
            init_kwargs={"param": "value"}
        )
        api_config = ApiConfig(
            adapter="ndarray",
            feature_order=["f1", "f2"]
        )
        observability_config = ObservabilityConfig(
            metrics=False,
            structured_logging=False
        )

        config = AppConfig(
            server=server_config,
            predictor=predictor_config,
            classifier={"name": "test-classifier", "version": "1.0.0"},
            api=api_config,
            observability=observability_config
        )

        assert config.server.title == "Test Server"
        assert config.server.port == 9000
        assert config.predictor.module == "test_module"
        assert config.api.adapter == "ndarray"
        assert config.observability.metrics is False

    def test_missing_predictor(self):
        with pytest.raises(ValidationError):
            AppConfig()

    def test_missing_classifier(self):
        with pytest.raises(ValidationError):
            AppConfig(
                predictor=PredictorConfig(
                    module="test",
                    class_name="Test"
                )
            )

    def test_valid_adapters(self):
        for adapter in ["records", "ndarray", "auto"]:
            config = AppConfig(
                predictor=PredictorConfig(
                    module="test",
                    class_name="Test"
                ),
                classifier={"name": "test-classifier", "version": "1.0.0"},
                api=ApiConfig(adapter=adapter)
            )
            assert config.api.adapter == adapter


class TestConfigFromDict:
    """Test configuration creation from dictionary (YAML-like)"""

    def test_from_dict_basic(self):
        config_dict = {
            "server": {
                "title": "Test API",
                "port": 8080
            },
            "predictor": {
                "module": "my_predictor",
                "class_name": "Predictor"
            },
            "classifier": {
                "name": "test-classifier",
                "version": "1.0.0"
            },
            "api": {
                "adapter": "records",
                "endpoints": {
                    "predict": True,
                    "batch_predict": False,
                    "predict_proba": True
                }
            },
            "observability": {
                "metrics": True,
                "structured_logging": False
            }
        }

        config = AppConfig.model_validate(config_dict)
        assert config.server.title == "Test API"
        assert config.server.port == 8080
        assert config.predictor.module == "my_predictor"
        assert config.api.adapter == "records"
        assert config.api.endpoints["batch_predict"] is False
        assert config.observability.metrics is True
        assert config.observability.structured_logging is False

    def test_from_dict_with_defaults(self):
        config_dict = {
            "predictor": {
                "module": "my_predictor",
                "class_name": "Predictor"
            },
            "classifier": {
                "name": "test-classifier",
                "version": "1.0.0"
            },
            "api": {}
        }

        config = AppConfig.model_validate(config_dict)
        # Should fill in defaults
        assert config.server.title == "ML Server"
        assert config.server.port == 8000
        assert config.api.adapter == "records"
        assert config.observability.metrics is True

    def test_from_dict_nested_validation_error(self):
        config_dict = {
            "server": {
                "port": "invalid"  # Should be int
            },
            "predictor": {
                "module": "test",
                "class_name": "Test"
            },
            "classifier": {
                "name": "test-classifier",
                "version": "1.0.0"
            },
            "api": {}
        }

        with pytest.raises(ValidationError) as exc_info:
            AppConfig.model_validate(config_dict)
        assert "port" in str(exc_info.value)

    def test_cors_from_dict(self):
        config_dict = {
            "server": {
                "cors": {
                    "allow_origins": ["http://localhost:3000"],
                    "allow_credentials": True
                }
            },
            "predictor": {
                "module": "test",
                "class_name": "Test"
            },
            "classifier": {
                "name": "test-classifier",
                "version": "1.0.0"
            },
            "api": {}
        }

        config = AppConfig.model_validate(config_dict)
        assert config.server.cors.allow_origins == ["http://localhost:3000"]
        assert config.server.cors.allow_credentials is True