"""Unit tests for server module components."""
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import Request, Response, HTTPException
from starlette.responses import JSONResponse

from mlserver.server import (
    ObservabilityMiddleware,
    create_app,
    PredictorWrapper,
    _prepare_input_data,
    _track_prediction_metrics,
    _create_predict_handler,
    _create_predict_proba_handler,
    _to_jsonable,
    _tolist2d
)
from mlserver.config import AppConfig, ServerConfig, PredictorConfig, ObservabilityConfig
from mlserver.schemas import PredictRequest
from mlserver.adapters import AdapterError


@pytest.fixture
def mock_config():
    """Create a mock AppConfig with default settings."""
    return AppConfig.model_validate({
        "server": {"host": "127.0.0.1", "port": 8000},
        "predictor": {
            "module": "mlserver.predictors.sklearn",
            "class_name": "SKLearnPredictor",
            "init_kwargs": {"model_path": "model.pkl"}
        },
        "observability": {
            "metrics": True,
            "structured_logging": True,
            "correlation_ids": True
        },
        "classifier": {
            "name": "test-model",
            "version": "1.0.0"
        },
        "api": {
            "version": "v1",
            "adapter": "auto"
        }
    })


@pytest.fixture
def mock_config_minimal():
    """Create a minimal AppConfig with observability disabled."""
    return AppConfig.model_validate({
        "server": {"host": "127.0.0.1", "port": 8000},
        "predictor": {
            "module": "mlserver.predictors.sklearn",
            "class_name": "SKLearnPredictor",
            "init_kwargs": {"model_path": "model.pkl"}
        },
        "observability": {
            "metrics": False,
            "structured_logging": False,
            "correlation_ids": False
        },
        "classifier": {
            "name": "test-model",
            "version": "1.0.0"
        },
        "api": {
            "version": "v1",
            "adapter": "auto"
        }
    })


