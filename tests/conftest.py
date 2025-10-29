import pytest
import tempfile
import os
import sys
import json
import pickle
from typing import Any, List
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from prometheus_client import REGISTRY, CollectorRegistry

# Ensure project root is on sys.path for proper module imports
project_root = str(Path(__file__).parent.parent.resolve())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mlserver.config import AppConfig, ServerConfig, PredictorConfig, ApiConfig, ObservabilityConfig
from mlserver.server import create_app
from httpx import AsyncClient, ASGITransport


# Mock predictor for testing
class MockPredictor:
    def __init__(self, model_path: str = None, **kwargs):
        self.model_path = model_path
        # Create a simple mock model
        self.model = RandomForestClassifier(n_estimators=3, random_state=42)
        # Train on dummy data
        X_dummy = np.random.random((100, 5))
        y_dummy = np.random.randint(0, 2, 100)
        self.model.fit(X_dummy, y_dummy)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        if X.shape[1] != 5:
            # Pad or truncate to 5 features for consistency
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        if X.shape[1] != 5:
            # Pad or truncate to 5 features for consistency
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict_proba(X)


# Mock predictor with preprocessing
class MockPredictorWithPreprocessing:
    def __init__(self, model_path: str = None, preprocessor_path: str = None,
                 feature_order: List[str] = None, **kwargs):
        self.model_path = model_path
        self.preprocessor_path = preprocessor_path
        self.feature_order = feature_order or ["f1", "f2", "f3", "f4", "f5"]

        # Mock model and preprocessor
        self.model = RandomForestClassifier(n_estimators=3, random_state=42)
        self.preprocessor = StandardScaler()

        # Train on dummy data
        X_dummy = np.random.random((100, 5))
        y_dummy = np.random.randint(0, 2, 100)
        self.preprocessor.fit(X_dummy)
        self.model.fit(self.preprocessor.transform(X_dummy), y_dummy)

    def _as_dataframe(self, X: np.ndarray) -> pd.DataFrame:
        if not isinstance(X, np.ndarray):
            X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return pd.DataFrame(X, columns=self.feature_order[:X.shape[1]])

    def predict(self, X: np.ndarray) -> np.ndarray:
        df = self._as_dataframe(X)
        # Ensure we have the right number of columns
        for col in self.feature_order:
            if col not in df.columns:
                df[col] = 0
        df = df[self.feature_order]
        X_processed = self.preprocessor.transform(df)
        return self.model.predict(X_processed)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        df = self._as_dataframe(X)
        # Ensure we have the right number of columns
        for col in self.feature_order:
            if col not in df.columns:
                df[col] = 0
        df = df[self.feature_order]
        X_processed = self.preprocessor.transform(df)
        return self.model.predict_proba(X_processed)


@pytest.fixture(autouse=True)
def reset_metrics_registry():
    """Reset prometheus metrics registry before each test to avoid conflicts"""
    # Clear the global metrics collector
    from mlserver import metrics
    metrics._metrics_collector = None

    # Clear all collectors from the default registry
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass  # Already unregistered
    yield


