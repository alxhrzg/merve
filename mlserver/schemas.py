
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    status: str = "ok"
    model: Optional[str] = None


class PredictRequest(BaseModel):
    """Request payload for predictions.

    The payload structure depends on the adapter configuration:
    - records adapter: {"records": [{"feature1": value1, "feature2": value2}, ...]}
    - ndarray adapter: {"ndarray": [[value1, value2], [value3, value4], ...]}
    """
    # Fully flexible payload — we parse inside route
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Prediction input data. Format depends on adapter: 'records' (list of dicts) or 'ndarray' (2D array)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Records format (for adapter='records')",
                    "value": {
                        "payload": {
                            "records": [
                                {"feature1": 1.5, "feature2": 2.3, "feature3": 0.8},
                                {"feature1": 2.1, "feature2": 1.7, "feature3": 1.2}
                            ]
                        }
                    }
                },
                {
                    "description": "Ndarray format (for adapter='ndarray')",
                    "value": {
                        "payload": {
                            "ndarray": [
                                [1.5, 2.3, 0.8],
                                [2.1, 1.7, 1.2]
                            ]
                        }
                    }
                },
                {
                    "description": "Single record prediction",
                    "value": {
                        "payload": {
                            "records": [
                                {"feature1": 1.5, "feature2": 2.3, "feature3": 0.8}
                            ]
                        }
                    }
                }
            ]
        }
    )


# BatchPredictRequest removed - /predict already handles both single and batch predictions
# Just use PredictRequest with multiple records in the payload


class ClassifierMetadataResponse(BaseModel):
    """Simplified metadata included in responses."""
    project: str = Field(description="Auto-detected project/repository name")
    classifier: str = Field(description="Classifier name")
    predictor_class: Optional[str] = Field(None, description="Predictor class name")
    predictor_module: Optional[str] = Field(None, description="Module file containing predictor")
    config_file: Optional[str] = Field(None, description="Configuration file used")
    git_commit: Optional[str] = Field(None, description="Git commit hash")
    git_tag: Optional[str] = Field(None, description="Git tag if on tagged commit")
    deployed_at: Optional[str] = Field(None, description="Deployment timestamp")
    mlserver_version: Optional[str] = Field(None, description="MLServer package version")
    mlserver_api_commit: Optional[str] = Field(None, description="MLServer API git commit")
    mlserver_api_tag: Optional[str] = Field(None, description="MLServer API git tag")


class PredictResponse(BaseModel):
    """Response from prediction endpoints."""
    predictions: List[Any] = Field(description="Model predictions for each input record")
    time_ms: float = Field(description="Time taken for prediction in milliseconds")
    metadata: Optional[ClassifierMetadataResponse] = Field(None, description="Comprehensive classifier metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "predictions": [0, 1, 0],
                    "time_ms": 12.5,
                    "model": "catboost-survival",
                    "metadata": {
                        "repository": "mlserver-repo",
                        "classifier": "catboost-survival",
                        "version": "1.0.0",
                        "api_version": "v1"
                    }
                },
                {
                    "predictions": ["class_a", "class_b", "class_a"],
                    "time_ms": 8.3,
                    "model": "text-classifier"
                }
            ]
        }
    )


class ProbaResponse(BaseModel):
    """Response from predict_proba endpoints."""
    probabilities: List[List[float]] = Field(description="Class probabilities for each input record")
    time_ms: float = Field(description="Time taken for prediction in milliseconds")
    classes: Optional[List[str]] = Field(None, description="Class labels corresponding to probability columns")
    metadata: Optional[ClassifierMetadataResponse] = Field(None, description="Comprehensive classifier metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "probabilities": [
                        [0.75, 0.25],
                        [0.10, 0.90],
                        [0.60, 0.40]
                    ],
                    "time_ms": 15.2,
                    "classes": ["negative", "positive"],
                    "model": "catboost-survival"
                }
            ]
        }
    )


class CustomPredictResponse(BaseModel):
    """Flexible response supporting arbitrary structures for custom predictors."""
    result: Any = Field(description="Prediction result (any JSON-serializable structure)")
    predictions: Optional[List[Any]] = Field(
        None,
        description="Optional extracted predictions for compatibility"
    )
    time_ms: float = Field(description="Time taken for prediction in milliseconds")
    metadata: Optional[ClassifierMetadataResponse] = Field(
        None,
        description="Classifier version and metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "result": {
                        "a": [1, 2, 3, 4, 5],
                        "b": {
                            "c": [1, 2, 3],
                            "d": [4, 5, 6]
                        }
                    },
                    "time_ms": 16.4,
                    "model": "CustomPredictor"
                },
                {
                    "result": {
                        "predictions": [0, 1, 0],
                        "confidence": [0.95, 0.87, 0.92],
                        "features_used": ["feature1", "feature2", "feature3"]
                    },
                    "time_ms": 12.5,
                    "model": "AdvancedClassifier",
                    "metadata": {
                        "repository": "mlserver-repo",
                        "classifier": "advanced-classifier",
                        "version": "2.0.0",
                        "api_version": "v1"
                    }
                }
            ]
        }
    )


class SinglePredictRequest(BaseModel):
    """Request for single record prediction with clear semantics."""
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Single record input. Use 'record' for dict format or 'ndarray' for array format"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Single record format",
                    "value": {
                        "payload": {
                            "record": {"feature1": 1.5, "feature2": 2.3, "feature3": 0.8}
                        }
                    }
                },
                {
                    "description": "Single array format",
                    "value": {
                        "payload": {
                            "ndarray": [1.5, 2.3, 0.8]
                        }
                    }
                }
            ]
        }
    )
