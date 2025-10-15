# Multi-Classifier Workflow Guide

## Overview
This guide explains how to set up, develop, and deploy multiple ML classifiers from a single repository using the mlserver framework.

## Workflow Summary

### Step 1: Train Multiple Models
Train different classifiers and save their artifacts in separate directories:

```bash
cd examples/example_titanic_manual_setup
python train_titanic_2_classifiers.py
```

This creates:
```
artifacts/
├── catboost-survival/
│   ├── model.pkl
│   ├── features.json
│   ├── metrics.json
│   └── categorical_indices.json
└── randomforest-survival/
    ├── model.pkl
    ├── features.json
    ├── metrics.json
    ├── label_encoders.pkl
    └── scaler.pkl
```

### Step 2: Create Predictor Classes
Create a predictor class for each classifier:
- `predictor_catboost_v2.py` - CatBoostSurvivalPredictor
- `predictor_randomforest.py` - RandomForestSurvivalPredictor

### Step 3: Configure Multi-Classifier YAML
Create `mlserver_multi_classifier.yaml` with structure:

```yaml
# Global settings (shared by all classifiers)
server:
  host: 0.0.0.0
  port: 8000

observability:
  metrics: true

repository:
  name: "titanic-multi-classifier"

# Define multiple classifiers
classifiers:
  catboost-survival:
    metadata:
      name: "catboost-survival"
      version: "1.0.0"
    predictor:
      module: predictor_catboost_v2
      class_name: CatBoostSurvivalPredictor
    api:
      include_version_in_url: false

  randomforest-survival:
    metadata:
      name: "randomforest-survival"
      version: "1.0.0"
    predictor:
      module: predictor_randomforest
      class_name: RandomForestSurvivalPredictor
    api:
      include_version_in_url: false

default_classifier: "catboost-survival"
```

### Step 4: Local Development

#### Serve specific classifier:
```bash
# Serve CatBoost classifier
ml_server serve mlserver_multi_classifier.yaml --classifier catboost-survival

# Serve RandomForest classifier
ml_server serve mlserver_multi_classifier.yaml --classifier randomforest-survival

# Serve default classifier (catboost-survival)
ml_server serve mlserver_multi_classifier.yaml
```

#### Test endpoints (versionless URLs):
```bash
# CatBoost endpoint
curl -X POST http://localhost:8000/catboost-survival/predict \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "records": [{
        "Pclass": 1,
        "Sex": "female",
        "Age": 25,
        "SibSp": 1,
        "Parch": 0,
        "Fare": 100.0,
        "Embarked": "S",
        "FamilySize": 2,
        "IsAlone": 0,
        "Title": "Mrs"
      }]
    }
  }'

# RandomForest endpoint
curl -X POST http://localhost:8000/randomforest-survival/predict \
  -H "Content-Type: application/json" \
  -d '{"payload": {"records": [...]}}'
```

### Step 5: Version Management

#### Git Tagging Strategy:
```bash
# Tag format: {classifier}-v{version}
git tag catboost-survival-v1.0.0
git tag randomforest-survival-v1.0.0

# Push tags
git push origin --tags
```

#### Version Bumping:
```bash
# Update version in mlserver_multi_classifier.yaml
# Change catboost-survival version from 1.0.0 to 1.1.0

# Commit and tag
git add mlserver_multi_classifier.yaml
git commit -m "Bump catboost-survival to v1.1.0"
git tag catboost-survival-v1.1.0
```

### Step 6: Container Build Strategy

#### Build Single Classifier:
```bash
# Build CatBoost classifier container
ml_server build --classifier catboost-survival

# Build RandomForest classifier container
ml_server build --classifier randomforest-survival
```

#### Container Naming Convention:
```
{repository}-{classifier}:{version}

Examples:
- titanic-multi-classifier-catboost-survival:1.0.0
- titanic-multi-classifier-catboost-survival:latest
- titanic-multi-classifier-randomforest-survival:1.0.0
```

#### Build All Classifiers:
```bash
# Script to build all classifiers
#!/bin/bash
for classifier in catboost-survival randomforest-survival; do
  ml_server build --classifier $classifier
done
```

### Step 7: CI/CD Integration

