# API Reference

## Overview

MLServer provides a unified REST API for ML model inference without version or classifier names in URLs. All endpoints return JSON responses and support CORS for cross-origin requests.

## Base URL Structure

```
http://<host>:<port>/
```

No versioning or classifier names in paths - clean, unified endpoints.

## Core Endpoints

### Prediction Endpoints

#### `POST /predict`
Single prediction endpoint for individual inference requests.

**Request Body**:
```json
{
  "payload": {
    "records": [...]  // or "ndarray": [...]
  }
}
```

**Input Formats**:
1. **Records Format** (JSON objects):
```json
{
  "payload": {
    "records": [
      {"age": 25, "sex": "male", "fare": 72.5}
    ]
  }
}
```

2. **Ndarray Format** (nested arrays):
```json
{
  "payload": {
    "ndarray": [[25, 1, 72.5]]
  }
}
```

3. **Auto-Detection** (default):
- Automatically detects format based on input structure
- Falls back to configured adapter if ambiguous

**Response**:
```json
{
  "predictions": [0],
  "time_ms": 12.5,
  "metadata": {
    "project": "mlserver-repo",
    "classifier": "catboost-survival",
    "predictor_class": "CatBoostPredictor",
    "predictor_module": "predictor_catboost",
    "config_file": "mlserver.yaml",
    "git_commit": "abc123",
    "git_tag": "v1.0.0",
    "deployed_at": "2025-01-18T10:00:00Z",
    "mlserver_version": "2.0.0"
  }
}
```

**Status Codes**:
- `200`: Success
- `400`: Invalid input
- `422`: Validation error
- `500`: Server error

---


#### `POST /predict_proba`
Probability predictions for classification models.

**Request Body**: Same as `/predict`

**Response**:
```json
{
  "probabilities": [[0.8, 0.2]],
  "classes": [0, 1],
  "time_ms": 14.8,
  "metadata": {
    "project": "mlserver-repo",
    "classifier": "catboost-survival",
    "predictor_class": "CatBoostPredictor",
    "predictor_module": "predictor_catboost",
    "config_file": "mlserver.yaml",
    "git_commit": "abc123",
    "git_tag": "v1.0.0",
    "deployed_at": "2025-01-18T10:00:00Z",
    "mlserver_version": "2.0.0"
  }
}
```

---

### Metadata Endpoints

#### `GET /info`
Complete model and API metadata.

**Response**:
```json
{
  "project": "mlserver-models",
  "classifier": "catboost-survival",
  "description": "Titanic survival prediction model",
  "predictor_class": "CatBoostPredictor",
  "deployed_at": "2025-01-18T10:30:00Z",
  "classifier_repository": {
    "repository": "mlserver-models",
    "commit": "abc123def",
    "tag": "v1.0.0",
    "branch": "main",
    "dirty": false
  },
  "api_service": {
    "version": "2.0.0",
    "commit": "def456",
    "tag": null
  },
  "endpoints": {
    "predict": "/predict",
    "batch_predict": "/batch_predict",
    "predict_proba": "/predict_proba",
    "info": "/info",
    "health": "/healthz",
    "metrics": "/metrics"
  }
}
```

---

### Health & Status Endpoints

#### `GET /healthz`
Basic health check endpoint for liveness probes.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /status`
Detailed status with predictor availability.

**Response**:
```json
{
  "status": "ready",
  "predictor_loaded": true,
  "model_type": "CatBoostPredictor",
  "workers": 4,
  "uptime_seconds": 3600
}
```

---

### Observability Endpoints

#### `GET /metrics`
Prometheus-formatted metrics endpoint.

**Response** (text/plain):
```
# HELP mlserver_request_duration_seconds Request duration
# TYPE mlserver_request_duration_seconds histogram
mlserver_request_duration_seconds_bucket{endpoint="/predict",le="0.1"} 100
mlserver_request_duration_seconds_bucket{endpoint="/predict",le="0.5"} 150
mlserver_request_duration_seconds_sum{endpoint="/predict"} 45.2
mlserver_request_duration_seconds_count{endpoint="/predict"} 200

# HELP mlserver_requests_total Total requests
# TYPE mlserver_requests_total counter
mlserver_requests_total{endpoint="/predict",status="200"} 195
mlserver_requests_total{endpoint="/predict",status="400"} 5

# HELP mlserver_prediction_errors_total Prediction errors
# TYPE mlserver_prediction_errors_total counter
mlserver_prediction_errors_total 5
```

---

### Documentation Endpoints

#### `GET /docs`
Interactive OpenAPI documentation (Swagger UI).

#### `GET /redoc`
Alternative API documentation (ReDoc format).

#### `GET /openapi.json`
OpenAPI schema in JSON format.

---

## Request Headers

### Standard Headers

| Header | Description | Example |
|--------|-------------|---------|
| `Content-Type` | Request body format | `application/json` |
| `Accept` | Response format | `application/json` |
| `X-Request-ID` | Correlation ID for tracking | `abc-123-def` |
| `X-Model-Version` | Request specific model version | `1.0.0` |

### CORS Headers

Automatically handled for cross-origin requests:
- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Methods`
- `Access-Control-Allow-Headers`

