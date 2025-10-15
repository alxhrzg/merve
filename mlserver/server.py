
from __future__ import annotations
import time
import threading
from contextlib import asynccontextmanager
from typing import Any, Optional
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import AppConfig
from .predictor_loader import load_predictor
from .adapters import to_ndarray, AdapterError
from .auto_detect import (
    get_simplified_info_response,
    generate_simplified_metadata,
    get_deployed_timestamp,
    get_mlserver_package_version
)
from .schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
    ClassifierMetadataResponse,
    CustomPredictResponse,
    SinglePredictRequest,
)
from .metrics import init_metrics, get_metrics
from .concurrency_limiter import PredictionSemaphore, PredictionLimiter
from .logging_conf import (
    set_correlation_id,
    log_request,
    log_response,
    log_prediction
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: AppConfig):
        super().__init__(app)
        self.config = config
        self.metrics = get_metrics() if config.observability.metrics else None

    async def dispatch(self, request: Request, call_next):
        # Skip metrics for health and metrics endpoints to reduce overhead
        skip_metrics = request.url.path in ["/healthz", self.config.observability.metrics_endpoint]

        # Set correlation ID if enabled
        correlation_id = None
        if self.config.observability.correlation_ids:
            correlation_id = set_correlation_id()

        start_time = time.perf_counter()

        # Track active requests only if metrics enabled and not skipped
        if self.metrics and not skip_metrics:
            self.metrics.inc_active_requests()

        # Log request start
        if self.config.observability.structured_logging:
            log_request(
                method=request.method,
                path=request.url.path,
                correlation_id=correlation_id
            )

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time

            # Track metrics only if enabled and not skipped
            if self.metrics and not skip_metrics:
                self.metrics.track_request(request, response, duration)
                self.metrics.dec_active_requests()

            # Log response
            if self.config.observability.structured_logging:
                log_response(
                    status_code=response.status_code,
                    duration_ms=duration * 1000
                )

            return response

        except Exception as e:
            duration = time.perf_counter() - start_time

            if self.metrics and not skip_metrics:
                self.metrics.dec_active_requests()

            if self.config.observability.structured_logging:
                log_response(
                    status_code=500,
                    duration_ms=duration * 1000,
                    error=str(e)
                )
            raise


class PredictorWrapper:
    def __init__(self, predictor: Any, thread_safe: bool = False):
        self._predictor = predictor
        self._lock = threading.Lock() if thread_safe else None

    def predict(self, X):
        if self._lock:
            with self._lock:
                return self._predictor.predict(X)
        return self._predictor.predict(X)

    def predict_proba(self, X):
        if not hasattr(self._predictor, "predict_proba"):
            raise AttributeError("predictor has no predict_proba")
        if self._lock:
            with self._lock:
                return self._predictor.predict_proba(X)
        return self._predictor.predict_proba(X)

    @property
    def name(self) -> str:
        return type(self._predictor).__name__

    def close(self):
        if hasattr(self._predictor, "close"):
            try:
                self._predictor.close()
            except Exception:
                pass


def _prepare_input_data(req: PredictRequest, config: AppConfig):
    """Parse and prepare input data for prediction."""
    import logging
    logger = logging.getLogger(__name__)

    # Debug logging for request details
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Incoming request payload type: {type(req.payload)}")
        logger.debug(f"Incoming request payload: {req.payload}")
        logger.debug(f"Adapter configuration: {config.api.adapter}")
        logger.debug(f"Feature order: {config.api.feature_order}")

    try:
        # Resolve feature_order from file if needed
        feature_order = config.api.get_resolved_feature_order(
            base_path=Path(config.project_path_internal) if config.project_path_internal else Path.cwd()
        )

        return to_ndarray(
            req.payload,
            adapter=config.api.adapter,
            feature_order=feature_order,
        )
    except Exception as e:
        # Log full traceback in DEBUG mode
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(f"Input parsing failed with detailed traceback:")
        else:
            logger.error(f"Input parsing error: {e}")

        # In DEBUG mode, include more detail in the response
        if logger.isEnabledFor(logging.DEBUG):
            raise HTTPException(
                status_code=400,
                detail=f"Input parsing failed: {str(e)}. Check server logs for full traceback."
            )
        else:
            raise HTTPException(status_code=400, detail="Input parsing failed. Please check your input format.")


