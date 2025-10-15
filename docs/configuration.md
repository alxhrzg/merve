# Configuration Guide

> ✅ **Metadata and Versioning System Streamlined!**
>
> The metadata system has been completely overhauled to reduce confusion and eliminate manual configuration.
> All metadata is now automatically detected from your git repository and environment.
>
> **What's Changed:**
> - **Removed redundant version fields** - No more 5 different version types!
> - **Automatic detection** - Git info, deployment timestamps, and project names are auto-detected
> - **Simplified configuration** - Just focus on your predictor and API settings
> - **Cleaner responses** - Streamlined metadata in all API responses
>
> **Key Improvements:**
> - ✅ **Auto-detected from git**: project name, commit hash, tags, branch
> - ✅ **Auto-generated**: deployment timestamps, MLServer version
> - ✅ **New logger config**: Control timestamps, structured logging, task names
> - ✅ **Enhanced metadata**: Shows predictor module, config file, and more
>
> **Migration Guide:**
> 1. **Remove deprecated fields** from your config:
>    - ❌ `model.version`, `model.trained_at`, `model.metrics`
>    - ❌ `classifier.version`, `classifier.repository`
>    - ❌ `api.version`
> 2. **Keep only essential fields**:
>    - ✅ `classifier.name` and `classifier.description`
>    - ✅ Your predictor and API configurations
> 3. **Use git tags** for versioning: `git tag v1.0.0`

## Complete Annotated Example

This comprehensive example shows **ALL** available configuration parameters with detailed annotations:

