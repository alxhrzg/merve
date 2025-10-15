# Metadata and Versioning Streamlining Plan

## Current Issues

### 1. Version Proliferation
Currently we have **5 different version fields** that are confusing and redundant:
- `version` - Manual config version
- `effective_version` - Computed from git tag or config
- `api_version` - API version (v1, v2)
- `model_version` - Another manual version
- `version_source` - Where version came from

### 2. Manual Configuration Overhead
Too many things that should be automatic are manually set:
- Repository name (should be from git)
- Trained_at timestamp (should be deployed_at and automatic)
- Model metrics (empty and pointless)
- Various versions that won't be updated

### 3. Unclear Metadata Fields
- `taskName` in logs is cryptic (Task-1, Task-2)
- `model_metrics` is always empty
- `model_type` should be `predictor_class`
- Missing git repository name

## Proposed Streamlined Structure

### Configuration File (mlserver.yaml)
```yaml
# Project-level metadata (optional, auto-detected if missing)
project:
    description: "Brief project description"  # Optional
    maintainer: "ML Team"  # Optional

# Classifier definition (required)
classifier:
    name: "rfq-likelihood-features-only"  # Required, URL-safe
    description: "RFQ Likelihood with features only"  # Required

# Server configuration
server:
    host: "0.0.0.0"
    port: 8000
    workers: 1
    log_level: "INFO"

    # NEW: Logger configuration
    logger:
        timestamp: false  # Default: no timestamps
        structured: true  # JSON logging
        show_tasks: false  # Hide Task-1, Task-2 etc

# Predictor configuration (required)
predictor:
    module: "mlserver_predictor"
    class_name: "RFQLikelihoodPredictor"
    init_kwargs: {}

# API configuration
api:
    response_format: "standard"
    endpoints:
        predict: true
        batch_predict: true
        predict_proba: true

# Observability
observability:
    metrics: true
    correlation_ids: true

# Build configuration (optional)
build:
    base_image: "python:3.9-slim"
    registry: "docker.io/myorg"
```

### /info Endpoint Response (Simplified)
```json
{
    "project": "enmacc-ds-rfq-boosting",  // Auto from git repo name
    "classifier": "rfq_likelihood_rfq_features_only",
    "description": "RFQ Likelihood Predicor with RFQ features only",
    "predictor_class": "RFQLikelihoodPredictor",  // renamed from model_type
    "deployed_at": "2025-09-18T10:00:00Z",  // Auto-generated at startup
    "git": {
        "repository": "enmacc-ds-rfq-boosting",  // Git repo name
        "commit": "1307985f",
        "tag": "v0.1.2",  // null if no tag
        "branch": "main",
        "dirty": false
    },
    "mlserver": {  // Info about the wrapper itself
        "version": "2.0.0",  // from pyproject.toml
        "commit": "abc123",  // mlserver git commit
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

### Prediction Response Metadata (Simplified)
```json
{
    "predictions": [...],
    "time_ms": 15.96,
    "predictor_class": "RFQLikelihoodPredictor",
    "metadata": {
        "project": "enmacc-ds-rfq-boosting",  // Auto from git
        "classifier": "rfq_likelihood_rfq_features_only",
        "git_commit": "1307985f",
        "git_tag": "v0.1.2",  // null if no tag
        "deployed_at": "2025-09-18T10:00:00Z",  // Auto at startup
        "mlserver_version": "2.0.0"  // MLServer wrapper version
    }
}
```

## Implementation Steps

### Phase 1: Schema Changes
1. Remove `ClassifierVersion`, `ModelVersion`, `ApiVersion` classes
2. Create simplified `ProjectMetadata` and `ClassifierMetadata`
3. Remove all manual version fields
4. Add automatic git repository detection

### Phase 2: Auto-Detection Implementation
1. Auto-detect git repository name
2. Auto-generate deployed_at timestamp at startup
3. Auto-detect mlserver package version
4. Remove all manual version configurations

### Phase 3: Logger Configuration
1. Add logger settings to ServerConfig
2. Implement timestamp toggle
3. Clarify or remove taskName from async context
4. Make structured logging configurable

### Phase 4: Response Simplification
1. Rename `model` to `predictor_class` in responses
2. Remove `api_version` from metadata
3. Add `mlserver` section with wrapper info
4. Remove empty `model_metrics`

## Breaking Changes

### Configuration File
- Remove `model.version` - Use git tags instead
- Remove `model.trained_at` - Auto-generate deployed_at
- Remove `model.metrics` - Not useful
- Remove `classifier.version` - Use git tags
- Remove `api.version` - Not needed
- Rename `classifier.repository` to auto-detected project name

### API Responses
- `/info` structure simplified
- Metadata in predictions simplified
- Field renames (model_type -> predictor_class)

## Benefits

1. **Reduced Confusion**: Single source of truth (git)
2. **Less Manual Work**: Auto-detection of metadata
3. **Clearer Semantics**: deployed_at vs trained_at
4. **Better Observability**: Configurable logging
5. **Simpler Configuration**: Less fields to manage
6. **Accurate Information**: Auto-detected is always current

## Migration Guide

### Before (mlserver.yaml)
```yaml
classifier:
    name: "my-classifier"
    version: "1.0.0"  # REMOVE
    repository: "my-repo"  # REMOVE

model:
    version: "1.0.0"  # REMOVE
    trained_at: "2025-01-17T10:30:00Z"  # REMOVE
    metrics:  # REMOVE
        accuracy: 0.95

api:
    version: "v1"  # REMOVE
```

### After (mlserver.yaml)
```yaml
classifier:
    name: "my-classifier"
    description: "My classifier description"

# That's it! Everything else is auto-detected
```

## Timeline

- **Week 1**: Schema changes and auto-detection
- **Week 2**: Logger configuration and response updates
- **Week 3**: Testing and migration tools
- **Week 4**: Documentation and rollout

## Backwards Compatibility

- Maintain reading of old config format for 1 version
- Provide migration tool: `mlserver migrate-config`
- Log deprecation warnings for old fields