def _track_prediction_metrics(endpoint_path: str, duration_seconds: float,
                             sample_count: int, model_name: str, config: AppConfig) -> None:
    """Track prediction metrics and logging."""
    # Track prediction metrics only if enabled
    if config.observability.metrics:
        metrics = get_metrics()
        if metrics:
            metrics.track_prediction(endpoint_path, duration_seconds, sample_count)

    # Log prediction
    if config.observability.structured_logging:
        log_prediction(
            model_name=model_name,
            duration_ms=duration_seconds * 1000,
            sample_count=sample_count
        )


def _create_predict_handler(app: FastAPI, config: AppConfig, endpoint_path: str,
                           prediction_limiter: Optional[PredictionSemaphore] = None):
    """Create a predict endpoint handler with concurrency control."""
    def predict(req: PredictRequest):
        # Use prediction limiter if configured
        if prediction_limiter:
            with PredictionLimiter(prediction_limiter):
                return _execute_prediction(app, config, endpoint_path, req)
        else:
            return _execute_prediction(app, config, endpoint_path, req)
    return predict


def _get_classifier_metadata(config: AppConfig, predictor_class_name: str = None, config_file_name: str = None) -> Optional[ClassifierMetadataResponse]:
    """Get simplified classifier metadata for response."""
    if not config.classifier:
        return None

    # Use auto-detection for git info
    from .auto_detect import get_git_info, get_project_name, get_mlserver_git_info
    import os

    git_data = get_git_info(config.project_path or ".")
    mlserver_info = get_mlserver_git_info()

    # Get config_file from environment if not provided (for containerized deployments)
    if not config_file_name:
        config_file_name = os.environ.get('MLSERVER_CONFIG_FILE')

    metadata = ClassifierMetadataResponse(
        project=git_data.get("repository") or get_project_name(config.project_path or "."),
        classifier=config.classifier.get('name', 'unknown'),
        predictor_class=predictor_class_name,
        predictor_module=config.predictor.module if config.predictor else None,
        config_file=config_file_name,
        git_commit=git_data.get("commit"),
        git_tag=git_data.get("tag"),
        deployed_at=None,  # Will be set at runtime
        mlserver_version=mlserver_info.get("package_version", "unknown"),
        mlserver_api_commit=mlserver_info.get("api_commit"),
        mlserver_api_tag=mlserver_info.get("api_tag")
    )

    # Note: deployed_at will be added at runtime from app.state.deployed_at

    return metadata


def _format_response(predictions, config: AppConfig, timing_ms: float, model_name: str, metadata=None):
    """Format response based on configuration.

    Args:
        predictions: Raw predictions from the predictor
        config: Application configuration
        timing_ms: Time taken for prediction in milliseconds
        model_name: Name of the predictor/model
        metadata: Optional classifier metadata

    Returns:
        Formatted response based on response_format configuration
    """
    response_format = config.api.response_format

    # Passthrough format - return exactly what predictor returned
    if response_format == 'passthrough':
        return predictions

    # Convert to JSON-serializable format
    json_safe = _to_jsonable(predictions)

    # Custom format - flexible structure with result field
    if response_format == 'custom':
        # For dictionaries, include the whole structure
        if isinstance(json_safe, dict):
            # Extract predictions if configured or if the dict contains a 'predictions' key
            predictions_list = None
            if config.api.extract_values:
                predictions_list = list(json_safe.values())
            elif 'predictions' in json_safe:
                # Use the predictions field if it exists in the response
                predictions_list = json_safe['predictions'] if isinstance(json_safe['predictions'], list) else [json_safe['predictions']]

            response = CustomPredictResponse(
                result=json_safe,
                predictions=predictions_list,
                time_ms=timing_ms,
                predictor_class=model_name,
                metadata=metadata
            )
            return response
        else:
            # For non-dict responses, wrap in result field
            return CustomPredictResponse(
                result=json_safe,
                predictions=json_safe if isinstance(json_safe, list) else [json_safe],
                time_ms=timing_ms,
                predictor_class=model_name,
                metadata=metadata
            )

    # Standard format (default) - backward compatible
    # Special handling for dict responses
    if isinstance(json_safe, dict):
        # In standard mode with dict, we need to handle it specially
        # to maintain backward compatibility
        if config.api.extract_values:
            # Extract values for predictions field
            predictions_list = list(json_safe.values())
        else:
            # Use the dict as a single prediction item
            predictions_list = [json_safe]

        return PredictResponse(
            predictions=predictions_list,
            time_ms=timing_ms,
            predictor_class=model_name,
            metadata=metadata
        )

    # Standard format for list/array responses
    if isinstance(json_safe, list):
        return PredictResponse(
            predictions=json_safe,
            time_ms=timing_ms,
            predictor_class=model_name,
            metadata=metadata
        )

    # Single value response - wrap in list for consistency
    return PredictResponse(
        predictions=[json_safe],
        time_ms=timing_ms,
        predictor_class=model_name,
        metadata=metadata
    )


