# mlserver-fastapi-wrapper

Wrap any Python predictor class into a production-ready FastAPI inference API using a YAML configuration file. No boilerplate, no framework lock-in!

## What This Does

You have a Python class with `predict()` and/or `predict_proba()` methods. This tool:

1. Wraps it in a FastAPI server with `/predict` and `/predict_proba` endpoints
2. Adds Prometheus metrics, structured logging, correlation IDs
3. Handles input validation and format conversion (records/JSON or numpy arrays)
4. Provides Docker containerization with hierarchical versioning
5. Generates GitHub Actions CI/CD workflows for automated builds

Configure everything in `mlserver.yaml` - no code changes required.

## Installation

```bash
pip install git+https://github.com/alxhrzg/merve.git
```

Or for development:

```bash
git clone https://github.com/alxhrzg/merve.git
cd merve
pip install -e ".[test]"
```

## Quick Start

### 1. Initialize Project

```bash
# Create mlserver.yaml, predictor skeleton, and GitHub Actions workflow
mlserver init

# Or initialize without GitHub Actions
mlserver init --no-github
```

This creates:
- `mlserver.yaml` - Configuration file
- `<classifier>_predictor.py` - Python predictor skeleton
- `.github/workflows/ml-classifier-container-build.yml` - CI/CD workflow

### 2. Implement Your Predictor

Edit the generated predictor file (or use your existing predictor class):

```python
# my_predictor.py
import joblib
import numpy as np

class MyPredictor:
    def __init__(self, model_path: str, **kwargs):
        # Load model once, kept in memory
        self.model = joblib.load(model_path)

    def predict(self, data):
        # data: list of dicts [{feature1: val1, ...}] or numpy array
        return self.model.predict(data)

    def predict_proba(self, data):
        return self.model.predict_proba(data)
```

### 3. Configure mlserver.yaml

```yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 1

predictor:
  module: my_predictor
  class_name: MyPredictor
  init_kwargs:
    model_path: "./model.pkl"

classifier:
  name: "my-classifier"
  version: "1.0.0"

api:
  adapter: auto  # auto-detects records vs ndarray
  endpoints:
    predict: true
    predict_proba: true

observability:
  metrics: true
  structured_logging: true
  correlation_ids: true
```

### 4. Start Server

```bash
mlserver serve
# or: mlserver serve path/to/mlserver.yaml
```

Server runs at http://localhost:8000

### 5. Make Predictions

```bash
# Single prediction
curl -X POST http://localhost:8000/v1/my-classifier/predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [{"feature1": 1.0, "feature2": 2.0}]}'

# Batch predictions
curl -X POST http://localhost:8000/v1/my-classifier/predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [
    {"feature1": 1.0, "feature2": 2.0},
    {"feature1": 3.0, "feature2": 4.0}
  ]}'

# Probabilities
curl -X POST http://localhost:8000/v1/my-classifier/predict_proba \
  -H "Content-Type: application/json" \
  -d '{"instances": [{"feature1": 1.0, "feature2": 2.0}]}'
```

## Core Concepts

### Predictor Class

Any Python class with these methods:

```python
class YourPredictor:
    def __init__(self, **init_kwargs):
        # Arguments from mlserver.yaml predictor.init_kwargs
        pass

    def predict(self, data):
        # data: list of dicts or numpy array
        # return: numpy array of predictions
        pass

    def predict_proba(self, data):
        # Optional: return probability distributions
        pass
```

### Input Formats

The API accepts two input formats:

**Records (list of dicts):**
```json
{
  "instances": [
    {"age": 25, "income": 50000},
    {"age": 30, "income": 60000}
  ]
}
```

**ndarray (nested lists):**
```json
{
  "instances": [[25, 50000], [30, 60000]]
}
```

Set `api.adapter: auto` to auto-detect, or use `records`/`ndarray` to enforce a format.

### Process-Based Scaling

`server.workers: N` spawns N separate processes, each with its own model copy. This is container-friendly and avoids Python GIL issues. Use one worker per CPU core.

### Observability

Built-in observability features:

- **Prometheus metrics** at `/metrics` - request counts, latencies, prediction distributions
- **Structured JSON logging** - machine-parseable logs with context
- **Correlation IDs** - trace requests through your system
- **Health checks** at `/healthz` and `/info`

## Containerization

### Build Container

```bash
mlserver build --classifier my-classifier
```