```yaml
# ============================================================================
# COMPLETE mlserver.yaml - All Available Parameters (with defaults shown)
# ============================================================================

# ----------------------------------------------------------------------------
# SERVER CONFIGURATION
# ----------------------------------------------------------------------------
server:
  title: "ML Server"                    # API title shown in docs (default: "ML Server")
  host: "0.0.0.0"                       # Network interface to bind (default: "0.0.0.0")
  port: 8000                            # Port number 1-65535 (default: 8000)
  log_level: "INFO"                     # Logging level: DEBUG|INFO|WARNING|ERROR (default: "INFO")
  workers: 1                            # Number of worker processes (default: 1, use 1 for K8s)

  # Logger Configuration (NEW - controls log output format)
  logger:
    timestamp: false                     # Include timestamps in logs (default: false)
    structured: true                     # Use structured JSON logging (default: true)
    show_tasks: false                    # Show async task names (default: false)
    format: null                         # Custom log format string (optional)

  # CORS Configuration (optional, disabled by default for security)
  cors:
    allow_origins: []                   # List of allowed origins, empty = CORS disabled (default: [])
    allow_methods: ["GET", "POST"]      # Allowed HTTP methods (default: ["GET", "POST"])
    allow_headers: ["Content-Type"]     # Allowed headers (default: ["Content-Type"])
    allow_credentials: false            # Allow credentials in CORS (default: false)

# ----------------------------------------------------------------------------
# PREDICTOR CONFIGURATION (REQUIRED)
# ----------------------------------------------------------------------------
predictor:
  module: "my_predictor"                # Python module containing predictor (required)
  class_name: "MyPredictor"             # Class name within module (required)
  init_kwargs:                          # Arguments passed to predictor __init__ (optional)
    model_path: "./models/model.pkl"
    config_param: "value"
    threshold: 0.5

# ----------------------------------------------------------------------------
# API CONFIGURATION (REQUIRED)
# ----------------------------------------------------------------------------
api:
  endpoints:                            # Enable/disable specific endpoints
    predict: true                       # POST /predict endpoint (default: true)
    predict_proba: true                 # POST /predict_proba endpoint (default: true)
    # Note: batch_predict removed - /predict handles both single and batch

  # Input/Output Configuration
  adapter: "records"                    # Input format: "records"|"ndarray"|"auto" (default: "records")
  feature_order: null                   # Optional list to enforce feature order, e.g., ["age", "sex"]

  # Response Format Configuration (NEW)
  response_format: "standard"           # Response format type (default: "standard")
                                        # Options:
                                        # - "standard": Traditional format with predictions list
                                        # - "custom": Flexible format with result field for complex objects
                                        # - "passthrough": Return predictor output unmodified
  response_validation: true             # Enable response validation (default: true)
                                        # Set false for complex custom responses
  extract_values: false                 # For dict responses, extract values to list (default: false)

  # Concurrency Control
  thread_safe_predict: false            # Use thread lock during prediction (default: false)
  max_concurrent_predictions: 1         # Max concurrent predictions (default: 1)
                                        # Set to 1 for single model protection in K8s

# ----------------------------------------------------------------------------
# OBSERVABILITY CONFIGURATION
# ----------------------------------------------------------------------------
observability:
  metrics: true                         # Enable Prometheus metrics (default: true)
  metrics_endpoint: "/metrics"          # Metrics endpoint path (default: "/metrics")
  structured_logging: true              # Enable JSON structured logging (default: true)
  log_payloads: false                   # Log request/response payloads (default: false)
                                        # WARNING: May log sensitive data
  correlation_ids: true                 # Generate correlation IDs for tracing (default: true)

# ----------------------------------------------------------------------------
# CLASSIFIER METADATA (SIMPLIFIED - Most fields now auto-detected!)
# ----------------------------------------------------------------------------
classifier:
  name: "my-classifier"                 # Classifier name (required, URL-safe: lowercase + hyphens)
  description: ""                       # Human-readable description (optional)
  # NOTE: version, repository, and other metadata are now auto-detected from git!

# ----------------------------------------------------------------------------
# MODEL METADATA (DEPRECATED - Do not use!)
# ----------------------------------------------------------------------------
# The 'model' section is deprecated. All metadata is now auto-detected:
# - Version comes from git tags
# - Deployment timestamp is auto-generated
# - Project/repository name is detected from git
# - MLServer version is detected from package

# ----------------------------------------------------------------------------
# BUILD CONFIGURATION (OPTIONAL)
# ----------------------------------------------------------------------------
build:
  base_image: "python:3.9-slim"        # Docker base image (default from settings)
  registry: "docker.io/myorg"          # Container registry URL (optional)
  tag_prefix: "ml-models"               # Prefix for container tags (optional)
  include_files:                        # Explicit files to include (optional)
    - "models/"
    - "configs/"
    - "*.py"
  exclude_patterns:                     # Patterns to exclude (optional)
    - "*.pyc"
    - "__pycache__"
    - ".git"
    - "tests/"

# ============================================================================
# MULTI-CLASSIFIER CONFIGURATION (Alternative to single classifier)
# ============================================================================
# Use this structure in mlserver_multi.yaml for multiple models:

# server:                               # Global server settings
#   workers: 4
#   port: 8000
#
# observability:                        # Global observability settings
#   metrics: true
#   structured_logging: true
#
# repository:                           # Repository metadata
#   name: "multi-model-repo"
#   description: "Repository with multiple ML models"
#
# classifiers:                          # Multiple classifier definitions
#   model-a:
#     predictor:
#       module: predictor_a
#       class_name: PredictorA
#     classifier:
#       name: "model-a"
#       # version auto-detected from git tags
#     api:
#       response_format: "standard"
#
#   model-b:
#     predictor:
#       module: predictor_b
#       class_name: PredictorB
#     classifier:
#       name: "model-b"
#       # version auto-detected from git tags
#     api:
#       response_format: "custom"
#
# default_classifier: "model-a"        # Default when none specified
#
# deployment:                           # Deployment configuration
#   strategy: "single"                  # or "multi" for separate services
#   resource_limits:
#     memory: "2Gi"
#     cpu: "1000m"
```

## Overview

MLServer uses YAML configuration files to define server settings, predictor loading, observability, and API behavior. Configuration is validated using Pydantic for type safety and clear error messages.

## Configuration Files

### File Detection Priority

1. **Explicit path**: `ml_server serve /path/to/config.yaml`
2. **Auto-detection** (in order):
   - `mlserver.yaml` (preferred)
   - `config.yaml`
   - `mlserver_multi.yaml` (multi-classifier)
   - Any `*.yaml` with classifier configs

### Configuration Types

- **Single Classifier**: Standard `mlserver.yaml`
- **Multi-Classifier**: `mlserver_multi.yaml` with multiple models
- **Global Settings**: `global_config.yaml` for shared defaults

## Single Classifier Configuration

### Minimal Configuration

```yaml
# mlserver.yaml - Minimal working example
predictor:
  module: my_predictor  # Just the filename!
  class_name: MyPredictor
```