def _execute_prediction(app: FastAPI, config: AppConfig, endpoint_path: str, req: PredictRequest):
    """Execute the actual prediction."""
    start_time = time.perf_counter()

    X = _prepare_input_data(req, config)

    try:
        predictions = app.state.predictor.predict(X)
    except Exception as e:
        # Log full error internally, return sanitized message to client
        import logging
        logging.error(f"Prediction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Prediction failed. Please contact support if the issue persists.")

    duration_ms = (time.perf_counter() - start_time) * 1000

    # Track metrics - handle different prediction types
    if isinstance(predictions, (list, tuple)):
        num_predictions = len(predictions)
    elif hasattr(predictions, 'shape'):  # numpy array
        num_predictions = predictions.shape[0] if len(predictions.shape) > 0 else 1
    else:
        num_predictions = 1

    _track_prediction_metrics(
        endpoint_path, duration_ms / 1000, num_predictions,
        app.state.predictor.name, config
    )

    # Include cached metadata if available
    metadata = getattr(app.state, 'metadata', None)

    # Add deployed_at timestamp to metadata
    if metadata:
        deployed_at = getattr(app.state, 'deployed_at', None)
        if deployed_at:
            metadata.deployed_at = deployed_at

    # Use the new formatting function
    return _format_response(
        predictions,
        config,
        duration_ms,
        app.state.predictor.name,
        metadata
    )


def _create_predict_proba_handler(app: FastAPI, config: AppConfig, endpoint_path: str,
                                 prediction_limiter: Optional[PredictionSemaphore] = None):
    """Create a predict_proba endpoint handler with concurrency control."""
    def predict_proba(req: PredictRequest):
        # Use prediction limiter if configured
        if prediction_limiter:
            with PredictionLimiter(prediction_limiter):
                return _execute_predict_proba(app, config, endpoint_path, req)
        else:
            return _execute_predict_proba(app, config, endpoint_path, req)
    return predict_proba


def _execute_predict_proba(app: FastAPI, config: AppConfig, endpoint_path: str, req: PredictRequest):
    """Execute the actual probability prediction."""
    start_time = time.perf_counter()

    X = _prepare_input_data(req, config)

    try:
        probabilities = app.state.predictor.predict_proba(X)
    except AttributeError:
        raise HTTPException(status_code=501, detail="Probability prediction not available for this model.")
    except Exception as e:
        # Log full error internally, return sanitized message to client
        import logging
        logging.error(f"Predict_proba error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Probability prediction failed. Please contact support if the issue persists.")

    duration_ms = (time.perf_counter() - start_time) * 1000

    _track_prediction_metrics(
        endpoint_path, duration_ms / 1000, len(probabilities),
        app.state.predictor.name, config
    )

    # Include cached metadata if available
    metadata = getattr(app.state, 'metadata', None)

    # Add deployed_at timestamp to metadata
    if metadata:
        deployed_at = getattr(app.state, 'deployed_at', None)
        if deployed_at:
            metadata.deployed_at = deployed_at

    # Create ProbaResponse with metadata
    from .schemas import ProbaResponse
    return ProbaResponse(
        probabilities=_tolist2d(probabilities),
        time_ms=duration_ms,
        classes=None,  # Could be populated if predictor provides class names
        metadata=metadata
    )


def _register_endpoint(app: FastAPI, endpoint_name: str, handler,
                     base_path: str, response_model=None) -> None:
    """Register a versioned endpoint."""
    # Only register versioned endpoint
    if base_path:
        versioned_path = f"{base_path}/{endpoint_name}"
        if response_model:
            app.post(versioned_path, response_model=response_model)(handler)
        else:
            app.post(versioned_path)(handler)
    else:
        # Fallback to root level if no base path (should not happen in modern config)
        fallback_path = f"/{endpoint_name}"
        if response_model:
            app.post(fallback_path, response_model=response_model)(handler)
        else:
            app.post(fallback_path)(handler)


