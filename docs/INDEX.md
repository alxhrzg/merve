# 📚 MLServer Documentation Index

## Quick Navigation Guide

This index provides a comprehensive overview of all documentation available for MLServer FastAPI Wrapper. Each section includes a brief description and links to detailed documentation.

---

## 📖 Core Documentation

### [API Reference](./api-reference.md)
- **REST API Endpoints**: Complete endpoint documentation with request/response schemas
- **Input Formats**: Records, ndarray, and auto-detection modes
- **Response Formats**: Prediction responses, metadata, and error handling
- **Authentication**: Security and access control patterns
- **Rate Limiting**: Concurrency control and throttling

### [Configuration Guide](./configuration.md)
- **YAML Structure**: Complete configuration schema and options
- **Server Settings**: Workers, ports, CORS, timeouts
- **Predictor Setup**: Module loading, initialization, and parameters
- **Observability**: Metrics, logging, tracing configuration
- **Multi-Classifier**: Managing multiple models in one repository

### [CLI Reference](./cli-reference.md)
- **Classic CLI** (`ml_server`): Traditional command interface
- **Modern CLI** (`mlserver`): Typer-based rich interface
- **Command Options**: Complete parameter documentation
- **Environment Variables**: CLI overrides and defaults
- **Examples**: Common usage patterns and workflows

### [Architecture Overview](./architecture.md)
- **System Design**: Core components and their interactions
- **Request Flow**: From API to predictor and back
- **Process Model**: Multi-worker architecture and scaling
- **Plugin System**: Dynamic predictor loading mechanism
- **Performance**: Optimization strategies and benchmarks

---

## 🚀 Implementation Guides

### [Deployment Guide](./deployment.md)
- **Kubernetes Strategy**: Pod-based scaling patterns
- **Container Workflow**: Building and pushing images
- **Version Management**: Git tags and registry tagging
- **Environment Configuration**: Production settings
- **Monitoring Setup**: Prometheus and Grafana integration

### [Development Guide](./development.md)
- **Local Setup**: Development environment configuration
- **Testing Strategy**: Unit, integration, and load testing
- **Code Structure**: Package organization and conventions
- **Contributing**: Pull request guidelines
- **Debugging**: Troubleshooting common issues

### [Examples Guide](./examples.md)
- **Titanic Demo**: Complete walkthrough with CatBoost and RandomForest
- **Multi-Classifier Setup**: Deploying multiple models
- **Custom Predictors**: Writing your own predictor classes
- **Load Testing**: Performance testing with Locust
- **Monitoring Demo**: Setting up observability stack

---

## 🔧 Feature Documentation

### [AI-Powered Initialization](./ainit.md)
- **Jupyter Integration**: Converting notebooks to production APIs
- **Auto-Generation**: Creating configs and predictors from notebooks
- **Best Practices**: Notebook structure for optimal results
- **Customization**: Tweaking generated outputs
- **Architecture**: How `ainit` analyzes and generates code

### [Multi-Classifier Support](./multi-classifier.md)
- **Configuration Format**: YAML structure for multiple models
- **Deployment Patterns**: Kubernetes and container strategies
- **Version Management**: Per-classifier versioning
- **Routing**: Request handling and classifier selection
- **Examples**: Real-world multi-model deployments

### [Observability Features](./observability.md)
- **Prometheus Metrics**: Available metrics and labels
- **Structured Logging**: JSON log format and fields
- **Correlation IDs**: Request tracking across services
- **Grafana Dashboards**: Pre-built visualizations
- **Performance Monitoring**: Latency, throughput, errors

---

## 📋 Quick Reference Sheets

### Configuration Quick Reference
```yaml
# Minimal mlserver.yaml
server:
  port: 8000
predictor:
  module: my_predictor
  class_name: MyPredictor
```

### CLI Quick Commands
```bash
# Serve with auto-detection
ml_server serve

# Serve specific classifier
ml_server serve config.yaml --classifier model-name

# Build container
ml_server build --tag my-model:v1.0.0

# AI-powered init
ml_server ainit notebook.ipynb
```

### API Quick Endpoints
- `POST /predict` - Single prediction
- `POST /batch_predict` - Batch predictions
- `GET /info` - Model metadata and version
- `GET /metrics` - Prometheus metrics
- `GET /healthz` - Health check

---

## 🔍 Finding Information

### By Task
- **"I want to deploy a model"** → [Deployment Guide](./deployment.md)
- **"I want to configure the server"** → [Configuration Guide](./configuration.md)
- **"I want to write a predictor"** → [Examples Guide](./examples.md)
- **"I want to monitor performance"** → [Observability Features](./observability.md)
- **"I want to use multiple models"** → [Multi-Classifier Support](./multi-classifier.md)

### By Component
- **Server** → [Architecture Overview](./architecture.md)
- **CLI** → [CLI Reference](./cli-reference.md)
- **API** → [API Reference](./api-reference.md)
- **Config** → [Configuration Guide](./configuration.md)
- **Predictor** → [Development Guide](./development.md)

### By Problem
- **"Server won't start"** → [Development Guide > Debugging](./development.md#debugging)
- **"Predictions are slow"** → [Architecture > Performance](./architecture.md#performance)
- **"Can't find module"** → [Configuration > Module Resolution](./configuration.md#module-resolution)
- **"Metrics not showing"** → [Observability > Troubleshooting](./observability.md#troubleshooting)

---

## 📝 Documentation Maintenance

This documentation is continuously updated as the codebase evolves. When making changes:

1. Update relevant documentation files
2. Update this index if new sections are added
3. Keep examples current with code changes
4. Verify links remain valid
5. Update CLAUDE.md references

**Last Updated**: 2025-01-16
**Version**: 0.2.0