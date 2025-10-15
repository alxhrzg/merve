import pytest
import numpy as np
from mlserver.adapters import (
    to_ndarray, AdapterError, _infer_adapter_type,
    _get_cached_feature_order, _records_to_numpy_fast,
    _extract_ndarray_data, _extract_records_data,
    _process_records_to_array, _FEATURE_ORDER_CACHE
)


class TestPayloadInference:
    """Test payload type inference"""

    def test_infer_records_payload(self):
        payload = {"records": [{"a": 1, "b": 2}]}
        assert _infer_adapter_type(payload) == "records"

    def test_infer_instances_payload(self):
        payload = {"instances": [{"a": 1, "b": 2}]}
        assert _infer_adapter_type(payload) == "records"

    def test_infer_features_payload(self):
        payload = {"features": {"a": 1, "b": 2}}
        assert _infer_adapter_type(payload) == "records"

    def test_infer_ndarray_payload(self):
        payload = {"ndarray": [[1, 2, 3]]}
        assert _infer_adapter_type(payload) == "ndarray"

    def test_infer_inputs_payload(self):
        payload = {"inputs": [[1, 2, 3]]}
        assert _infer_adapter_type(payload) == "ndarray"

    def test_infer_default_fallback(self):
        payload = {"unknown": "format"}
        assert _infer_adapter_type(payload) == "records"


class TestRecordsAdapter:
    """Test records format conversion"""

    def test_records_basic(self):
        payload = {
            "records": [
                {"a": 1, "b": 2},
                {"a": 3, "b": 4}
            ]
        }
        result = to_ndarray(payload, adapter="records")
        expected = np.array([[1, 2], [3, 4]])
        np.testing.assert_array_equal(result, expected)

    def test_records_with_feature_order(self):
        payload = {
            "records": [
                {"b": 2, "a": 1},  # Different order
                {"b": 4, "a": 3}
            ]
        }
        feature_order = ["a", "b"]
        result = to_ndarray(payload, adapter="records", feature_order=feature_order)
        expected = np.array([[1, 2], [3, 4]])
        np.testing.assert_array_equal(result, expected)

    def test_instances_format(self):
        payload = {
            "instances": [
                {"a": 1, "b": 2},
                {"a": 3, "b": 4}
            ]
        }
        result = to_ndarray(payload, adapter="records")
        expected = np.array([[1, 2], [3, 4]])
        np.testing.assert_array_equal(result, expected)

    def test_single_features_format(self):
        payload = {
            "features": {"a": 1, "b": 2}
        }
        result = to_ndarray(payload, adapter="records")
        expected = np.array([[1, 2]])
        np.testing.assert_array_equal(result, expected)

    def test_records_mixed_types(self):
        payload = {
            "records": [
                {"a": 1, "b": "category1", "c": 3.14},
                {"a": 2, "b": "category2", "c": 2.71}
            ]
        }
        result = to_ndarray(payload, adapter="records")
        # Should preserve mixed types as object array
        assert result.shape == (2, 3)
        assert result[0, 0] == 1
        assert result[0, 1] == "category1"
        assert result[0, 2] == 3.14

    def test_records_missing_features_error(self):
        payload = {
            "records": [
                {"a": 1, "b": 2},
                {"a": 3}  # Missing 'b'
            ]
        }
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records")

    def test_records_empty_payload(self):
        payload = {"records": []}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records")

    def test_records_no_records_key(self):
        payload = {"data": [{"a": 1, "b": 2}]}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records")


class TestNdarrayAdapter:
    """Test ndarray format conversion"""

    def test_ndarray_basic(self):
        payload = {
            "ndarray": [[1, 2, 3], [4, 5, 6]]
        }
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[1, 2, 3], [4, 5, 6]])
        np.testing.assert_array_equal(result, expected)

    def test_inputs_format(self):
        payload = {
            "inputs": [[1, 2, 3], [4, 5, 6]]
        }
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[1, 2, 3], [4, 5, 6]])
        np.testing.assert_array_equal(result, expected)

    def test_inputs_single_row(self):
        payload = {
            "inputs": [1, 2, 3]
        }
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[1, 2, 3]])
        np.testing.assert_array_equal(result, expected)

    def test_ndarray_mixed_types(self):
        payload = {
            "ndarray": [[1, "a", 3.14], [2, "b", 2.71]]
        }
        result = to_ndarray(payload, adapter="ndarray")
        assert result.shape == (2, 3)
        assert result[0, 0] == 1
        assert result[0, 1] == "a"

    def test_ndarray_empty_payload(self):
        payload = {"ndarray": []}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="ndarray")

    def test_ndarray_no_ndarray_key(self):
        payload = {"data": [[1, 2, 3]]}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="ndarray")

    def test_ndarray_inconsistent_shapes(self):
        payload = {
            "ndarray": [[1, 2, 3], [4, 5]]  # Different lengths
        }
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="ndarray")