#### GitHub Actions Workflow:
```yaml
name: Build and Deploy Classifier

on:
  workflow_dispatch:
    inputs:
      classifier:
        description: 'Classifier to build'
        required: true
        type: choice
        options:
          - catboost-survival
          - randomforest-survival
      tag:
        description: 'Git tag (e.g., catboost-survival-v1.0.0)'
        required: true

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.event.inputs.tag }}

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install mlserver
        run: pip install fastapi-mlserver-wrapper

      - name: Build Container
        run: |
          ml_server build \
            --classifier ${{ github.event.inputs.classifier }} \
            --registry ${{ secrets.REGISTRY_URL }}

      - name: Push Container
        run: |
          ml_server push \
            --classifier ${{ github.event.inputs.classifier }} \
            --registry ${{ secrets.REGISTRY_URL }}
```

### Step 8: Kubernetes Deployment

#### Deployment per Classifier Version:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catboost-survival-v1-0-0
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: classifier
        image: registry.example.com/titanic-multi-classifier-catboost-survival:1.0.0
        env:
        - name: MLSERVER_CLASSIFIER
          value: "catboost-survival"
---
apiVersion: v1
kind: Service
metadata:
  name: catboost-survival
spec:
  selector:
    app: catboost-survival
    version: v1.0.0
  ports:
  - port: 8000
```

### Step 9: Version Tracking

#### Response Metadata:
Every prediction response includes metadata:
```json
{
  "predictions": [1, 0, 1],
  "time_ms": 12.5,
  "metadata": {
    "repository": "titanic-multi-classifier",
    "classifier": "catboost-survival",
    "version": "1.0.0",
    "git_tag": "catboost-survival-v1.0.0",
    "git_commit": "abc123def",
    "trained_at": "2024-01-15T10:30:00Z",
    "model_metrics": {
      "accuracy": 0.8267,
      "f1_score": 0.7429
    }
  }
}
```

### Step 10: Production Workflow

1. **Development**: Train model, create predictor, test locally
2. **Version**: Update version in config, commit changes
3. **Tag**: Create git tag for specific classifier version
4. **Build**: CI/CD builds container from tag
5. **Deploy**: Deploy to dev environment
6. **Test**: Validate predictions and performance
7. **Promote**: Deploy to production
8. **Monitor**: Track metrics by classifier and version

## Best Practices

### 1. Naming Conventions
- Classifiers: `{model-type}-{purpose}` (e.g., catboost-survival)
- Git tags: `{classifier}-v{semver}` (e.g., catboost-survival-v1.2.3)
- Containers: `{repo}-{classifier}:{version}`

### 2. Version Management
- Each classifier has independent versioning
- Use semantic versioning (major.minor.patch)
- Tag every production deployment
- Keep metadata synchronized with git tags

### 3. Testing Strategy
- Unit tests per predictor class
- Integration tests per classifier
- Load testing with specific classifier endpoints
- A/B testing with multiple versions

### 4. Deployment Strategy
- Immutable containers (never update, always redeploy)
- Blue-green deployments per classifier
- Canary deployments for new versions
- Separate scaling policies per classifier

## Migration from Single to Multi-Classifier

### For Existing Projects:
1. Keep existing `mlserver.yaml` for backward compatibility
2. Create new `mlserver_multi.yaml` with multi-classifier format
3. Update CI/CD to detect configuration type
4. Gradually migrate to multi-classifier structure

### Detection Logic:
```python
# The CLI automatically detects configuration type:
if "classifiers" in config:
    # Multi-classifier mode
    use_multi_classifier_logic()
else:
    # Single classifier mode (backward compatible)
    use_single_classifier_logic()
```

## Troubleshooting

### Issue: "No classifier specified"
**Solution**: Either specify `--classifier <name>` or set `default_classifier` in config

### Issue: Container build fails
**Solution**: Ensure predictor module paths are correct and artifacts exist

### Issue: Wrong version deployed
**Solution**: Check git tag matches container tag and deployment manifest

### Issue: Performance degradation
**Solution**: Monitor metrics per classifier, scale replicas independently

## Example Commands Reference

```bash
# Local development
ml_server serve mlserver_multi.yaml --classifier catboost-survival

# List available classifiers
ml_server list-classifiers mlserver_multi.yaml

# Build specific version
git checkout catboost-survival-v1.2.3
ml_server build --classifier catboost-survival

# Push to registry
ml_server push --classifier catboost-survival --registry gcr.io/myproject

# Check version info
ml_server version --classifier catboost-survival

# Run tests for specific classifier
pytest tests/test_catboost_predictor.py
```

## Next Steps

1. Implement automated version bumping script
2. Add classifier-specific health checks
3. Create Grafana dashboards per classifier
4. Implement automated rollback on metric degradation
5. Add support for ensemble predictions across classifiers