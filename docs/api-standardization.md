# API Standardization and Flexible Response Support

## Current Issues

1. **No semantic difference between `/predict` and `/batch_predict`**
   - Both endpoints accept the same input (lists of records or 2D arrays)
   - Both return the same response structure
   - `batch_predict` just wraps the request as `PredictRequest`

2. **Response handling bug with complex objects**
   - When predictor returns dict like `{"a": [1,2,3], "b": {"c": [1,2,3]}}`
   - `_to_jsonable` only handles numpy scalars
   - `list(map(_to_jsonable, predictions))` treats dict keys as predictions
   - Results in incorrect output: `['a', 'b']` instead of the full object

3. **Lack of flexibility**
   - Response schema is rigid: `predictions: List[Any]`
   - Cannot handle arbitrary response structures
   - No validation for custom response formats

## Proposed Solution

### 1. Clear Endpoint Semantics

#### `/predict` - Single Record Prediction
- **Input**: Single record/row
  - Records format: `{"payload": {"record": {"feature1": 1.5, "feature2": 2.3}}}`
  - Ndarray format: `{"payload": {"ndarray": [1.5, 2.3, 0.8]}}`
- **Output**: Single prediction or custom object
- **Use case**: Real-time inference for individual samples

#### `/batch_predict` - Batch Prediction
- **Input**: Multiple records/rows
  - Records format: `{"payload": {"records": [{"feature1": 1.5}, {"feature1": 2.1}]}}`
  - Ndarray format: `{"payload": {"ndarray": [[1.5, 2.3], [2.1, 1.7]]}}`
- **Output**: List of predictions or custom batch response
- **Use case**: Bulk processing, offline inference

#### `/predict_proba` - Probability Prediction
- **Input**: Same as `/batch_predict` (always expects multiple records)
- **Output**: Probability matrix (n_samples × n_classes)
- **Use case**: When class probabilities are needed

### 2. Flexible Response Formats

#### Configuration Options

Add to `mlserver.yaml`:
```yaml
api:
  response_format: "standard"  # or "custom" or "passthrough"
  response_validation: true    # Enable/disable response validation
  custom_response_schema:      # Optional: define custom schema
    type: "object"
    properties:
      results:
        type: "array"
      metadata:
        type: "object"
```

#### Response Format Types

1. **Standard Format** (default)
   ```json
   {
     "predictions": [0, 1, 0],
     "time_ms": 12.5,
     "model": "classifier-name",
     "metadata": {...}
   }
   ```

2. **Custom Format** (structured)
   ```json
   {
     "data": {
       "predictions": [...],
       "probabilities": [...],
       "custom_field": {...}
     },
     "time_ms": 12.5,
     "model": "classifier-name",
     "metadata": {...}
   }
   ```

3. **Passthrough Format** (unmodified)
   - Returns exactly what the predictor returns
   - No wrapper, no metadata
   - Use for complete control

### 3. Implementation Changes

#### A. Fix Response Handling

```python
def _to_jsonable(x):
    """Convert any Python object to JSON-serializable format."""
    try:
        import numpy as np
        # Handle numpy arrays
        if isinstance(x, np.ndarray):
            return x.tolist()
        # Handle numpy scalars
        if isinstance(x, np.generic):
            return x.item()
    except ImportError:
        pass

    # Handle pandas objects
    try:
        import pandas as pd
        if isinstance(x, pd.DataFrame):
            return x.to_dict('records')
        if isinstance(x, pd.Series):
            return x.tolist()
    except ImportError:
        pass

    # Handle dictionaries recursively
    if isinstance(x, dict):
        return {k: _to_jsonable(v) for k, v in x.items()}

    # Handle lists/tuples recursively
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(item) for item in x]

    # Return as-is for basic types
    return x
```

#### B. Separate Input Handling

