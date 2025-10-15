
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Sequence
import numpy as np
import pandas as pd


class AdapterError(ValueError):
    pass


# Global cache for feature orderings to improve performance
# LRU-style cache with size limit to prevent unbounded memory growth
from collections import OrderedDict

_FEATURE_ORDER_CACHE: OrderedDict[frozenset, List[str]] = OrderedDict()
_CACHE_MAX_SIZE = 100  # Maximum number of cached feature orderings


def _get_cached_feature_order(records: List[Dict], config_order: Optional[List[str]] = None) -> List[str]:
    """Get feature order with caching for performance optimization.

    Uses LRU cache with size limit to prevent memory issues while maintaining performance.
    """
    # Use explicit feature order if provided
    if config_order:
        return config_order

    if not records:
        return []

    # Create cache key from feature set of first record
    first_record_features = frozenset(records[0].keys())

    # Check if in cache and move to end (most recently used)
    if first_record_features in _FEATURE_ORDER_CACHE:
        _FEATURE_ORDER_CACHE.move_to_end(first_record_features)
        return _FEATURE_ORDER_CACHE[first_record_features]

    # Compute union of all features across all records
    all_features = {feature for record in records for feature in record.keys()}
    feature_order = sorted(all_features)

    # Add to cache with LRU eviction if needed
    if len(_FEATURE_ORDER_CACHE) >= _CACHE_MAX_SIZE:
        # Remove least recently used item (first item in OrderedDict)
        _FEATURE_ORDER_CACHE.popitem(last=False)

    _FEATURE_ORDER_CACHE[first_record_features] = feature_order
    return feature_order


def clear_feature_cache() -> None:
    """Clear the feature order cache. Useful for memory management in long-running services."""
    global _FEATURE_ORDER_CACHE
    _FEATURE_ORDER_CACHE.clear()


def get_cache_info() -> Dict[str, Any]:
    """Get information about the feature order cache for monitoring."""
    return {
        "size": len(_FEATURE_ORDER_CACHE),
        "max_size": _CACHE_MAX_SIZE,
        "cache_keys": list(_FEATURE_ORDER_CACHE.keys())[:10]  # First 10 keys for debugging
    }


def _records_to_numpy_fast(records: List[Dict], feature_order: List[str]) -> np.ndarray:
    """Convert records to numpy array with vectorized operations for better performance.

    Args:
        records: List of dictionaries containing features
        feature_order: List of feature names in the desired order

    Returns:
        numpy array with shape (n_records, n_features)

    Raises:
        AdapterError: If records are missing required features or exceed size limits
    """
    if not records:
        return np.empty((0, len(feature_order)), dtype=object)

    # Input validation: Check size limits to prevent DoS
    MAX_RECORDS = 10000
    MAX_FEATURES = 1000

    if len(records) > MAX_RECORDS:
        raise AdapterError(f"Too many records: {len(records)} exceeds limit of {MAX_RECORDS}")
    if len(feature_order) > MAX_FEATURES:
        raise AdapterError(f"Too many features: {len(feature_order)} exceeds limit of {MAX_FEATURES}")

    # Validate that all records have all required features
    for i, record in enumerate(records):
        missing_features = [f for f in feature_order if f not in record]
        if missing_features:
            raise AdapterError(
                f"Record {i} is missing required features: {missing_features}"
            )

    # Vectorized approach: Extract all values at once for better performance
    # This is more efficient than nested loops for larger datasets
    result = np.array([
        [record.get(feature, None) for feature in feature_order]
        for record in records
    ], dtype=object)

    return result


def _infer_adapter_type(payload: dict) -> str:
    """Infer adapter type from payload structure using heuristics."""
    if payload is None:
        raise AdapterError("Payload cannot be None")

    # Check for records format indicators
    if "instances" in payload or "records" in payload:
        return "records"

    # Check for single features object
    if "features" in payload and isinstance(payload["features"], dict):
        return "records"

    # Check for ndarray format indicators
    if "ndarray" in payload or isinstance(payload.get("inputs"), list):
        return "ndarray"

    # Default to records format
    return "records"