This:
1. Generates a Dockerfile
2. Installs dependencies from `build.requirements` in mlserver.yaml
3. Copies your code and artifacts
4. Builds a Docker image

### Hierarchical Versioning

Tag your releases with hierarchical tags that track both classifier and MLServer versions:

```bash
# Create version tag (patch/minor/major)
mlserver tag patch --classifier my-classifier

# Produces tag: my-classifier-v1.0.1-mlserver-abc123d
# Format: <classifier>-v<version>-mlserver-<mlserver-commit>
```

Push tags to trigger GitHub Actions builds:

```bash
git push --tags
```

The workflow automatically builds and publishes containers to GitHub Container Registry (GHCR).

### Run Container

```bash
docker run -p 8000:8000 my-classifier:latest
```

## Multi-Classifier Setup

Serve multiple models from a single repository:

```yaml
server:
  host: 0.0.0.0
  port: 8000

classifiers:
  model-a:
    predictor:
      module: predictor_a
      class_name: PredictorA
      init_kwargs:
        model_path: "./models/model_a.pkl"
    classifier:
      name: "model-a"
      version: "1.0.0"

  model-b:
    predictor:
      module: predictor_b
      class_name: PredictorB
      init_kwargs:
        model_path: "./models/model_b.pkl"
    classifier:
      name: "model-b"
      version: "2.0.0"
```

Start specific classifier:
```bash
mlserver serve --classifier model-a
```

Build specific classifier:
```bash
mlserver build --classifier model-a
```

## CLI Commands

```bash
# Initialize project with mlserver.yaml and GitHub Actions
mlserver init

# Start server
mlserver serve [config.yaml]

# Show version info
mlserver version [--json]

# Create hierarchical version tag
mlserver tag patch|minor|major --classifier <name>

# Build Docker container
mlserver build --classifier <name>

# Push to registry
mlserver push --classifier <name> --registry <url>

# List built images
mlserver images

# Remove built images
mlserver clean --classifier <name>
```

## Examples

See `examples/` directory:

- **example_titanic_manual_setup/** - Complete single-classifier example with CatBoost
- **example_titanic_manual_multi_classifier_setup/** - Multi-classifier repository
- **example_titanic_raw/** - Jupyter notebook automation

Each example includes:
- Training script
- Predictor implementation
- mlserver.yaml configuration
- Test requests
- Docker setup

## Configuration Reference

### Server Section
```yaml
server:
  title: "API Title"       # OpenAPI title
  host: 0.0.0.0           # Bind address
  port: 8000              # Port
  log_level: INFO         # DEBUG|INFO|WARNING|ERROR
  workers: 1              # Number of processes
  cors:
    allow_origins: ["*"]  # CORS origins
```

### Predictor Section
```yaml
predictor:
  module: my_module              # Python module path
  class_name: MyPredictor        # Class name to instantiate
  init_kwargs:                   # Passed to __init__()
    model_path: "./model.pkl"
    any_other_arg: value
```

### API Section
```yaml
api:
  version: "v1"                  # API version (metadata only)
  adapter: auto                  # auto|records|ndarray
  feature_order: [col1, col2]    # Column order for records
  thread_safe_predict: false     # Lock predictions (if needed)
  endpoints:
    predict: true                # Enable /predict
    predict_proba: true          # Enable /predict_proba
```

### Observability Section
```yaml
observability:
  metrics: true               # Prometheus metrics
  metrics_endpoint: "/metrics"
  structured_logging: true    # JSON logs
  log_payloads: false        # Log request/response data
  correlation_ids: true      # Generate correlation IDs
```

### Build Section
```yaml
build:
  base_image: "python:3.11-slim"
  requirements:                # Additional pip packages
    - "catboost>=1.2"
    - "scikit-learn>=1.7"
  registry: "my-registry.com"  # Container registry
  tag_prefix: "ml-models"      # Image name prefix
```

## GitHub Actions CI/CD

When you run `mlserver init`, it creates a GitHub Actions workflow that:

1. Triggers on hierarchical tags (`*-v*-mlserver-*`)
2. Parses the tag to extract versions
3. Installs MLServer at the specified commit
4. Builds the Docker container
5. Tests the container (health checks)
6. Pushes to GitHub Container Registry

The workflow ensures reproducible builds by pinning MLServer to the exact commit used during tagging.

## Workflow Version Compatibility

The tool validates that your GitHub Actions workflow is compatible with your MLServer version. If you see warnings:

```bash
⚠ Workflow version mismatch! File has v1.0, but current MLServer expects v2.0
Regenerate with: mlserver init-github --force
```

Regenerate the workflow:
```bash
mlserver init-github --force
```

## Testing

```bash
# Run all tests
pytest tests/ --cov=mlserver

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Load testing
cd tests/load
locust -f locustfile.py --host http://localhost:8000
```

## Monitoring

Example Prometheus + Grafana setup in `monitoring/`:

```bash
# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana at http://localhost:3000
# Default credentials: admin/admin
```

Pre-built dashboard shows:
- Request rate and latencies
- Prediction distributions
- Error rates
- Resource usage

## Requirements

- Python 3.9+
- Docker (for containerization)
- Git (for versioning)

## Architecture

```
Request → FastAPI → InputAdapter → Predictor.predict() → OutputFormatter → Response
                                         ↓
                                   Prometheus Metrics
                                   Structured Logs
```

Components:

- **FastAPI Server** - HTTP layer with OpenAPI docs
- **Input Adapters** - Convert records/ndarray to predictor format
- **Predictor** - Your ML model wrapper (any Python class)
- **Metrics** - Prometheus instrumentation
- **Logger** - Structured JSON logging with correlation IDs

## Common Patterns

### Feature Preprocessing

```python
class MyPredictor:
    def __init__(self, model_path: str, preprocessor_path: str):
        self.model = joblib.load(model_path)
        self.preprocessor = joblib.load(preprocessor_path)

    def predict(self, data):
        # data is list of dicts
        df = pd.DataFrame(data)
        X = self.preprocessor.transform(df)
        return self.model.predict(X)
```

### Model Ensembles

```python
class EnsemblePredictor:
    def __init__(self, model_paths: list):
        self.models = [joblib.load(p) for p in model_paths]

    def predict(self, data):
        predictions = [m.predict(data) for m in self.models]
        return np.mean(predictions, axis=0)
```

### Custom Validation

```python
class ValidatingPredictor:
    def predict(self, data):
        if not isinstance(data, list):
            raise ValueError("Expected list of records")

        required_features = ["age", "income"]
        for record in data:
            missing = [f for f in required_features if f not in record]
            if missing:
                raise ValueError(f"Missing features: {missing}")

        return self.model.predict(data)
```

## Development

```bash
# Clone repository
git clone https://github.com/alxhrzg/merve.git
cd merve

# Install in development mode
pip install -e ".[test]"

# Run tests
pytest

# Format code
black mlserver/
isort mlserver/

# Type checking
mypy mlserver/
```

## Troubleshooting

### Server won't start

Check `mlserver.yaml` syntax:
```bash
python -c "import yaml; yaml.safe_load(open('mlserver.yaml'))"
```

Validate configuration:
```bash
mlserver version  # Should show no errors
```

### Import errors

Ensure your predictor module is in Python path:
```python
# In mlserver.yaml, use full module path:
predictor:
  module: my_package.my_module.predictor
  class_name: MyPredictor
```

Or run from parent directory:
```bash
cd /path/to/parent
mlserver serve path/to/project/mlserver.yaml
```

### Memory issues

Reduce worker count:
```yaml
server:
  workers: 1  # Each worker loads full model
```

Use model compression or quantization to reduce memory footprint.

### Prediction errors

Enable payload logging (temporarily):
```yaml
observability:
  log_payloads: true  # See exact request/response data
```

Check logs for validation errors and data format issues.

## Project Status

This tool is actively maintained and used in production. Features are stable but the API may evolve. Pin your version:

```bash
pip install git+https://github.com/alxhrzg/merve.git@v0.3.1
```

## License

[Your License Here]

## Contributing

Contributions welcome. Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

- Issues: https://github.com/alxhrzg/merve/issues
- Examples: See `examples/` directory
- Configuration: See `mlserver.yaml` examples

## Alternatives

If this tool doesn't fit your needs, consider:

- **MLflow Models** - Full ML lifecycle management platform
- **BentoML** - Model serving with advanced features
- **TorchServe** - PyTorch-specific serving
- **TensorFlow Serving** - TensorFlow-specific serving
- **Ray Serve** - Distributed serving with Ray

This tool focuses on simplicity: wrap any Python predictor with minimal configuration. No framework lock-in, no complex deployment patterns.
