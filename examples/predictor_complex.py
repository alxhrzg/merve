"""Example predictor returning complex dictionary structures."""

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
from typing import Any, Dict, List, Union


class ComplexResponsePredictor:
    """Example predictor that returns complex nested structures."""

    def __init__(self):
        """Initialize the predictor."""
        self.name = "ComplexResponsePredictor"
        self.version = "1.0.0"

    def predict(self, X: Any) -> Dict[str, Any]:
        """Return a complex dictionary structure.

        This demonstrates the new response handling capabilities.
        """
        # Simulate complex analysis results
        num_samples = len(X) if hasattr(X, '__len__') else 1

        # Create predictions list of appropriate length
        base_pattern = [0, 1, 0]
        predictions = (base_pattern * (num_samples // 3 + 1))[:num_samples]

        return {
            "predictions": predictions,
            "analysis": {
                "confidence_scores": [0.95, 0.87, 0.92][:num_samples] if not HAS_NUMPY else np.random.rand(num_samples).tolist(),
                "feature_importance": {
                    "feature_1": 0.45,
                    "feature_2": 0.30,
                    "feature_3": 0.25
                },
                "decision_paths": [
                    {"node": 1, "feature": "age", "threshold": 30},
                    {"node": 3, "feature": "income", "threshold": 50000}
                ]
            },
            "metadata": {
                "model_version": self.version,
                "prediction_timestamp": "2025-01-17T10:30:00Z",
                "processing_time_ms": 15.4
            },
            "custom_fields": {
                "a": [1, 2, 34, 5],
                "b": {
                    "c": [1, 2, 3],
                    "d": [4, 5, 6]
                }
            }
        }

    def predict_proba(self, X: Any) -> List[List[float]]:
        """Return probability predictions."""
        num_samples = len(X) if hasattr(X, '__len__') else 1
        # Return mock probabilities
        if HAS_NUMPY:
            probs = np.random.rand(num_samples, 2)
            # Normalize to sum to 1
            return (probs / probs.sum(axis=1, keepdims=True)).tolist()
        else:
            # Return fixed probabilities if numpy not available
            return [[0.7, 0.3]] * num_samples


class LegacyFormatPredictor:
    """Example predictor that needs exact response format control."""

    def __init__(self):
        """Initialize the predictor."""
        self.name = "LegacyFormatPredictor"

    def predict(self, X: Any) -> Dict[str, Any]:
        """Return a legacy format response.

        This should be used with response_format: "passthrough"
        to return exactly this structure without modification.
        """
        return {
            "status": "success",
            "code": 200,
            "data": {
                "results": [1, 0, 1],
                "scores": [0.95, 0.12, 0.88]
            },
            "errors": [],
            "warnings": ["Feature 3 missing, using default"]
        }


class SimplePredictor:
    """Traditional predictor returning simple list."""

    def __init__(self):
        """Initialize the predictor."""
        self.name = "SimplePredictor"

    def predict(self, X: Any) -> List[int]:
        """Return simple list of predictions."""
        num_samples = len(X) if hasattr(X, '__len__') else 1
        base_pattern = [0, 1]
        return (base_pattern * (num_samples // 2 + 1))[:num_samples]