def _extract_ndarray_data(payload: dict) -> np.ndarray:
    """Extract and validate ndarray data from payload."""
    # Try different keys for array data
    array_data = payload.get("ndarray")
    if array_data is None:
        array_data = payload.get("inputs")
        if array_data is None and isinstance(payload, list):
            array_data = payload

    if array_data is None:
        raise AdapterError(
            "Expected 'ndarray' or 'inputs' field in payload, or a direct list for ndarray adapter"
        )

    # Check for empty arrays
    if not array_data:
        raise AdapterError("Array data cannot be empty")

    # Convert to numpy array and ensure 2D shape
    try:
        arr = np.asarray(array_data, dtype=object)
    except ValueError as e:
        raise AdapterError(f"Invalid array data: {e}")

    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    return arr


def _extract_records_data(payload: dict) -> List[Dict]:
    """Extract records data from various payload formats."""
    # Try different keys for records data
    if "records" in payload:
        records = payload["records"]
    elif "instances" in payload:
        records = payload["instances"]
    elif "features" in payload and isinstance(payload["features"], dict):
        records = [payload["features"]]
    elif isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and len(payload) > 0:
        # If payload has unknown keys but contains data, be more strict
        # Only treat as a single record if it looks like actual record data (no list values)
        has_list_values = any(isinstance(v, list) for v in payload.values())
        if has_list_values:
            # Looks like it should have proper keys but doesn't
            raise AdapterError(
                "Expected 'records', 'instances', 'features' field in payload, "
                "or a direct list/dict for records adapter"
            )
        else:
            # Treat entire dict as single record
            records = [payload]
    else:
        raise AdapterError(
            "Expected 'records', 'instances', 'features' field in payload, "
            "or a direct list/dict for records adapter"
        )

    return records


def _process_records_to_array(records: List[Dict], feature_order: Optional[List[str]], adapter_type: str = "records") -> np.ndarray:
    """Convert records list to numpy array.

    For records adapter: feature_order is optional - if not provided,
                        uses keys from records to preserve column names
    For ndarray adapter: feature_order is required to map positions to names
    """
    if not isinstance(records, list):
        raise AdapterError("Records must be a list")

    if not records:
        raise AdapterError("Records list cannot be empty")

    # Use cached feature ordering for performance
    resolved_feature_order = _get_cached_feature_order(records, feature_order)

    # Convert directly to numpy for better performance
    return _records_to_numpy_fast(records, resolved_feature_order)


def to_ndarray(
    payload: dict,
    adapter: str = "auto",
    feature_order: Optional[List[str]] = None,
) -> np.ndarray:
    """Convert common JSON payload formats to a numpy 2D array.

    Supported formats:
    - {"records": [{feature: value, ...}, ...]}
    - {"instances": [{feature: value, ...}, ...]}  # alias for records
    - {"features": {feature: value, ...}}         # single record
    - {"ndarray": [[...], [...]]}
    - {"inputs": [[...], [...]]} or "inputs": [...]
    - Direct list/dict payloads

    Args:
        payload: Input data in various JSON formats
        adapter: Conversion strategy ("auto", "records", "ndarray")
        feature_order: Optional explicit feature ordering for records

    Returns:
        2D numpy array ready for model prediction
    """
    import logging
    logger = logging.getLogger(__name__)

    # Debug logging
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"to_ndarray called with adapter='{adapter}', payload type={type(payload)}")
        if isinstance(payload, dict):
            logger.debug(f"Payload keys: {list(payload.keys())}")
            # Log first few values for each key
            for key in list(payload.keys())[:3]:
                value = payload[key]
                if isinstance(value, list) and len(value) > 0:
                    logger.debug(f"  {key}: {value[:min(2, len(value))]}... (length: {len(value)})")
                else:
                    logger.debug(f"  {key}: {value}")
        else:
            logger.debug(f"Payload content: {payload}")
        logger.debug(f"Feature order: {feature_order}")

    # Validate payload is not None or empty
    if payload is None:
        raise AdapterError("Payload cannot be None")

    if not payload and not isinstance(payload, list):
        raise AdapterError("Payload cannot be empty. Received: " + str(type(payload)))

    if adapter == "auto":
        adapter = _infer_adapter_type(payload)

    if adapter == "ndarray":
        return _extract_ndarray_data(payload)
    elif adapter == "records":
        records = _extract_records_data(payload)
        return _process_records_to_array(records, feature_order, adapter_type=adapter)
    else:
        raise AdapterError(f"Unknown adapter type: '{adapter}'. Use 'records', 'ndarray', or 'auto'.")