class TestAutoAdapter:
    """Test automatic adapter detection"""

    def test_auto_detects_records(self):
        payload = {
            "records": [{"a": 1, "b": 2}]
        }
        result = to_ndarray(payload, adapter="auto")
        expected = np.array([[1, 2]])
        np.testing.assert_array_equal(result, expected)

    def test_auto_detects_ndarray(self):
        payload = {
            "ndarray": [[1, 2, 3]]
        }
        result = to_ndarray(payload, adapter="auto")
        expected = np.array([[1, 2, 3]])
        np.testing.assert_array_equal(result, expected)

    def test_auto_detects_instances(self):
        payload = {
            "instances": [{"a": 1, "b": 2}]
        }
        result = to_ndarray(payload, adapter="auto")
        expected = np.array([[1, 2]])
        np.testing.assert_array_equal(result, expected)

    def test_auto_detects_features(self):
        payload = {
            "features": {"a": 1, "b": 2}
        }
        result = to_ndarray(payload, adapter="auto")
        expected = np.array([[1, 2]])
        np.testing.assert_array_equal(result, expected)

    def test_auto_defaults_to_records(self):
        # This should fail because unknown format defaults to records
        # but doesn't have the right keys
        payload = {"unknown": "format"}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="auto")


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_invalid_adapter_type(self):
        payload = {"records": [{"a": 1}]}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="invalid")

    def test_empty_payload(self):
        payload = {}
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records")

    def test_none_payload(self):
        with pytest.raises((AdapterError, AttributeError)):
            to_ndarray(None, adapter="records")

    def test_numpy_array_input_passthrough(self):
        # Test that numpy arrays are handled correctly
        payload = {
            "ndarray": np.array([[1, 2, 3], [4, 5, 6]]).tolist()
        }
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[1, 2, 3], [4, 5, 6]])
        np.testing.assert_array_equal(result, expected)

    def test_single_value_expansion(self):
        payload = {
            "inputs": 42
        }
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[42]])
        np.testing.assert_array_equal(result, expected)

    def test_feature_order_with_extra_features(self):
        payload = {
            "records": [{"a": 1, "b": 2, "c": 3, "d": 4}]
        }
        feature_order = ["b", "a"]  # Only select subset
        result = to_ndarray(payload, adapter="records", feature_order=feature_order)
        expected = np.array([[2, 1]])
        np.testing.assert_array_equal(result, expected)

    def test_feature_order_with_missing_features(self):
        payload = {
            "records": [{"a": 1, "b": 2}]
        }
        feature_order = ["a", "b", "c"]  # 'c' is missing
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records", feature_order=feature_order)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear feature order cache before each test."""
    _FEATURE_ORDER_CACHE.clear()
    yield
    _FEATURE_ORDER_CACHE.clear()


