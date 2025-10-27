# Development Guide

## Environment Setup

### Prerequisites
- Python 3.9+
- Docker (optional, for container builds)
- Git
- Virtual environment tool (venv/conda)

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/alxhrzg/fastapi-mlserver-wrapper.git
cd fastapi-mlserver-wrapper

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify setup
pytest
```

## Project Structure

```
fastapi-mlserver-wrapper/
├── mlserver/               # Core package
│   ├── __init__.py
│   ├── cli.py             # Classic CLI
│   ├── cli_v2.py          # Modern Typer CLI
│   ├── server.py          # FastAPI application
│   ├── config.py          # Configuration management
│   ├── adapters.py        # Input adapters
│   ├── predictor_loader.py # Dynamic loading
│   ├── container.py       # Docker building
│   ├── settings.py        # Global settings
│   ├── multi_classifier.py # Multi-model support
│   ├── concurrency_limiter.py # Rate limiting
│   └── ainit/             # AI-powered init
│       ├── __init__.py
│       ├── analyzer.py
│       ├── generator.py
│       └── templates/
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── load/            # Load tests
│   └── fixtures/        # Test data
├── examples/             # Example implementations
├── docs/                # Documentation
├── monitoring/          # Prometheus/Grafana
└── scripts/            # Utility scripts
```

## Writing Predictors

### Basic Predictor Interface

```python
# predictor.py
class MyPredictor:
    """Custom ML predictor."""

    def __init__(self, model_path: str, **kwargs):
        """Initialize with model artifacts."""
        self.model = self.load_model(model_path)

    def predict(self, X):
        """Make predictions."""
        return self.model.predict(X)

    def predict_proba(self, X):
        """Optional: Return probabilities."""
        return self.model.predict_proba(X)

    def load_model(self, path: str):
        """Load model from disk."""
        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)
```

### Advanced Predictor Features

```python
class AdvancedPredictor:
    """Predictor with preprocessing and validation."""

    def __init__(self, model_path: str, config_path: str):
        self.model = self.load_model(model_path)
        self.config = self.load_config(config_path)
        self.preprocessor = self.build_preprocessor()

    def predict(self, X):
        # Validate input
        X = self.validate_input(X)

        # Preprocess
        X_processed = self.preprocessor.transform(X)

        # Predict
        predictions = self.model.predict(X_processed)

        # Post-process
        return self.postprocess(predictions)

    def validate_input(self, X):
        """Ensure input meets requirements."""
        if len(X.shape) != 2:
            raise ValueError("Expected 2D array")
        if X.shape[1] != len(self.config['features']):
            raise ValueError(f"Expected {len(self.config['features'])} features")
        return X

    def postprocess(self, predictions):
        """Apply business logic to predictions."""
        # Example: Apply threshold
        if hasattr(self, 'threshold'):
            predictions = (predictions > self.threshold).astype(int)
        return predictions
```

## Testing

### Unit Tests

```python
# tests/unit/test_predictor.py
import pytest
import numpy as np
from predictor import MyPredictor

def test_predictor_initialization():
    predictor = MyPredictor(model_path="model.pkl")
    assert predictor is not None
    assert hasattr(predictor, 'predict')

def test_prediction():
    predictor = MyPredictor(model_path="model.pkl")
    X = np.array([[1, 2, 3]])
    predictions = predictor.predict(X)
    assert predictions.shape[0] == 1
```

### Integration Tests

```python
# tests/integration/test_api.py
import pytest
from fastapi.testclient import TestClient
from mlserver.server import create_app

@pytest.fixture
def client():
    app = create_app("test_config.yaml")
    return TestClient(app)

def test_predict_endpoint(client):
    response = client.post(
        "/predict",
        json={"data": [{"feature1": 1, "feature2": 2}]}
    )
    assert response.status_code == 200
    assert "predictions" in response.json()