class TestObservabilityMiddleware:
    """Test the ObservabilityMiddleware class."""

    def test_middleware_init(self, mock_config):
        """Test middleware initialization."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics:
            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            app = Mock()
            middleware = ObservabilityMiddleware(app, mock_config)

            assert middleware.config == mock_config
            assert middleware.metrics == mock_metrics

    def test_middleware_init_no_metrics(self, mock_config_minimal):
        """Test middleware initialization when metrics are disabled."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics:
            mock_get_metrics.return_value = None

            app = Mock()
            middleware = ObservabilityMiddleware(app, mock_config_minimal)

            assert middleware.config == mock_config_minimal
            assert middleware.metrics is None

    @pytest.mark.asyncio
    async def test_middleware_dispatch_full_observability(self, mock_config):
        """Test middleware dispatch with full observability enabled."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics, \
             patch('mlserver.server.set_correlation_id') as mock_set_correlation_id, \
             patch('mlserver.server.log_request') as mock_log_request, \
             patch('mlserver.server.log_response') as mock_log_response:

            # Setup mocks
            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics
            mock_set_correlation_id.return_value = "test-correlation-id"

            # Create middleware
            app = Mock()
            middleware = ObservabilityMiddleware(app, mock_config)

            # Create mock request and response
            mock_request = Mock(spec=Request)
            mock_request.url = Mock()
            mock_request.url.path = "/predict"
            mock_request.method = "POST"

            mock_response = Mock(spec=Response)
            mock_response.status_code = 200

            # Mock call_next
            async def mock_call_next(request):
                return mock_response

            # Execute middleware
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Verify calls
            mock_set_correlation_id.assert_called_once()
            mock_metrics.inc_active_requests.assert_called_once()
            mock_metrics.dec_active_requests.assert_called_once()
            mock_metrics.record_request_duration.assert_called_once()
            mock_log_request.assert_called_once()
            mock_log_response.assert_called_once()

            assert result == mock_response

    @pytest.mark.asyncio
    async def test_middleware_dispatch_minimal_observability(self, mock_config_minimal):
        """Test middleware dispatch with minimal observability."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics, \
             patch('mlserver.server.set_correlation_id') as mock_set_correlation_id, \
             patch('mlserver.server.log_request') as mock_log_request, \
             patch('mlserver.server.log_response') as mock_log_response:

            # Setup mocks
            mock_get_metrics.return_value = None

            # Create middleware
            app = Mock()
            middleware = ObservabilityMiddleware(app, mock_config_minimal)

            # Create mock request and response
            mock_request = Mock(spec=Request)
            mock_response = Mock(spec=Response)
            mock_response.status_code = 200

            # Mock call_next
            async def mock_call_next(request):
                return mock_response

            # Execute middleware
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Verify minimal calls
            mock_set_correlation_id.assert_not_called()
            mock_log_request.assert_not_called()
            mock_log_response.assert_not_called()

            assert result == mock_response

    @pytest.mark.asyncio
    async def test_middleware_dispatch_handles_exceptions(self, mock_config):
        """Test middleware properly handles exceptions."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics:
            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            app = Mock()
            middleware = ObservabilityMiddleware(app, mock_config)

            mock_request = Mock(spec=Request)
            mock_request.url = Mock()
            mock_request.url.path = "/predict"
            mock_request.method = "POST"

            # Mock call_next to raise an exception
            async def mock_call_next(request):
                raise Exception("Test error")

            # Execute middleware and expect exception to propagate
            with pytest.raises(Exception, match="Test error"):
                await middleware.dispatch(mock_request, mock_call_next)

            # Verify cleanup still happened
            mock_metrics.dec_active_requests.assert_called_once()


class TestCreateApp:
    """Test the create_app function."""

    def test_create_app_with_metrics(self, mock_config):
        """Test app creation with metrics enabled."""
        with patch('mlserver.server.init_metrics') as mock_init_metrics, \
             patch('mlserver.server.load_predictor') as mock_load_predictor:

            mock_predictor = Mock()
            mock_load_predictor.return_value = mock_predictor
            mock_init_metrics.return_value = Mock()

            app = create_app(mock_config)

            # Verify app creation
            assert app.title == "MLServer FastAPI Wrapper"
            mock_init_metrics.assert_called_once()
            mock_load_predictor.assert_called_once_with(mock_config.predictor)

    def test_create_app_without_metrics(self, mock_config_minimal):
        """Test app creation with metrics disabled."""
        with patch('mlserver.server.init_metrics') as mock_init_metrics, \
             patch('mlserver.server.load_predictor') as mock_load_predictor:

            mock_predictor = Mock()
            mock_load_predictor.return_value = mock_predictor

            app = create_app(mock_config_minimal)

            # Verify app creation
            assert app.title == "MLServer FastAPI Wrapper"
            mock_init_metrics.assert_not_called()
            mock_load_predictor.assert_called_once_with(mock_config_minimal.predictor)

    def test_create_app_with_cors(self):
        """Test app creation with CORS middleware."""
        config = AppConfig(
            server=ServerConfig(
                host="127.0.0.1",
                port=8000,
                cors_origins=["http://localhost:3000", "https://example.com"]
            ),
            predictor=PredictorConfig(
                module="mlserver.predictors.sklearn",
                class_name="SKLearnPredictor",
                init_kwargs={"model_path": "model.pkl"}
            )
        )

        with patch('mlserver.server.load_predictor') as mock_load_predictor:
            mock_predictor = Mock()
            mock_load_predictor.return_value = mock_predictor

            app = create_app(config)

            # Check that CORS middleware was added
            cors_middleware_found = any(
                hasattr(middleware, 'cls') and
                middleware.cls.__name__ == 'CORSMiddleware'
                for middleware in app.user_middleware
            )
            assert cors_middleware_found


class TestPredictorWrapper:
    """Test the PredictorWrapper class."""

    def test_predictor_wrapper_init_thread_safe(self):
        """Test PredictorWrapper initialization with thread safety."""
        mock_predictor = Mock()
        wrapper = PredictorWrapper(mock_predictor, thread_safe=True)

        assert wrapper._predictor == mock_predictor
        assert wrapper._lock is not None

    def test_predictor_wrapper_init_not_thread_safe(self):
        """Test PredictorWrapper initialization without thread safety."""
        mock_predictor = Mock()
        wrapper = PredictorWrapper(mock_predictor, thread_safe=False)

        assert wrapper._predictor == mock_predictor
        assert wrapper._lock is None

    def test_predict_without_lock(self):
        """Test prediction without thread safety."""
        mock_predictor = Mock()
        mock_predictor.predict.return_value = [1, 0, 1]

        wrapper = PredictorWrapper(mock_predictor, thread_safe=False)
        result = wrapper.predict([[1, 2], [3, 4], [5, 6]])

        assert result == [1, 0, 1]
        mock_predictor.predict.assert_called_once_with([[1, 2], [3, 4], [5, 6]])

    def test_predict_with_lock(self):
        """Test prediction with thread safety."""
        mock_predictor = Mock()
        mock_predictor.predict.return_value = [1, 0]

        wrapper = PredictorWrapper(mock_predictor, thread_safe=True)
        result = wrapper.predict([[1, 2], [3, 4]])

        assert result == [1, 0]
        mock_predictor.predict.assert_called_once_with([[1, 2], [3, 4]])

    def test_predict_proba_success(self):
        """Test predict_proba method."""
        mock_predictor = Mock()
        mock_predictor.predict_proba.return_value = [[0.7, 0.3], [0.2, 0.8]]

        wrapper = PredictorWrapper(mock_predictor, thread_safe=False)
        result = wrapper.predict_proba([[1, 2], [3, 4]])

        assert result == [[0.7, 0.3], [0.2, 0.8]]

    def test_predict_proba_no_method(self):
        """Test predict_proba when method doesn't exist."""
        mock_predictor = Mock(spec=[])
        wrapper = PredictorWrapper(mock_predictor, thread_safe=False)

        with pytest.raises(AttributeError, match="predictor has no predict_proba"):
            wrapper.predict_proba([[1, 2]])

    def test_predictor_name_property(self):
        """Test the name property."""
        mock_predictor = Mock()
        mock_predictor.__class__.__name__ = "TestPredictor"

        wrapper = PredictorWrapper(mock_predictor)
        assert wrapper.name == "TestPredictor"

    def test_close_with_method(self):
        """Test close method when predictor has close."""
        mock_predictor = Mock()
        wrapper = PredictorWrapper(mock_predictor)

        wrapper.close()
        mock_predictor.close.assert_called_once()

    def test_close_without_method(self):
        """Test close method when predictor doesn't have close."""
        mock_predictor = Mock(spec=[])
        wrapper = PredictorWrapper(mock_predictor)

        # Should not raise an exception
        wrapper.close()

    def test_close_with_exception(self):
        """Test close method when predictor.close raises exception."""
        mock_predictor = Mock()
        mock_predictor.close.side_effect = Exception("Close failed")

        wrapper = PredictorWrapper(mock_predictor)

        # Should not propagate the exception
        wrapper.close()
        mock_predictor.close.assert_called_once()