class TestInternalFunctions:
    """Test internal helper functions for better coverage."""

    def test_get_cached_feature_order_with_config(self):
        """Test _get_cached_feature_order returns config order when provided."""
        records = [{"b": 1, "a": 2}]
        config_order = ["a", "b"]
        result = _get_cached_feature_order(records, config_order)
        assert result == ["a", "b"]

    def test_get_cached_feature_order_empty_records(self):
        """Test _get_cached_feature_order with empty records."""
        result = _get_cached_feature_order([], None)
        assert result == []

    def test_get_cached_feature_order_caching(self):
        """Test feature order caching behavior."""
        records1 = [{"b": 1, "a": 2}]
        records2 = [{"a": 3, "b": 4}]  # Same features, different order

        result1 = _get_cached_feature_order(records1, None)
        assert frozenset(records1[0].keys()) in _FEATURE_ORDER_CACHE

        result2 = _get_cached_feature_order(records2, None)
        assert result1 == result2 == ["a", "b"]

    def test_get_cached_feature_order_union_features(self):
        """Test feature union across multiple records."""
        records = [
            {"a": 1, "b": 2},
            {"b": 3, "c": 4},
            {"c": 5, "d": 6}
        ]
        result = _get_cached_feature_order(records, None)
        assert result == ["a", "b", "c", "d"]

    def test_records_to_numpy_fast_basic(self):
        """Test _records_to_numpy_fast basic functionality."""
        records = [{"a": 1, "b": "test"}, {"a": 2, "b": "data"}]
        feature_order = ["a", "b"]
        result = _records_to_numpy_fast(records, feature_order)

        assert result.shape == (2, 2)
        assert result[0, 0] == 1
        assert result[0, 1] == "test"
        assert result[1, 0] == 2
        assert result[1, 1] == "data"

    def test_records_to_numpy_fast_empty(self):
        """Test _records_to_numpy_fast with empty records."""
        result = _records_to_numpy_fast([], ["a", "b"])
        assert result.shape == (0, 2)
        assert result.dtype == object

    def test_records_to_numpy_fast_missing_feature(self):
        """Test _records_to_numpy_fast with missing features."""
        records = [{"a": 1}, {"a": 2, "b": 3}]  # First record missing 'b'
        feature_order = ["a", "b"]

        with pytest.raises(AdapterError, match="Record 0 is missing required features"):
            _records_to_numpy_fast(records, feature_order)

    def test_records_to_numpy_fast_none_values(self):
        """Test _records_to_numpy_fast with None values."""
        records = [{"a": None, "b": 2}]
        feature_order = ["a", "b"]
        result = _records_to_numpy_fast(records, feature_order)

        assert result[0, 0] is None
        assert result[0, 1] == 2

    def test_extract_ndarray_data_ndarray_key(self):
        """Test _extract_ndarray_data with ndarray key."""
        payload = {"ndarray": [[1, 2], [3, 4]]}
        result = _extract_ndarray_data(payload)
        expected = np.array([[1, 2], [3, 4]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_extract_ndarray_data_inputs_key(self):
        """Test _extract_ndarray_data with inputs key."""
        payload = {"inputs": [[1, 2], [3, 4]]}
        result = _extract_ndarray_data(payload)
        expected = np.array([[1, 2], [3, 4]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_extract_ndarray_data_direct_list(self):
        """Test _extract_ndarray_data with direct list payload."""
        payload = [[1, 2], [3, 4]]
        result = _extract_ndarray_data(payload)
        expected = np.array([[1, 2], [3, 4]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_extract_ndarray_data_1d_reshape(self):
        """Test _extract_ndarray_data reshapes 1D to 2D."""
        payload = {"ndarray": [1, 2, 3]}
        result = _extract_ndarray_data(payload)
        expected = np.array([[1, 2, 3]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_extract_ndarray_data_no_data(self):
        """Test _extract_ndarray_data with no array data."""
        payload = {"other": "value"}
        with pytest.raises(AdapterError, match="Expected 'ndarray' or 'inputs' field"):
            _extract_ndarray_data(payload)

    def test_extract_ndarray_data_empty_array(self):
        """Test _extract_ndarray_data with empty array."""
        payload = {"ndarray": []}
        with pytest.raises(AdapterError, match="Array data cannot be empty"):
            _extract_ndarray_data(payload)

    def test_extract_records_data_records_key(self):
        """Test _extract_records_data with records key."""
        payload = {"records": [{"a": 1}, {"a": 2}]}
        result = _extract_records_data(payload)
        assert result == [{"a": 1}, {"a": 2}]

    def test_extract_records_data_instances_key(self):
        """Test _extract_records_data with instances key."""
        payload = {"instances": [{"a": 1}, {"a": 2}]}
        result = _extract_records_data(payload)
        assert result == [{"a": 1}, {"a": 2}]

    def test_extract_records_data_features_key(self):
        """Test _extract_records_data with features key."""
        payload = {"features": {"a": 1, "b": 2}}
        result = _extract_records_data(payload)
        assert result == [{"a": 1, "b": 2}]

    def test_extract_records_data_direct_list(self):
        """Test _extract_records_data with direct list."""
        payload = [{"a": 1}, {"a": 2}]
        result = _extract_records_data(payload)
        assert result == [{"a": 1}, {"a": 2}]

    def test_extract_records_data_single_dict(self):
        """Test _extract_records_data with single dict."""
        payload = {"a": 1, "b": 2}
        result = _extract_records_data(payload)
        assert result == [{"a": 1, "b": 2}]

    def test_extract_records_data_dict_with_lists(self):
        """Test _extract_records_data with dict containing lists."""
        payload = {"unknown": [1, 2, 3]}
        with pytest.raises(AdapterError, match="Expected 'records', 'instances', 'features' field"):
            _extract_records_data(payload)

    def test_extract_records_data_empty_dict(self):
        """Test _extract_records_data with empty dict."""
        payload = {}
        with pytest.raises(AdapterError, match="Expected 'records', 'instances', 'features' field"):
            _extract_records_data(payload)

    def test_process_records_to_array_basic(self):
        """Test _process_records_to_array basic functionality."""
        records = [{"a": 1, "b": 2}]
        result = _process_records_to_array(records, ["a", "b"])
        expected = np.array([[1, 2]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_process_records_to_array_not_list(self):
        """Test _process_records_to_array with non-list input."""
        with pytest.raises(AdapterError, match="Records must be a list"):
            _process_records_to_array({"a": 1}, None)

    def test_process_records_to_array_empty(self):
        """Test _process_records_to_array with empty list."""
        with pytest.raises(AdapterError, match="Records list cannot be empty"):
            _process_records_to_array([], None)

    def test_process_records_to_array_auto_feature_order(self):
        """Test _process_records_to_array with auto feature order."""
        records = [{"b": 2, "a": 1}]
        result = _process_records_to_array(records, None)
        expected = np.array([[1, 2]], dtype=object)  # Should be sorted a, b
        np.testing.assert_array_equal(result, expected)

    def test_infer_adapter_type_none(self):
        """Test _infer_adapter_type with None payload."""
        with pytest.raises(AdapterError, match="Payload cannot be None"):
            _infer_adapter_type(None)

    def test_infer_adapter_type_features_non_dict(self):
        """Test _infer_adapter_type with features key but non-dict value."""
        payload = {"features": [1, 2, 3]}  # Not a dict
        # Should not match the features condition
        assert _infer_adapter_type(payload) == "records"  # Falls through to default


class TestAdditionalEdgeCases:
    """Additional edge cases for comprehensive coverage."""

    def test_to_ndarray_list_payload_empty(self):
        """Test to_ndarray with empty list payload."""
        with pytest.raises(AdapterError):
            to_ndarray([])

    def test_to_ndarray_direct_dict_as_records(self):
        """Test direct dict payload treated as single record."""
        payload = {"temperature": 25.5, "humidity": 60.0}
        result = to_ndarray(payload, adapter="records")
        # Should be sorted alphabetically: humidity, temperature
        assert result.shape == (1, 2)
        assert result[0, 0] == 60.0  # humidity first
        assert result[0, 1] == 25.5  # temperature second

    def test_to_ndarray_direct_list_as_records(self):
        """Test direct list payload as records."""
        payload = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = to_ndarray(payload, adapter="records")
        expected = np.array([[1, 2], [3, 4]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_inconsistent_record_features(self):
        """Test records with inconsistent features."""
        payload = {
            "records": [
                {"a": 1, "b": 2, "c": 3},
                {"a": 4, "b": 5}  # Missing 'c'
            ]
        }
        # Should fail when trying to create array with missing features
        with pytest.raises(AdapterError):
            to_ndarray(payload, adapter="records")

    def test_single_value_ndarray(self):
        """Test single scalar value as ndarray."""
        payload = {"inputs": 42}
        result = to_ndarray(payload, adapter="ndarray")
        expected = np.array([[42]], dtype=object)
        np.testing.assert_array_equal(result, expected)

    def test_complex_nested_values(self):
        """Test records with complex nested values."""
        payload = {
            "records": [
                {"id": 1, "data": {"nested": "value"}, "tags": ["a", "b"]},
                {"id": 2, "data": {"nested": "other"}, "tags": ["c", "d"]}
            ]
        }
        result = to_ndarray(payload, adapter="records")
        assert result.shape == (2, 3)
        # Values should be preserved as-is (object dtype)
        assert result[0, 1] == {"nested": "value"}
        assert result[0, 2] == ["a", "b"]