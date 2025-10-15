"""Test complex response handling and formatting."""

import pytest
import numpy as np
from unittest.mock import Mock
from mlserver.server import _to_jsonable, _format_response
from mlserver.config import AppConfig, ApiConfig
from mlserver.schemas import ClassifierMetadataResponse


class TestToJsonable:
    """Test the enhanced _to_jsonable function."""

    def test_simple_dict(self):
        """Test conversion of simple dictionary."""
        input_data = {"a": 1, "b": 2, "c": 3}
        result = _to_jsonable(input_data)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_nested_dict(self):
        """Test conversion of nested dictionary."""
        input_data = {
            "a": [1, 2, 3, 4, 5],
            "b": {
                "c": [1, 2, 3],
                "d": [4, 5, 6]
            }
        }
        result = _to_jsonable(input_data)
        assert result == input_data

    def test_numpy_array(self):
        """Test conversion of numpy arrays."""
        input_data = np.array([[1, 2, 3], [4, 5, 6]])
        result = _to_jsonable(input_data)
        assert result == [[1, 2, 3], [4, 5, 6]]

    def test_numpy_scalar(self):
        """Test conversion of numpy scalar."""
        input_data = np.float32(3.14)
        result = _to_jsonable(input_data)
        assert isinstance(result, float)
        assert abs(result - 3.14) < 0.001

    def test_mixed_types(self):
        """Test conversion of mixed types including numpy."""
        input_data = {
            "predictions": np.array([0, 1, 0]),
            "probabilities": np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]]),
            "metadata": {
                "confidence": np.float32(0.95),
                "features": ["a", "b", "c"]
            }
        }
        result = _to_jsonable(input_data)
        expected = {
            "predictions": [0, 1, 0],
            "probabilities": [[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]],
            "metadata": {
                "confidence": pytest.approx(0.95, rel=1e-3),
                "features": ["a", "b", "c"]
            }
        }
        assert result["predictions"] == expected["predictions"]
        assert result["probabilities"] == expected["probabilities"]
        assert result["metadata"]["features"] == expected["metadata"]["features"]
        assert abs(result["metadata"]["confidence"] - 0.95) < 0.001

    def test_list_of_dicts(self):
        """Test conversion of list of dictionaries."""
        input_data = [
            {"id": 1, "value": np.array([1, 2, 3])},
            {"id": 2, "value": np.array([4, 5, 6])}
        ]
        result = _to_jsonable(input_data)
        expected = [
            {"id": 1, "value": [1, 2, 3]},
            {"id": 2, "value": [4, 5, 6]}
        ]
        assert result == expected