### Complete Configuration

```yaml
# mlserver.yaml - Full example with all options
server:
  title: "Titanic Survival Prediction API"
  description: "ML model for predicting passenger survival"
  host: "0.0.0.0"
  port: 8000
  workers: 4  # Number of processes
  cors:
    enabled: true
    allow_origins: ["*"]
    allow_methods: ["GET", "POST"]
    allow_headers: ["*"]
  timeout: 30  # Request timeout in seconds

predictor:
  module: predictor_catboost  # Simple filename
  class_name: CatBoostPredictor
  init_kwargs:
    model_path: "./models/catboost_model.cbm"
    features_path: "./models/features.json"
    threshold: 0.5

observability:
  metrics: true
  metrics_endpoint: "/metrics"
  structured_logging: true
  log_level: "INFO"
  correlation_ids: true
  log_payloads: false  # Privacy consideration

api:
  adapter: "auto"  # auto|records|ndarray
  feature_order: ["age", "sex", "fare", "pclass"]
  thread_safe_predict: true
  max_concurrent_requests: 10
  endpoints:
    predict: true
    batch_predict: true
    predict_proba: true
    info: true
    healthz: true
    status: true
  version: "v1"

classifier:
  name: "catboost-survival"
  version: "1.0.0"
  repository: "mlserver-models"
  description: "CatBoost model for Titanic survival"

model:
  version: "1.0.0"
  metrics:
    accuracy: 0.94
    precision: 0.92
    recall: 0.89
  trained_at: "2024-01-15T10:30:00Z"
  framework: "catboost"

build:
  base_image: "python:3.9-slim"
  registry: "registry.example.com"
  tag_prefix: "ml-models"
```

## Multi-Classifier Configuration

### Basic Multi-Classifier

```yaml
# mlserver_multi.yaml
classifiers:
  catboost-model:
    predictor:
      module: predictor_catboost
      class_name: CatBoostPredictor
      init_kwargs:
        model_path: "./models/catboost.cbm"
    metadata:
      name: "catboost-model"
      version: "1.0.0"

  randomforest-model:
    predictor:
      module: predictor_rf
      class_name: RandomForestPredictor
      init_kwargs:
        model_path: "./models/rf.pkl"
    metadata:
      name: "randomforest-model"
      version: "2.0.0"

default_classifier: "catboost-model"

# Shared settings for all classifiers
server:
  workers: 4
  port: 8000

observability:
  metrics: true
  structured_logging: true
```

### Advanced Multi-Classifier

```yaml
# mlserver_multi_advanced.yaml
global_settings:
  server:
    workers: 4
    cors:
      enabled: true
  observability:
    metrics: true
    structured_logging: true
  api:
    max_concurrent_requests: 10

classifiers:
  production:
    predictor:
      module: predictor_prod
      class_name: ProductionModel
    metadata:
      name: "production"
      version: "3.0.0"
      stage: "production"
    api:
      thread_safe_predict: true

  staging:
    predictor:
      module: predictor_staging
      class_name: StagingModel
    metadata:
      name: "staging"
      version: "3.1.0-rc1"
      stage: "staging"
    api:
      thread_safe_predict: false  # Testing new async mode

  experimental:
    predictor:
      module: predictor_exp
      class_name: ExperimentalModel
    metadata:
      name: "experimental"
      version: "4.0.0-alpha"
      stage: "experimental"
    server:
      workers: 1  # Limited resources for experimental

default_classifier: "production"
```

## Configuration Sections

### Server Configuration

```yaml
server:
  # API metadata
  title: "API Title"
  description: "API Description"
  version: "1.0.0"

  # Network settings
  host: "0.0.0.0"  # Bind address
  port: 8000       # Port number

  # Worker configuration
  workers: 4       # Number of processes (not threads!)

  # CORS settings
  cors:
    enabled: true
    allow_origins: ["*"]
    allow_methods: ["GET", "POST", "OPTIONS"]
    allow_headers: ["*"]
    allow_credentials: false
    max_age: 3600

  # Timeouts
  timeout: 30           # Request timeout (seconds)
  shutdown_timeout: 10  # Graceful shutdown timeout

  # Advanced
  reload: false    # Auto-reload on code changes (dev only)
  access_log: true # Enable access logging
```