@pytest.fixture
def temp_dir():
    """Temporary directory for test artifacts"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_model_artifacts(temp_dir):
    """Create mock model artifacts for testing"""
    # Create mock model
    model = RandomForestClassifier(n_estimators=3, random_state=42)
    X_dummy = np.random.random((100, 5))
    y_dummy = np.random.randint(0, 2, 100)
    model.fit(X_dummy, y_dummy)

    # Create mock preprocessor
    preprocessor = StandardScaler()
    preprocessor.fit(X_dummy)

    # Save artifacts
    model_path = os.path.join(temp_dir, "model.pkl")
    preprocessor_path = os.path.join(temp_dir, "preprocessor.pkl")
    feature_order_path = os.path.join(temp_dir, "feature_order.json")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(preprocessor_path, "wb") as f:
        pickle.dump(preprocessor, f)
    with open(feature_order_path, "w") as f:
        json.dump(["f1", "f2", "f3", "f4", "f5"], f)

    return {
        "model_path": model_path,
        "preprocessor_path": preprocessor_path,
        "feature_order_path": feature_order_path
    }


@pytest.fixture
def basic_config():
    """Basic test configuration"""
    return AppConfig(
        server=ServerConfig(
            title="Test ML Server",
            host="127.0.0.1",
            port=8888,
            workers=1
        ),
        predictor=PredictorConfig(
            module="tests.fixtures.mock_predictor",
            class_name="MockPredictor"
        ),
        classifier={
            "name": "test-classifier",
            "version": "1.0.0",
            "description": "Test classifier for unit tests"
        },
        api=ApiConfig(
            version="v1",
            adapter="auto",  # Use auto adapter to handle both records and ndarray formats
            feature_order=["f1", "f2", "f3", "f4", "f5"],
            thread_safe_predict=False,
            endpoints={
                "predict": True,
                "batch_predict": True,
                "predict_proba": True
            }
        ),
        observability=ObservabilityConfig(
            metrics=True,
            structured_logging=False  # Disable for cleaner test output
        )
    )


@pytest.fixture
def config_with_preprocessing():
    """Configuration with preprocessing"""
    return AppConfig(
        server=ServerConfig(
            title="Test ML Server with Preprocessing",
            host="127.0.0.1",
            port=8889,
            workers=1
        ),
        predictor=PredictorConfig(
            module="tests.fixtures.mock_predictor",
            class_name="MockPredictorWithPreprocessing",
            init_kwargs={
                "feature_order": ["f1", "f2", "f3", "f4", "f5"]
            }
        ),
        classifier={
            "name": "test-classifier-preprocessing",
            "version": "1.0.0",
            "description": "Test classifier with preprocessing"
        },
        api=ApiConfig(
            version="v1",
            adapter="records",
            feature_order=["f1", "f2", "f3", "f4", "f5"],
            thread_safe_predict=False,
            endpoints={
                "predict": True,
                "batch_predict": True,
                "predict_proba": True
            }
        ),
        observability=ObservabilityConfig(
            metrics=True,
            structured_logging=False
        )
    )


@pytest.fixture
def observability_config():
    """Configuration with full observability enabled"""
    return AppConfig(
        server=ServerConfig(title="Test ML Server - Observability"),
        predictor=PredictorConfig(
            module="tests.fixtures.mock_predictor",
            class_name="MockPredictor"
        ),
        classifier={
            "name": "test-classifier-observability",
            "version": "1.0.0",
            "description": "Test classifier for observability"
        },
        api=ApiConfig(
            version="v1",
            adapter="records",
            thread_safe_predict=False,
            endpoints={
                "predict": True,
                "batch_predict": True,
                "predict_proba": True
            }
        ),
        observability=ObservabilityConfig(
            metrics=True,
            structured_logging=True,
            correlation_ids=True,
            log_payloads=True
        )
    )


@pytest.fixture
def test_app(basic_config):
    """Create test FastAPI app"""
    app = create_app(basic_config)
    # Manually initialize state for testing since lifespan may not trigger in test environment
    if not hasattr(app.state, "predictor") or app.state.predictor is None:
        from mlserver.predictor_loader import load_predictor
        from mlserver.server import PredictorWrapper
        from mlserver.metrics import init_metrics

        predictor = load_predictor(
            basic_config.predictor.module,
            basic_config.predictor.class_name,
            basic_config.predictor.init_kwargs,
        )
        predictor_wrapper = PredictorWrapper(
            predictor, thread_safe=basic_config.api.thread_safe_predict
        )
        app.state.predictor = predictor_wrapper

        # Initialize metrics if enabled
        if basic_config.observability.metrics:
            init_metrics(predictor_wrapper.name)

    return app


@pytest.fixture
def test_app_with_preprocessing(config_with_preprocessing):
    """Create test FastAPI app with preprocessing"""
    app = create_app(config_with_preprocessing)
    # Manually initialize state for testing since lifespan may not trigger in test environment
    if not hasattr(app.state, "predictor") or app.state.predictor is None:
        from mlserver.predictor_loader import load_predictor
        from mlserver.server import PredictorWrapper
        from mlserver.metrics import init_metrics

        predictor = load_predictor(
            config_with_preprocessing.predictor.module,
            config_with_preprocessing.predictor.class_name,
            config_with_preprocessing.predictor.init_kwargs,
        )
        predictor_wrapper = PredictorWrapper(
            predictor, thread_safe=config_with_preprocessing.api.thread_safe_predict
        )
        app.state.predictor = predictor_wrapper

        # Initialize metrics if enabled
        if config_with_preprocessing.observability.metrics:
            init_metrics(predictor_wrapper.name)

    return app


@pytest.fixture
def observability_app(observability_config):
    """Create test FastAPI app with observability"""
    app = create_app(observability_config)
    # Manually initialize state for testing since lifespan may not trigger in test environment
    if not hasattr(app.state, "predictor") or app.state.predictor is None:
        from mlserver.predictor_loader import load_predictor
        from mlserver.server import PredictorWrapper
        from mlserver.metrics import init_metrics

        predictor = load_predictor(
            observability_config.predictor.module,
            observability_config.predictor.class_name,
            observability_config.predictor.init_kwargs,
        )
        predictor_wrapper = PredictorWrapper(
            predictor, thread_safe=observability_config.api.thread_safe_predict
        )
        app.state.predictor = predictor_wrapper

        # Initialize metrics if enabled
        if observability_config.observability.metrics:
            init_metrics(predictor_wrapper.name)

    return app


@pytest.fixture
async def async_client(test_app):
    """Async HTTP client for testing"""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def async_client_preprocessing(test_app_with_preprocessing):
    """Async HTTP client for preprocessing tests"""
    async with AsyncClient(transport=ASGITransport(app=test_app_with_preprocessing), base_url="http://test") as client:
        yield client


@pytest.fixture
async def observability_client(observability_app):
    """Async HTTP client for observability tests"""
    async with AsyncClient(transport=ASGITransport(app=observability_app), base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_records_payload():
    """Sample records payload for testing"""
    return {
        "payload": {
            "records": [
                {"f1": 1.0, "f2": 2.0, "f3": 3.0, "f4": 4.0, "f5": 5.0},
                {"f1": 1.5, "f2": 2.5, "f3": 3.5, "f4": 4.5, "f5": 5.5}
            ]
        }
    }


@pytest.fixture
def sample_ndarray_payload():
    """Sample ndarray payload for testing"""
    return {
        "payload": {
            "ndarray": [[1.0, 2.0, 3.0, 4.0, 5.0], [1.5, 2.5, 3.5, 4.5, 5.5]]
        }
    }


@pytest.fixture
def sample_single_record_payload():
    """Sample single record payload for testing"""
    return {
        "payload": {
            "features": {"f1": 1.0, "f2": 2.0, "f3": 3.0, "f4": 4.0, "f5": 5.0}
        }
    }