def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
```

### Load Testing

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class MLServerUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def predict(self):
        self.client.post(
            "/predict",
            json={"data": [{"age": 25, "fare": 50}]}
        )

    @task(2)
    def check_info(self):
        self.client.get("/info")
```

Run load tests:
```bash
# Start server
mlserver serve

# Run load test
locust -f tests/load/locustfile.py --host http://localhost:8000
```

## Debugging

### Enable Debug Logging

```bash
# Via CLI
mlserver serve --log-level DEBUG

# Via environment
export MLSERVER_LOG_LEVEL=DEBUG
mlserver serve

# In config
observability:
  log_level: "DEBUG"
```

### Common Issues and Solutions

#### Module Not Found
```python
# Problem: Can't find predictor module
# Solution 1: Use simple filename in config
predictor:
  module: predictor  # Not path/to/predictor.py

# Solution 2: Add to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

#### Memory Issues
```python
# Problem: Model too large for memory
# Solution: Use lazy loading
class LazyPredictor:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = self.load_model(self.model_path)
        return self._model
```

#### Slow Predictions
```python
# Problem: Predictions taking too long
# Solution 1: Batch processing
def predict(self, X):
    if len(X) > 100:
        # Process in batches
        results = []
        for i in range(0, len(X), 100):
            batch = X[i:i+100]
            results.extend(self.model.predict(batch))
        return np.array(results)
    return self.model.predict(X)

# Solution 2: Caching
from functools import lru_cache

@lru_cache(maxsize=128)
def predict_cached(self, X_hash):
    X = self.unhash(X_hash)
    return self.model.predict(X)
```

## Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints
- Document with docstrings
- Keep functions small and focused

### Example with Type Hints
```python
from typing import List, Dict, Union, Optional
import numpy as np
import pandas as pd

class TypedPredictor:
    def __init__(self, model_path: str, config: Optional[Dict] = None) -> None:
        """Initialize predictor with optional config."""
        self.model_path = model_path
        self.config = config or {}

    def predict(
        self,
        X: Union[np.ndarray, pd.DataFrame, List[Dict]]
    ) -> np.ndarray:
        """Make predictions on input data."""
        # Convert to numpy if needed
        if isinstance(X, pd.DataFrame):
            X = X.values
        elif isinstance(X, list):
            X = np.array(X)

        return self._predict_internal(X)

    def _predict_internal(self, X: np.ndarray) -> np.ndarray:
        """Internal prediction logic."""
        return self.model.predict(X)
```

## Contributing

### Development Workflow

1. **Fork and Clone**
```bash
git clone https://github.com/yourusername/fastapi-mlserver-wrapper.git
cd fastapi-mlserver-wrapper
git remote add upstream https://github.com/alxhrzg/fastapi-mlserver-wrapper.git
```

2. **Create Feature Branch**
```bash
git checkout -b feature/your-feature-name
```

3. **Make Changes**
```bash
# Edit files
# Add tests
# Update documentation
```

4. **Run Tests**
```bash
# All tests
pytest

# With coverage
pytest --cov=mlserver --cov-report=html

# Specific tests
pytest tests/unit/test_config.py
```

5. **Commit Changes**
```bash
git add .
git commit -m "feat: add new feature

- Detailed description
- Breaking changes (if any)
- Related issues"
```

6. **Push and Create PR**
```bash
git push origin feature/your-feature-name
# Create pull request on GitHub
```

### Version Management in Development

#### Understanding Hierarchical Tags

MLServer uses hierarchical tags for complete reproducibility:
```
<classifier-name>-v<X.X.X>-mlserver-<commit-hash>
Example: sentiment-v2.3.1-mlserver-b5dff2a
```

This format captures:
- **Classifier version**: Semantic version of your classifier code
- **MLServer commit**: Exact version of the MLServer tool used

#### Creating Versions During Development

```bash
# Check current version status
mlserver tag