### Predictor Configuration

```yaml
predictor:
  # Module loading (intelligent resolution)
  module: predictor_name  # Simple filename
  # OR
  module: path/to/predictor.py  # Relative path
  # OR
  module: package.module.predictor  # Full module path

  # Class configuration
  class_name: PredictorClass

  # Initialization arguments
  init_kwargs:
    model_path: "./model.pkl"
    config:
      threshold: 0.5
      batch_size: 32
    custom_param: "value"
```

#### Module Resolution

The system intelligently resolves module paths:

1. **Simple name** (`predictor_catboost`):
   - Looks for `predictor_catboost.py` in config directory
   - Adds config directory to Python path

2. **Relative path** (`models/predictor.py`):
   - Resolves relative to config file location
   - Strips `.py` extension

3. **Full module** (`mlserver.predictors.catboost`):
   - Uses standard Python import

### Observability Configuration

```yaml
observability:
  # Metrics
  metrics: true
  metrics_endpoint: "/metrics"
  metrics_prefix: "mlserver_"

  # Logging
  structured_logging: true  # JSON format
  log_level: "INFO"        # DEBUG|INFO|WARNING|ERROR
  log_file: null           # Optional file output

  # Request tracking
  correlation_ids: true    # Generate request IDs
  log_payloads: false     # Log request/response (privacy!)

  # Performance monitoring
  profile: false          # Enable profiling
  trace_sampling: 0.1     # Trace 10% of requests
```

### API Configuration

```yaml
api:
  # Input adapter
  adapter: "auto"  # auto|records|ndarray

  # Feature handling
  feature_order: ["feat1", "feat2"]  # Explicit ordering
  validate_features: true            # Check required features

  # Concurrency
  thread_safe_predict: true          # Lock during prediction
  max_concurrent_requests: 10        # Rate limiting

  # Response format (NEW)
  response_format: "standard"         # standard|custom|passthrough
  response_validation: true            # Enable/disable validation
  extract_values: false               # Extract dict values to list

  # Endpoints control
  endpoints:
    predict: true
    batch_predict: true
    predict_proba: true
    info: true
    healthz: true
    status: true
    metrics: true
    docs: true

  # Versioning
  version: "v1"  # API version for metadata

  # Request limits
  max_request_size: "100MB"
  max_batch_size: 1000
```

#### Response Formats

The `response_format` configuration controls how predictions are formatted:

1. **`standard`** (default): Traditional format with predictions list
   ```json
   {
     "predictions": [0, 1, 0],
     "time_ms": 12.5,
     "model": "classifier",
     "metadata": {...}
   }
   ```

2. **`custom`**: Flexible format for complex responses
   ```json
   {
     "result": {
       "a": [1, 2, 3],
       "b": {"c": [4, 5]}
     },
     "time_ms": 16.4,
     "model": "CustomPredictor",
     "metadata": {...}
   }
   ```

3. **`passthrough`**: Return predictor output unmodified
   - No wrapper or metadata
   - Complete control over response structure
   - Useful for legacy systems or special requirements

Example configurations:

```yaml
# For complex dictionary responses
api:
  response_format: "custom"
  extract_values: false  # Keep dict structure intact

# For legacy compatibility
api:
  response_format: "passthrough"
  response_validation: false  # Skip validation

# Standard ML classifier (default)
api:
  response_format: "standard"
  extract_values: true  # Extract dict values to list
```

### Classifier Metadata

```yaml
classifier:
  name: "model-name"
  version: "1.0.0"
  repository: "ml-models"
  description: "Model description"
  tags: ["production", "nlp", "transformer"]
  author: "Data Science Team"

  # Additional metadata
  framework: "pytorch"
  task: "classification"
  domain: "finance"

  # Performance specs
  inference_time_ms: 50
  memory_mb: 512
  gpu_required: false
```

### Model Information

```yaml
model:
  version: "1.0.0"

  # Training metadata
  trained_at: "2024-01-15T10:30:00Z"
  training_data: "dataset_v3"

  # Model metrics
  metrics:
    accuracy: 0.94
    precision: 0.92
    recall: 0.89
    f1_score: 0.905
    auc_roc: 0.96

  # Feature importance
  features:
    important: ["age", "income", "education"]
    importance_scores:
      age: 0.45
      income: 0.35
      education: 0.20
```