def _register_prediction_endpoints(app: FastAPI, config: AppConfig,
                                  prediction_limiter: Optional[PredictionSemaphore] = None) -> None:
    """Register versioned prediction endpoints with optional concurrency control."""
    base_path = config.get_base_path()

    # Determine response model based on configuration
    response_format = config.api.response_format
    if response_format == "custom":
        response_model = CustomPredictResponse
    elif response_format == "passthrough":
        response_model = None  # No validation for passthrough
    else:
        response_model = PredictResponse  # Default standard format

    # Register predict endpoint
    if config.is_endpoint_enabled("predict"):
        endpoint_path = f"{base_path}/predict" if base_path else "/predict"
        predict_handler = _create_predict_handler(app, config, endpoint_path, prediction_limiter)
        _register_endpoint(
            app, "predict", predict_handler, base_path, response_model
        )

    # Note: batch_predict endpoint removed - /predict already handles batches naturally

    # Register predict_proba endpoint
    if config.is_endpoint_enabled("predict_proba"):
        endpoint_path = f"{base_path}/predict_proba" if base_path else "/predict_proba"
        predict_proba_handler = _create_predict_proba_handler(app, config, endpoint_path, prediction_limiter)
        _register_endpoint(
            app, "predict_proba", predict_proba_handler, base_path
        )


def create_app(config: AppConfig, config_file_name: str = None) -> FastAPI:
    predictor_wrapper: Optional[PredictorWrapper] = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal predictor_wrapper
        # Load predictor once at startup
        # Pass config_dir for intelligent module resolution
        config_dir = config.project_path if config.project_path else None
        predictor = load_predictor(
            config.predictor.module,
            config.predictor.class_name,
            config.predictor.init_kwargs,
            config_dir=config_dir
        )
        predictor_wrapper = PredictorWrapper(
            predictor, thread_safe=config.api.thread_safe_predict
        )
        app.state.predictor = predictor_wrapper

        # Cache metadata at startup
        predictor_class_name = config.predictor.class_name if config.predictor else None
        app.state.metadata = _get_classifier_metadata(config, predictor_class_name, config_file_name)

        # Cache deployment timestamp at startup
        app.state.deployed_at = get_deployed_timestamp()

        # Initialize metrics if enabled
        if config.observability.metrics:
            init_metrics(predictor_wrapper.name)

        yield
        # Shutdown
        predictor_wrapper.close()

    app = FastAPI(title=config.get_api_title(), lifespan=lifespan)

    # Add observability middleware
    app.add_middleware(ObservabilityMiddleware, config=config)

    # CORS
    if config.server.cors:
        c = config.server.cors
        app.add_middleware(
            CORSMiddleware,
            allow_origins=c.allow_origins,
            allow_credentials=c.allow_credentials,
            allow_methods=c.allow_methods,
            allow_headers=c.allow_headers,
        )

    # Create prediction limiter if concurrency control is enabled
    prediction_limiter = None
    if config.api.max_concurrent_predictions > 0:
        prediction_limiter = PredictionSemaphore(
            max_concurrent=config.api.max_concurrent_predictions,
            timeout=0  # Immediate rejection for Kubernetes pod scaling
        )

    @app.get("/healthz", response_model=HealthResponse)
    def health():
        predictor = getattr(app.state, "predictor", None)
        return HealthResponse(status="ok", model=predictor.name if predictor else None)

    @app.get("/info")
    def info():
        """Get simplified classifier information with auto-detected metadata."""
        predictor = getattr(app.state, "predictor", None)
        deployed_at = getattr(app.state, 'deployed_at', None)

        # Use the new simplified info response
        info_response = get_simplified_info_response(
            config.model_dump(),
            predictor.name if predictor else "unknown",
            config.project_path or "."
        )

        # Use the cached deployed_at timestamp from startup
        if deployed_at:
            info_response["deployed_at"] = deployed_at

        # Keep the endpoints section consistent
        info_response["endpoints"] = {
            "predict": "/predict" if config.is_endpoint_enabled("predict") else None,
            "predict_proba": "/predict_proba" if config.is_endpoint_enabled("predict_proba") else None,
            "info": "/info",
            "health": "/healthz",
            "metrics": config.observability.metrics_endpoint if config.observability.metrics else None
        }

        return info_response

    @app.get("/status")
    def prediction_status():
        """Get current prediction availability status."""
        if prediction_limiter:
            return {
                "prediction_slots_available": prediction_limiter.is_available,
                "active_predictions": prediction_limiter.active_predictions,
                "max_concurrent_predictions": config.api.max_concurrent_predictions,
                "concurrency_control_enabled": True
            }
        else:
            return {
                "prediction_slots_available": True,
                "active_predictions": 0,
                "max_concurrent_predictions": None,
                "concurrency_control_enabled": False
            }

    # Add metrics endpoint if enabled
    if config.observability.metrics:
        # Cache metrics for 5 seconds to reduce CPU load during monitoring scrapes
        @lru_cache(maxsize=1)
        def _get_cached_metrics(timestamp_key: int):
            """Cache metrics generation keyed by 5-second intervals."""
            metrics_collector = get_metrics()
            if metrics_collector:
                return Response(
                    content=metrics_collector.generate_metrics(),
                    media_type=metrics_collector.get_content_type()
                )
            return Response(content="# No metrics available\n", media_type="text/plain")

        @app.get(config.observability.metrics_endpoint)
        def metrics():
            # Cache key updates every 5 seconds
            cache_key = int(time.time() // 5)
            return _get_cached_metrics(cache_key)

    # Register versioned prediction endpoints
    _register_prediction_endpoints(app, config, prediction_limiter)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_jsonable(x):
    """Convert any Python object to JSON-serializable format.

    Handles numpy arrays, pandas objects, and nested data structures.
    """
    # Handle numpy types
    try:
        import numpy as np
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
    except ImportError:
        pass

    # Handle pandas types
    try:
        import pandas as pd
        if isinstance(x, pd.DataFrame):
            return x.to_dict('records')
        if isinstance(x, pd.Series):
            return x.tolist()
    except ImportError:
        pass

    # Recursively handle dictionaries
    if isinstance(x, dict):
        return {k: _to_jsonable(v) for k, v in x.items()}

    # Recursively handle lists and tuples
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(item) for item in x]

    # Return as-is for basic types (str, int, float, bool, None)
    return x