# Output shows current versions and recommendations:
#                    🏷️  Classifier Version Status
# ┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
# ┃ Classifier ┃ Version ┃ MLServer  ┃ Status ┃ Action Required ┃
# ┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
# │ sentiment  │ 1.0.0   │ b5dff2a ✓ │ Ready  │ -               │
# └────────────┴─────────┴───────────┴────────┴─────────────────┘

# Create version tag after completing feature
mlserver tag --classifier sentiment patch  # For bug fixes
mlserver tag --classifier sentiment minor  # For new features
mlserver tag --classifier sentiment major  # For breaking changes

# Push tags to remote
git push --tags
```

#### Testing Reproducibility

Before creating a PR, verify your build is reproducible:

```bash
# 1. Create a tag for your changes
mlserver tag --classifier sentiment patch

# 2. Note the created tag (e.g., sentiment-v1.0.1-mlserver-b5dff2a)

# 3. Build container with the tag
mlserver build --classifier sentiment-v1.0.1-mlserver-b5dff2a

# 4. Verify container labels include version info
docker inspect sentiment:latest | grep -A 20 Labels

# 5. Test the container
docker run -p 8000:8000 sentiment:latest

# 6. Verify version endpoint
curl http://localhost:8000/version
```

#### Multi-Classifier Development

For repositories with multiple classifiers:

```bash
# Check status of all classifiers
mlserver tag

# Work on specific classifier
cd classifiers/sentiment

# Make changes...

# Tag only the classifier you modified
mlserver tag --classifier sentiment patch

# Other classifiers maintain their versions independently
mlserver tag --classifier intent minor  # If you also modified intent
```

#### Version Bumping Guidelines

Choose the right semantic version bump:

- **Patch (X.X.Y)**: Bug fixes, minor improvements, no API changes
  ```bash
  mlserver tag --classifier sentiment patch
  ```

- **Minor (X.Y.0)**: New features, backward compatible
  ```bash
  mlserver tag --classifier sentiment minor
  ```

- **Major (Y.0.0)**: Breaking changes, API modifications
  ```bash
  mlserver tag --classifier sentiment major
  ```

#### Validating Before PR

Run this checklist before creating your PR:

```bash
# 1. Run all tests
pytest tests/ --cov=mlserver

# 2. Check working directory is clean
git status

# 3. View tag status
mlserver tag

# 4. If tests pass and everything looks good, create tag
mlserver tag --classifier <name> <patch|minor|major>

# 5. Build and test container
mlserver build --classifier <tag-name>

# 6. Validate push readiness (checks for uncommitted changes)
mlserver version --detailed
```

#### Common Version Management Scenarios

**Scenario 1: Forgot to tag before pushing**
```bash
# No problem! Create tag now
mlserver tag --classifier sentiment patch

# Push the tag separately
git push --tags
```

**Scenario 2: Need to fix a bug in an old version**
```bash
# Checkout the old tag
git checkout sentiment-v1.0.0-mlserver-abc123

# Create a branch
git checkout -b hotfix/sentiment-security-fix

# Make fixes, commit
git commit -m "fix: security vulnerability"

# Create new patch version
mlserver tag --classifier sentiment patch  # Creates v1.0.1

# Push branch and tag
git push origin hotfix/sentiment-security-fix --tags
```

**Scenario 3: Working with uncommitted changes**
```bash
# Try to create tag with uncommitted changes
mlserver tag --classifier sentiment patch

# Output:
# ⚠️  Warning: Working directory has uncommitted changes
# ❌ Cannot create tag with uncommitted changes

# Solution: Commit your changes first
git add .
git commit -m "feat: add new feature"
mlserver tag --classifier sentiment minor
```

### Pull Request Guidelines

- Clear, descriptive title
- Reference related issues
- Include test coverage
- Update documentation
- Follow existing code style
- Add changelog entry
- **Create version tag** for significant changes
- **Test reproducibility** with container builds

## Performance Optimization

### Profiling

```python
# Enable profiling
import cProfile
import pstats

def profile_predictor():
    profiler = cProfile.Profile()
    profiler.enable()

    # Your code here
    predictor.predict(data)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