---

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "PREDICTION_FAILED",
    "message": "Failed to make prediction",
    "details": "Model expects 3 features, got 2",
    "request_id": "abc-123-def"
  }
}
```

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|------------|
| `INVALID_INPUT` | Malformed request data | 400 |
| `MISSING_FEATURES` | Required features missing | 400 |
| `PREDICTION_FAILED` | Model prediction error | 500 |
| `MODEL_NOT_LOADED` | Predictor not initialized | 503 |
| `RATE_LIMITED` | Too many concurrent requests | 429 |

---

## Rate Limiting

### Concurrency Control

Configured via `api.max_concurrent_requests`:
```yaml
api:
  max_concurrent_requests: 10  # Limit concurrent predictions
```

Response when rate limited:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many concurrent requests",
    "retry_after": 1
  }
}
```

---

## Input Adapters

### Records Adapter
Expects JSON objects with named features:
```python
# Config
api:
  adapter: "records"
  feature_order: ["age", "sex", "fare"]  # Optional ordering

# Request
{"data": [{"age": 25, "sex": "male", "fare": 72.5}]}
```

### Ndarray Adapter
Expects nested arrays:
```python
# Config
api:
  adapter: "ndarray"

# Request
{"data": [[25, 1, 72.5]]}
```

### Auto Adapter (Default)
Automatically detects format:
```python
# Config
api:
  adapter: "auto"  # or omit for default

# Works with both formats
{"data": [{"age": 25}]}  # Detected as records
{"data": [[25, 1]]}      # Detected as ndarray
```

---

## Response Formats

### Successful Prediction
```json
{
  "predictions": [0, 1, 0],
  "model": "catboost-survival",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "abc-123-def"
}
```

### Prediction with Probabilities
```json
{
  "predictions": [0, 1],
  "probabilities": [
    [0.8, 0.2],
    [0.3, 0.7]
  ],
  "classes": [0, 1],
  "model": "catboost-survival",
  "version": "1.0.0"
}
```

### Batch Response
```json
{
  "predictions": [0, 1, 0, 1],
  "batch_size": 4,
  "processing_time_ms": 45,
  "model": "catboost-survival",
  "version": "1.0.0"
}
```

---

## Security

### CORS Configuration

```yaml
server:
  cors:
    enabled: true
    allow_origins: ["*"]
    allow_methods: ["GET", "POST"]
    allow_headers: ["*"]
```

### Request Validation

- Input size limits (configurable)
- Type validation via Pydantic
- Feature validation against expected schema
- Sanitization of string inputs

---

## Performance Optimization

### Caching

Feature ordering is cached for records adapter:
```python
# First request establishes order
{"data": [{"age": 25, "sex": "male"}]}
# Subsequent requests use cached order
```

### Connection Pooling

Keep-alive connections supported:
```bash
curl -H "Connection: keep-alive" http://localhost:8000/predict
```

### Compression

Supports gzip compression:
```bash
curl -H "Accept-Encoding: gzip" http://localhost:8000/info
```

---

## Examples

### Python Client

```python
import requests

# Single prediction
response = requests.post(
    "http://localhost:8000/predict",
    json={
        "data": [{"age": 25, "sex": "male", "fare": 72.5}]
    }
)
print(response.json()["predictions"])

# Batch prediction
response = requests.post(
    "http://localhost:8000/batch_predict",
    json={
        "data": [
            {"age": 25, "sex": "male"},
            {"age": 30, "sex": "female"}
        ]
    }
)
print(response.json()["predictions"])

# Get model info
response = requests.get("http://localhost:8000/info")
print(response.json()["version"])
```

### cURL Examples

```bash
# Single prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"data": [{"age": 25, "sex": "male"}]}'

# Model info
curl http://localhost:8000/info

# Health check
curl http://localhost:8000/healthz

# Metrics
curl http://localhost:8000/metrics
```

### JavaScript/TypeScript

```typescript
// Single prediction
const response = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    data: [{ age: 25, sex: 'male', fare: 72.5 }]
  })
});
const result = await response.json();
console.log(result.predictions);
```

---

## Troubleshooting

### Common Issues

**404 Not Found**
- Ensure no `/v1/` prefix in URL
- Check endpoint spelling
- Verify server is running

**400 Bad Request**
- Validate JSON syntax
- Check feature names match model expectations
- Ensure data format matches adapter configuration

**503 Service Unavailable**
- Model may still be loading
- Check `/status` endpoint
- Review server logs

**429 Too Many Requests**
- Reduce concurrent requests
- Implement client-side rate limiting
- Increase `max_concurrent_requests` setting