def _tolist2d(arr):
    try:
        import numpy as _np
        if isinstance(arr, _np.ndarray):
            return arr.tolist()
    except Exception:
        pass
    # assume already nested list
    return arr


# Factory function for uvicorn when using workers
def app() -> FastAPI:
    """Factory function to create the FastAPI app for uvicorn workers."""
    import os
    import yaml
    from pathlib import Path
    from .config import AppConfig
    from .multi_classifier import detect_multi_classifier_config, load_multi_classifier_config

    # Try to find config file
    config_paths = [
        os.environ.get('MLSERVER_CONFIG_PATH'),
        'mlserver.yaml',
        'config.yaml',
        'mlserver_multi_classifier.yaml',
        'mlserver_single_classifier.yaml'
    ]

    config_file = None
    for path in config_paths:
        if path and Path(path).exists():
            config_file = Path(path)
            break

    if not config_file:
        raise RuntimeError("No configuration file found. Please specify mlserver.yaml or set MLSERVER_CONFIG_PATH")

    # Check for multi-classifier config
    if detect_multi_classifier_config(str(config_file)):
        # Get classifier from environment or use default
        classifier_name = os.environ.get('MLSERVER_CLASSIFIER')
        configs = load_multi_classifier_config(str(config_file))

        if classifier_name and classifier_name in configs:
            cfg = configs[classifier_name]
        else:
            # Find default or first classifier
            with open(config_file, 'r') as f:
                raw = yaml.safe_load(f)
            default = raw.get('default_classifier')
            if default and default in configs:
                cfg = configs[default]
            else:
                cfg = next(iter(configs.values()))
    else:
        # Single classifier config
        with open(config_file, 'r') as f:
            raw = yaml.safe_load(f)
        cfg = AppConfig.model_validate(raw)

    cfg.set_project_path(str(config_file.parent))

    return create_app(cfg, config_file_name=config_file.name)