### Memory Optimization

```python
# Use generators for large datasets
def batch_generator(data, batch_size=32):
    for i in range(0, len(data), batch_size):
        yield data[i:i+batch_size]

# Process in batches
for batch in batch_generator(large_dataset):
    predictions.extend(predictor.predict(batch))
```

### Async Operations

```python
# Async predictor for I/O-bound operations
import asyncio

class AsyncPredictor:
    async def predict(self, X):
        # Async preprocessing
        X_processed = await self.preprocess_async(X)

        # Run CPU-bound work in executor
        loop = asyncio.get_event_loop()
        predictions = await loop.run_in_executor(
            None, self.model.predict, X_processed
        )

        return predictions
```

## Monitoring & Logging

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

class LoggingPredictor:
    def predict(self, X):
        logger.info(
            "prediction_started",
            input_shape=X.shape,
            model_version=self.version
        )

        try:
            predictions = self.model.predict(X)
            logger.info(
                "prediction_completed",
                output_shape=predictions.shape
            )
            return predictions
        except Exception as e:
            logger.error(
                "prediction_failed",
                error=str(e),
                exc_info=True
            )
            raise
```

### Custom Metrics

```python
from prometheus_client import Histogram, Counter

prediction_duration = Histogram(
    'prediction_duration_seconds',
    'Time spent making predictions'
)

prediction_errors = Counter(
    'prediction_errors_total',
    'Total prediction errors'
)

class MetricsPredictor:
    def predict(self, X):
        with prediction_duration.time():
            try:
                return self.model.predict(X)
            except Exception as e:
                prediction_errors.inc()
                raise
```

## Security Best Practices

### Input Validation

```python
def validate_input(data: dict) -> dict:
    """Validate and sanitize input data."""
    # Check required fields
    required = ['feature1', 'feature2']
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Validate types
    if not isinstance(data['feature1'], (int, float)):
        raise TypeError("feature1 must be numeric")

    # Sanitize strings
    if 'text' in data:
        data['text'] = data['text'].strip()[:1000]  # Limit length

    return data
```

### Secure Model Loading

```python
import hashlib

def verify_model_integrity(model_path: str, expected_hash: str):
    """Verify model file integrity."""
    sha256_hash = hashlib.sha256()
    with open(model_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    actual_hash = sha256_hash.hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("Model file integrity check failed")
```

## Troubleshooting Guide

### Issue: Server Won't Start

**Symptoms**: Error on startup
**Common Causes**:
1. Port already in use
2. Missing dependencies
3. Invalid configuration

**Solutions**:
```bash
# Check port usage
lsof -i :8000

# Install missing dependencies
pip install -r requirements.txt

# Validate config
python -c "from mlserver.config import load_config; load_config('mlserver.yaml')"
```

### Issue: Predictions Failing

**Symptoms**: 500 errors on /predict
**Common Causes**:
1. Model not loaded
2. Input shape mismatch
3. Missing preprocessing

**Debug Steps**:
```python
# Add debug logging
def predict(self, X):
    print(f"Input shape: {X.shape}")
    print(f"Input dtype: {X.dtype}")
    print(f"Model expects: {self.model.n_features_in_}")

    # Check preprocessing
    X_processed = self.preprocess(X)
    print(f"After preprocessing: {X_processed.shape}")

    return self.model.predict(X_processed)
```

### Issue: Memory Leaks

**Symptoms**: Increasing memory usage
**Common Causes**:
1. Large objects not garbage collected
2. Circular references
3. Cache growing unbounded

**Solutions**:
```python
# Clear caches periodically
import gc

class MemoryEfficientPredictor:
    def __init__(self):
        self.cache = {}
        self.request_count = 0

    def predict(self, X):
        self.request_count += 1

        # Clear cache every 1000 requests
        if self.request_count % 1000 == 0:
            self.cache.clear()
            gc.collect()

        return self.model.predict(X)
```