class TestHelperFunctions:
    """Test server helper functions."""

    def test_prepare_input_data_success(self, mock_config):
        """Test _prepare_input_data with successful parsing."""
        with patch('mlserver.server.to_ndarray') as mock_to_ndarray:
            mock_to_ndarray.return_value = [[1, 2], [3, 4]]

            request = PredictRequest(inputs={"data": [[1, 2], [3, 4]]})
            result = _prepare_input_data(request, mock_config)

            assert result == [[1, 2], [3, 4]]
            mock_to_ndarray.assert_called_once()

    def test_prepare_input_data_failure(self, mock_config):
        """Test _prepare_input_data with parsing failure."""
        with patch('mlserver.server.to_ndarray') as mock_to_ndarray:
            mock_to_ndarray.side_effect = Exception("Parsing error")

            request = PredictRequest(inputs={"data": "invalid"})

            with pytest.raises(HTTPException) as exc_info:
                _prepare_input_data(request, mock_config)

            assert exc_info.value.status_code == 400
            assert "Input parsing failed" in str(exc_info.value.detail)

    def test_track_prediction_metrics_with_metrics(self, mock_config):
        """Test _track_prediction_metrics when metrics are enabled."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics, \
             patch('mlserver.server.log_prediction') as mock_log_prediction:

            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            _track_prediction_metrics("/predict", 0.5, 10, "TestModel", mock_config)

            mock_metrics.track_prediction.assert_called_once_with("/predict", 0.5, 10)
            mock_log_prediction.assert_called_once()

    def test_track_prediction_metrics_without_metrics(self, mock_config_minimal):
        """Test _track_prediction_metrics when metrics are disabled."""
        with patch('mlserver.server.get_metrics') as mock_get_metrics, \
             patch('mlserver.server.log_prediction') as mock_log_prediction:

            mock_get_metrics.return_value = None

            _track_prediction_metrics("/predict", 0.5, 10, "TestModel", mock_config_minimal)

            # Should not call track_prediction but should still log if structured logging enabled
            mock_log_prediction.assert_called_once()

    def test_to_jsonable_simple_types(self):
        """Test _to_jsonable with simple types."""
        assert _to_jsonable(42) == 42
        assert _to_jsonable("hello") == "hello"
        assert _to_jsonable([1, 2, 3]) == [1, 2, 3]

    def test_to_jsonable_numpy_types(self):
        """Test _to_jsonable with numpy-like types."""
        import numpy as np

        # Test numpy scalar
        result = _to_jsonable(np.int32(42))
        assert result == 42
        assert isinstance(result, int)

        # Test numpy array
        arr = np.array([1, 2, 3])
        result = _to_jsonable(arr)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_tolist2d_simple_list(self):
        """Test _tolist2d with simple nested list."""
        data = [[1, 2], [3, 4]]
        result = _tolist2d(data)
        assert result == [[1, 2], [3, 4]]

    def test_tolist2d_numpy_array(self):
        """Test _tolist2d with numpy array."""
        import numpy as np

        data = np.array([[1, 2], [3, 4]])
        result = _tolist2d(data)
        assert result == [[1, 2], [3, 4]]
        assert isinstance(result, list)
        assert all(isinstance(row, list) for row in result)


class TestHandlerFunctions:
    """Test the handler creation functions."""

    def test_create_predict_handler(self, mock_config):
        """Test _create_predict_handler function."""
        with patch('mlserver.server.load_predictor') as mock_load_predictor:
            mock_predictor = Mock()
            mock_load_predictor.return_value = mock_predictor

            app = Mock()
            handler = _create_predict_handler(app, mock_config, "/predict")

            # Verify that a handler function was created
            assert callable(handler)

    def test_create_predict_proba_handler(self, mock_config):
        """Test _create_predict_proba_handler function."""
        with patch('mlserver.server.load_predictor') as mock_load_predictor:
            mock_predictor = Mock()
            mock_load_predictor.return_value = mock_predictor

            app = Mock()
            handler = _create_predict_proba_handler(app, mock_config, "/predict_proba")

            # Verify that a handler function was created
            assert callable(handler)

    def test_app_lifespan_context(self, mock_config):
        """Test app lifespan context functionality."""
        with patch('mlserver.server.load_predictor') as mock_load_predictor:
            # Mock predictor with close method
            mock_predictor = Mock()
            mock_wrapper = Mock()
            mock_wrapper.close = Mock()

            with patch('mlserver.server.PredictorWrapper') as mock_wrapper_class:
                mock_wrapper_class.return_value = mock_wrapper
                mock_load_predictor.return_value = mock_predictor

                # Create app to test lifespan
                app = create_app(mock_config)

                # Verify predictor was loaded
                mock_load_predictor.assert_called_once_with(mock_config.predictor)