class TestFormatResponse:
    """Test the response formatting function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metadata = ClassifierMetadataResponse(
            project="test-project",
            classifier="test-classifier",
            git_commit="abc123",
            git_tag="v1.0.0",
            deployed_at="2025-01-01T10:00:00Z",
            mlserver_version="2.0.0"
        )

    def test_standard_format_with_list(self):
        """Test standard format with list predictions."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = [0, 1, 0, 1]
        result = _format_response(predictions, config, 10.5, "TestModel", self.metadata)

        assert hasattr(result, 'predictions')
        assert result.predictions == [0, 1, 0, 1]
        assert result.time_ms == 10.5
        assert result.predictor_class == "TestModel"
        assert result.metadata == self.metadata

    def test_standard_format_with_dict(self):
        """Test standard format with dictionary predictions."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard", extract_values=False),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = {"a": [1, 2, 3], "b": {"c": [4, 5, 6]}}
        result = _format_response(predictions, config, 15.2, "TestModel", self.metadata)

        assert hasattr(result, 'predictions')
        # Without extract_values, the dict is wrapped in a list
        assert result.predictions == [{"a": [1, 2, 3], "b": {"c": [4, 5, 6]}}]
        assert result.time_ms == 15.2

    def test_standard_format_with_dict_extract_values(self):
        """Test standard format with dictionary predictions and value extraction."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard", extract_values=True),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = {"class1": 0.8, "class2": 0.2}
        result = _format_response(predictions, config, 12.0, "TestModel", None)

        assert hasattr(result, 'predictions')
        # With extract_values, only the values are returned
        assert result.predictions == [0.8, 0.2]

    def test_custom_format_with_dict(self):
        """Test custom format with dictionary predictions."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="custom", extract_values=False),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = {
            "a": [1, 2, 3, 4, 5],
            "b": {
                "c": [1, 2, 3],
                "d": [4, 5, 6]
            }
        }
        result = _format_response(predictions, config, 20.0, "CustomModel", self.metadata)

        assert hasattr(result, 'result')
        assert result.result == predictions
        assert result.predictions is None  # No extraction
        assert result.time_ms == 20.0
        assert result.predictor_class == "CustomModel"
        assert result.metadata == self.metadata

    def test_custom_format_with_list(self):
        """Test custom format with list predictions."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="custom"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = [0, 1, 0]
        result = _format_response(predictions, config, 8.5, "CustomModel", None)

        assert hasattr(result, 'result')
        assert result.result == [0, 1, 0]
        assert result.predictions == [0, 1, 0]
        assert result.time_ms == 8.5

    def test_passthrough_format(self):
        """Test passthrough format returns unmodified predictions."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="passthrough"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = {
            "custom": "response",
            "with": ["any", "structure"],
            "numbers": [1, 2, 3]
        }
        result = _format_response(predictions, config, 5.0, "Model", None)

        # Passthrough returns exactly what was passed in
        assert result == predictions

    def test_numpy_array_handling(self):
        """Test that numpy arrays are properly converted."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = np.array([0, 1, 0, 1])
        result = _format_response(predictions, config, 7.3, "NumpyModel", None)

        assert hasattr(result, 'predictions')
        assert result.predictions == [0, 1, 0, 1]
        assert isinstance(result.predictions, list)

    def test_single_value_prediction(self):
        """Test single value prediction gets wrapped in list."""
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        predictions = 42
        result = _format_response(predictions, config, 3.2, "SingleModel", None)

        assert hasattr(result, 'predictions')
        assert result.predictions == [42]


class TestComplexPredictor:
    """Test with a mock predictor returning complex structures."""

    def test_complex_dict_response(self):
        """Test end-to-end with predictor returning complex dictionary."""
        # This simulates your exact use case
        class ComplexPredictor:
            def predict(self, X):
                return {
                    "a": [1, 2, 34, 5],
                    "b": {
                        "c": [1, 2, 3],
                        "d": [4, 5, 6]
                    }
                }

        predictor = ComplexPredictor()
        predictions = predictor.predict(None)

        # Test with standard format
        config = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="standard"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        result = _format_response(predictions, config, 16.365, "RFQLikelihoodPredictor", None)

        # Should wrap the dict in a list for standard format
        assert result.predictions == [{
            "a": [1, 2, 34, 5],
            "b": {
                "c": [1, 2, 3],
                "d": [4, 5, 6]
            }
        }]

        # Test with custom format
        config_custom = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="custom"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        result_custom = _format_response(predictions, config_custom, 16.365, "RFQLikelihoodPredictor", None)

        # Should preserve the full structure in result field
        assert result_custom.result == {
            "a": [1, 2, 34, 5],
            "b": {
                "c": [1, 2, 3],
                "d": [4, 5, 6]
            }
        }

        # Test with passthrough format
        config_pass = AppConfig(
            predictor={"module": "test", "class_name": "Test"},
            api=ApiConfig(response_format="passthrough"),
            classifier={"name": "test-classifier", "version": "1.0.0"}
        )
        result_pass = _format_response(predictions, config_pass, 16.365, "RFQLikelihoodPredictor", None)

        # Should return exactly the original
        assert result_pass == predictions