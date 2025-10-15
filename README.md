# 🚀 MLServer FastAPI Wrapper

**Transform any Python predictor into a production-ready FastAPI inference API with just a YAML configuration.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-modern-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://docker.com)
[![Prometheus](https://img.shields.io/badge/Prometheus-metrics-orange.svg)](https://prometheus.io)

## ✨ Key Features

### 🎯 **Zero-Code API Generation**
- **Instant deployment**: Wrap any Python predictor class into a FastAPI server with a single YAML file
- **Multi-classifier support**: Deploy multiple ML models from a single repository
- **Auto-detection**: Automatically discovers configuration files (`mlserver.yaml`)
- **Plugin architecture**: Support for any machine learning framework (scikit-learn, CatBoost, PyTorch, etc.)

### 🏗️ **Production-Ready Architecture**
- **Process-based scaling**: Multi-process workers (not threads) for true parallelism and container compatibility
- **Unified endpoints**: Clean `/predict` API structure without version/classifier in URLs
- **Thread-safe predictions**: Configurable locking for model inference safety
- **Flexible input formats**: Support for both JSON records and numpy ndarray inputs with auto-detection
- **Intelligent module resolution**: Use simple filenames in configs instead of full module paths

### 📊 **Enterprise Observability**
- **Prometheus metrics**: Built-in `/metrics` endpoint with request latency, throughput, and error rates
- **Structured logging**: JSON logs with correlation IDs for distributed tracing
- **Request tracking**: Full request/response lifecycle monitoring
- **Live monitoring**: Integrated Grafana dashboards for real-time insights
- **Comprehensive metadata**: `/info` endpoint returns classifier details, version, and metrics

### 🐳 **Complete Container Workflow**
- **One-command builds**: `ml_server build` creates optimized Docker images
- **Registry integration**: Push to any container registry with `ml_server push`
- **Automatic tagging**: Semantic versioning with Git integration
- **Dependency optimization**: Smart wheel building and caching

### ⚡ **Modern Developer Experience**
- **Beautiful CLI**: Modern Typer-based CLI with rich tables and color-coded output
- **AI-powered init**: `ml_server ainit` generates complete setup from Jupyter notebooks
- **Multi-classifier workflows**: Deploy and manage multiple models with single command
- **Hot configuration**: Live server updates without code changes
- **Rich validation**: Pydantic-powered configuration validation with helpful error messages

## 🚦 Quick Start

### 1. Install
```bash
pip install mlserver-fastapi-wrapper
```

### 2. Create Configuration
```yaml
# mlserver.yaml
server:
  title: "My ML API"
  port: 8000

predictor:
  module: my_predictor  # Simple filename, no path needed!
  class_name: MyPredictor
  init_kwargs:
    model_path: "./model.pkl"

observability:
  metrics: true
  structured_logging: true

classifier:
  name: "my-classifier"
  version: "1.0.0"
```

### 3. Launch Server
```bash
ml_server serve
# Or use the modern CLI with rich output:
mlserver serve
```

Your ML API is now running at `http://localhost:8000` with:
- 🎯 `/predict` - Main prediction endpoint
- 📊 `/info` - Complete metadata and version info
- 🏥 `/healthz` - Health check endpoint
- 📈 `/metrics` - Prometheus metrics
- 📚 `/docs` - Interactive OpenAPI documentation

## 🎭 Multi-Classifier Support (New!)

Deploy multiple ML models from a single repository:

```yaml
# mlserver_multi.yaml
classifiers:
  catboost-model:
    predictor:
      module: predictor_catboost
      class_name: CatBoostPredictor
    metadata:
      name: "catboost-model"
      version: "1.0.0"

  randomforest-model:
    predictor:
      module: predictor_rf
      class_name: RandomForestPredictor
    metadata:
      name: "randomforest-model"
      version: "2.0.0"

default_classifier: "catboost-model"
```

Launch specific classifier:
```bash
ml_server serve mlserver_multi.yaml --classifier catboost-model
```

## 🛠️ CLI Commands

### Classic CLI (`ml_server`)
| Command | Purpose | Example |
|---------|---------|---------|
| `serve` | Launch ML server | `ml_server serve --port 8080` |
| `ainit` | AI-powered init from notebook | `ml_server ainit notebook.ipynb` |
| `version` | Display version info | `ml_server version --json` |
| `build` | Build Docker container | `ml_server build --registry my-registry.com` |
| `push` | Push to registry | `ml_server push --registry my-registry.com` |
| `images` | List built images | `ml_server images` |
| `clean` | Remove images | `ml_server clean --force` |

### Modern CLI (`mlserver`) - With Rich Output!
| Command | Purpose | Example |
|---------|---------|---------|
| `serve` | Launch with beautiful output | `mlserver serve` |
| `status` | System status with tables | `mlserver status` |
| `list-classifiers` | Show available classifiers | `mlserver list-classifiers` |
| `version` | Version info in table format | `mlserver version` |
| All classic commands | With rich formatting | `mlserver <command>` |

## 🎯 API Endpoints

### Unified Interface (No Version in URLs!)
- **POST** `/predict` - Single prediction
- **POST** `/batch_predict` - Batch predictions
- **POST** `/predict_proba` - Probability predictions
- **GET** `/info` - Complete metadata, version, and metrics
- **GET** `/healthz` - Health check
- **GET** `/metrics` - Prometheus metrics
- **GET** `/status` - Prediction availability status
- **GET** `/docs` - Interactive API documentation

### Metadata Response (`/info`)
```json
{
  "repository": "my-ml-models",
  "classifier": "catboost-model",
  "version": "1.0.0",
  "model_type": "CatBoostPredictor",
  "api_version": "v1",
  "trained_at": "2024-01-15T10:30:00Z",
  "model_metrics": {
    "accuracy": 0.94,
    "precision": 0.92,
    "recall": 0.89
  },
  "git": {
    "commit": "abc123",
    "tag": "v1.0.0"
  }
}
```

## 📈 Performance & Scalability

- **Multi-process workers**: True parallelism without Python GIL limitations
- **Async FastAPI**: Non-blocking I/O for high concurrency
- **Memory efficient**: Cached feature ordering and optimized numpy conversions
- **Container optimized**: Minimal base images with dependency layer caching
- **Concurrency control**: Configurable prediction limits for Kubernetes pod scaling

## 🔧 Configuration Flexibility

- **Unified YAML format**: Single file for server, predictor, and metadata configuration
- **Multi-classifier configs**: Deploy multiple models with single configuration
- **Environment overrides**: CLI arguments override configuration values
- **Intelligent path resolution**: Automatic module discovery from config directory
- **Validation**: Rich error messages with configuration validation

## 📊 Monitoring & Observability

- **Built-in metrics**: Request count, latency percentiles, error rates
- **Custom dashboards**: Pre-configured Grafana visualizations
- **Correlation tracking**: Request IDs for distributed tracing
- **Payload logging**: Optional request/response logging (privacy-aware)
- **Structured logging**: JSON formatted logs for log aggregation systems

## 🏃‍♂️ Complete Demo

Experience all features with our comprehensive demo:

```bash
git clone https://github.com/alxhrzg/fastapi-mlserver-wrapper.git
cd fastapi-mlserver-wrapper
make demo-full
```

This launches:
- ✅ ML server with sample Titanic classifier
- ✅ Prometheus metrics collection
- ✅ Grafana monitoring dashboards
- ✅ Interactive load testing with live metrics
- ✅ Complete container build workflow

### Multi-Classifier Demo
```bash
make demo-setup-multi  # Setup multi-classifier environment
make multi-demo-catboost  # Run CatBoost classifier
make multi-demo-randomforest  # Run RandomForest classifier
```

## 🚀 Deployment Strategy

### Kubernetes Deployment
Each classifier gets its own deployment with unique base URL:
```yaml
# Deployment 1: CatBoost at api.example.com/catboost/
ml_server serve multi.yaml --classifier catboost-model

# Deployment 2: RandomForest at api.example.com/randomforest/
ml_server serve multi.yaml --classifier randomforest-model
```

### Version Management
- Version tracked via metadata, not URLs
- Git tags format: `{classifier}-v{version}`
- Container tags: `{repository}-{classifier}:{version}`
- Query version via `/info` endpoint

## 🤝 Contributing

We welcome contributions! This project includes:
- Comprehensive test suite with 80%+ coverage
- Unit, integration, and load testing
- Docker-based development environment
- Modern CLI with Typer framework
- AI-powered initialization tools

---

**Ready to deploy your ML models with confidence?** Get started in under 5 minutes with MLServer FastAPI Wrapper.