### Build Configuration

```yaml
build:
  # Docker settings
  base_image: "python:3.9-slim"
  registry: "registry.example.com"
  repository: "ml-models"

  # Tagging
  tag_prefix: "mlserver"
  tag_suffix: null
  latest: true  # Also tag as latest

  # Build options
  no_cache: false
  platform: "linux/amd64"

  # Dependencies
  requirements_file: "requirements.txt"
  system_packages: ["libgomp1", "libatlas-base-dev"]
```

## Environment Variables

Override configuration via environment variables:

```bash
# Server settings
export MLSERVER_HOST="0.0.0.0"
export MLSERVER_PORT="8080"
export MLSERVER_WORKERS="8"

# Observability
export MLSERVER_METRICS="true"
export MLSERVER_LOG_LEVEL="DEBUG"

# API settings
export MLSERVER_MAX_CONCURRENT_REQUESTS="20"

# Run server
ml_server serve
```

## CLI Overrides

Command-line arguments override both config and environment:

```bash
# Override port
ml_server serve --port 9000

# Override workers
ml_server serve --workers 8

# Select classifier from multi-config
ml_server serve mlserver_multi.yaml --classifier staging

# Multiple overrides
ml_server serve \
  --port 9000 \
  --workers 8 \
  --log-level DEBUG \
  --no-metrics
```

## Global Configuration

Create `global_config.yaml` for shared settings:

```yaml
# global_config.yaml
server:
  workers: 4
  cors:
    enabled: true

observability:
  metrics: true
  structured_logging: true
  log_level: "INFO"

api:
  thread_safe_predict: true
  max_concurrent_requests: 10
```

Reference in classifier configs:

```yaml
# mlserver.yaml
global_config: "./global_config.yaml"

predictor:
  module: my_predictor
  class_name: MyPredictor

# Inherits all global settings
```

## Configuration Validation

### Schema Validation

All configurations are validated using Pydantic:

```python
# Invalid config example
server:
  port: "not_a_number"  # Error: port must be integer
  workers: -1           # Error: workers must be positive
```

Error message:
```
Configuration error:
  - server.port: value is not a valid integer
  - server.workers: ensure this value is greater than 0
```

### Required Fields

Minimal required configuration:
```yaml
predictor:
  module: <module_name>
  class_name: <class_name>
```

### Type Checking

Configuration types are enforced:
- Integers: `port`, `workers`, `timeout`
- Booleans: `metrics`, `structured_logging`
- Strings: `module`, `class_name`, `log_level`
- Lists: `allow_origins`, `allow_methods`
- Dictionaries: `init_kwargs`, `metrics`

## Configuration Patterns

### Development Configuration

```yaml
# mlserver.dev.yaml
server:
  reload: true  # Auto-reload
  workers: 1    # Single worker for debugging

observability:
  log_level: "DEBUG"
  log_payloads: true  # See all requests

api:
  thread_safe_predict: false  # Faster for single worker
```

### Production Configuration

```yaml
# mlserver.prod.yaml
server:
  workers: 8
  timeout: 60

observability:
  metrics: true
  structured_logging: true
  log_level: "WARNING"
  log_payloads: false  # Privacy

api:
  thread_safe_predict: true
  max_concurrent_requests: 100
  validate_features: true
```

### Testing Configuration

```yaml
# mlserver.test.yaml
server:
  port: 0  # Random port
  workers: 2

predictor:
  module: mock_predictor
  class_name: MockPredictor

observability:
  metrics: false  # Disable for tests
  log_level: "ERROR"
```

## Troubleshooting

### Common Issues

**Module not found**:
```yaml
predictor:
  module: predictor  # Make sure predictor.py exists
  # OR use full path
  module: /absolute/path/to/predictor.py
```

**Class not found**:
```yaml
predictor:
  class_name: Predictor  # Check exact class name
  # Case sensitive!
```

**Init kwargs error**:
```yaml
predictor:
  init_kwargs:
    model_path: "./model.pkl"  # Check file exists
    # Paths are relative to config file
```

### Debugging Configuration

Enable debug logging:
```bash
ml_server serve --log-level DEBUG
```

Validate configuration:
```bash
ml_server validate mlserver.yaml
```

Print resolved configuration:
```bash
ml_server serve --print-config
```