```python
def _prepare_single_input(req: PredictRequest, config: AppConfig):
    """Prepare input for single prediction."""
    # Extract single record from payload
    if "record" in req.payload:
        # Single record format
        return adapter.transform([req.payload["record"]])[0]
    elif "ndarray" in req.payload:
        # Single row array
        arr = req.payload["ndarray"]
        if not isinstance(arr[0], list):
            # Already 1D array
            return np.array(arr)
        else:
            # 2D array with single row
            return np.array(arr[0])
    # Fallback to existing logic for backward compatibility
    return _prepare_input_data(req, config)[0]

def _prepare_batch_input(req: BatchPredictRequest, config: AppConfig):
    """Prepare input for batch prediction."""
    # Existing _prepare_input_data logic
    return _prepare_input_data(PredictRequest(payload=req.payload), config)
```

#### C. Response Format Selection

```python
def _format_response(predictions, config: AppConfig, timing: float, model_name: str):
    """Format response based on configuration."""
    response_format = config.api.get('response_format', 'standard')

    if response_format == 'passthrough':
        # Return predictor output as-is
        return predictions

    # Convert to JSON-serializable format
    json_predictions = _to_jsonable(predictions)

    if response_format == 'custom':
        # Wrap in custom structure
        response = {
            "data": json_predictions,
            "time_ms": timing,
            "model": model_name
        }
        if metadata := getattr(app.state, 'metadata', None):
            response["metadata"] = metadata
        return response

    # Standard format (default)
    # Handle both list and dict predictions appropriately
    if isinstance(json_predictions, dict):
        # For dict responses, include the whole structure
        return {
            "result": json_predictions,
            "predictions": list(json_predictions.values()) if config.api.get('extract_values', False) else None,
            "time_ms": timing,
            "model": model_name,
            "metadata": getattr(app.state, 'metadata', None)
        }
    else:
        # For list responses, use standard format
        return PredictResponse(
            predictions=json_predictions if isinstance(json_predictions, list) else [json_predictions],
            time_ms=timing,
            model=model_name,
            metadata=getattr(app.state, 'metadata', None)
        )
```

### 4. New Schema Definitions

```python
# schemas.py additions

class SinglePredictRequest(BaseModel):
    """Request for single record prediction."""
    payload: Dict[str, Any] = Field(
        description="Single record input. Use 'record' for dict or 'ndarray' for array"
    )

class CustomPredictResponse(BaseModel):
    """Flexible response supporting arbitrary structures."""
    result: Any = Field(description="Prediction result (any structure)")
    predictions: Optional[List[Any]] = Field(None, description="Extracted predictions if applicable")
    time_ms: float = Field(description="Prediction time in milliseconds")
    model: Optional[str] = Field(None, description="Model name")
    metadata: Optional[ClassifierMetadataResponse] = None

class ResponseFormat(str, Enum):
    STANDARD = "standard"
    CUSTOM = "custom"
    PASSTHROUGH = "passthrough"
```

### 5. Configuration Examples

#### Standard ML Classifier
```yaml
api:
  response_format: "standard"
  endpoints:
    predict: true
    batch_predict: true
    predict_proba: true
```

#### Custom Response Structure
```yaml
api:
  response_format: "custom"
  extract_values: false  # Don't extract dict values
  endpoints:
    predict: true
    batch_predict: true
```

#### Complex Output Predictor
```yaml
api:
  response_format: "passthrough"  # Return exactly what predictor returns
  response_validation: false       # Skip validation
  endpoints:
    predict: true
```

### 6. Migration Path

1. **Phase 1**: Add new functionality without breaking changes
   - Keep current endpoints working as-is
   - Add `response_format` configuration
   - Fix `_to_jsonable` to handle complex objects

2. **Phase 2**: Deprecation warnings
   - Warn when using ambiguous inputs
   - Suggest migration to clearer semantics

3. **Phase 3**: Full migration
   - Enforce single vs batch semantics
   - Remove deprecated patterns

## Benefits

1. **Clear semantics**: Single vs batch prediction is explicit
2. **Flexibility**: Support any response structure
3. **Backward compatible**: Existing code continues to work
4. **Validation**: Optional response validation
5. **Performance**: Single predictions don't need array wrapping
6. **Extensibility**: Easy to add new response formats

## Testing Strategy

1. **Unit tests** for `_to_jsonable` with complex objects
2. **Integration tests** for each response format
3. **Backward compatibility** tests
4. **Performance benchmarks** for different formats
5. **Documentation examples** for common use cases