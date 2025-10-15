# ML Server Deployment Strategy

## Overview
This document outlines the deployment strategy for ML classifiers using the mlserver framework, supporting both single and multi-classifier repositories with proper versioning.

## Key Design Decisions

### 1. API Versioning Strategy
We recommend **removing the API version from URLs** and using **versionless endpoints** with metadata responses. Here's why:

- **Immutable containers**: Each Docker image is a specific version of a classifier
- **Version in metadata**: Every response includes repository, classifier name, and git tag
- **Kubernetes manages versions**: Different versions run as separate deployments
- **Simpler client integration**: Clients don't need to update URLs for version changes

### 2. Multi-Classifier Repository Support
A single repository can contain multiple classifiers, each with its own:
- Predictor class
- Model artifacts
- Configuration file
- Docker image

## Repository Structure

### Single Classifier Repository
```
my-classifier/
├── mlserver.yaml           # Main configuration
├── predictor.py           # Predictor class
├── artifacts/             # Model files
│   ├── model.pkl
│   └── preprocessor.pkl
└── Dockerfile            # Auto-generated
```

### Multi-Classifier Repository
```
multi-classifier-repo/
├── classifiers/
│   ├── sentiment/
│   │   ├── mlserver.yaml
│   │   ├── predictor.py
│   │   └── artifacts/
│   ├── intent/
│   │   ├── mlserver.yaml
│   │   ├── predictor.py
│   │   └── artifacts/
│   └── ner/
│       ├── mlserver.yaml
│       ├── predictor.py
│       └── artifacts/
├── shared/               # Shared utilities
│   └── preprocessing.py
└── build.sh             # Build script for all classifiers
```

## Configuration Changes

### Remove API Version from URLs
Update `mlserver/config.py`:
```python
def get_base_path(self) -> str:
    """Get base API path for endpoints."""
    # Option 1: Classifier name only (recommended)
    classifier_name = self.classifier.get('name', 'classifier')
    return f"/{classifier_name}"

    # Option 2: Keep versioning but make it optional
    # api_version = self.api.version
    # if self.api.include_version_in_url:  # New config option
    #     return f"/{api_version}/{classifier_name}"
    # return f"/{classifier_name}"
```

### Enhanced Metadata Response
All endpoints should include comprehensive metadata:
```json
{
  "predictions": [...],
  "metadata": {
    "repository": "multi-classifier-repo",
    "classifier": "sentiment-analyzer",
    "version": "2.3.1",
    "git_tag": "v2.3.1",
    "git_commit": "abc123def",
    "trained_at": "2024-01-15T10:30:00Z",
    "api_version": "v1",
    "model_metrics": {
      "accuracy": 0.95,
      "f1_score": 0.93
    }
  },
  "time_ms": 12.5
}
```

## CI/CD Workflow Adaptations

### 1. Git Tagging Strategy
For multi-classifier repos, use hierarchical tags:
```bash
# Format: <classifier-name>-v<version>
git tag sentiment-v2.3.1
git tag intent-v1.0.0
git tag ner-v3.1.0

# Or use directories in tags
git tag classifiers/sentiment/v2.3.1
```

### 2. Build Script for Multi-Classifier
Create `scripts/build_classifier.sh`:
```bash
#!/bin/bash
CLASSIFIER_PATH=$1
CLASSIFIER_NAME=$(basename $CLASSIFIER_PATH)
VERSION=$2

# Build specific classifier
cd $CLASSIFIER_PATH
ml_server build --tag "${REPO_NAME}-${CLASSIFIER_NAME}:${VERSION}"
```

### 3. GitHub Actions Workflow
`.github/workflows/build-deploy.yml`:
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
          - sentiment
          - intent
          - ner
      version_tag:
        description: 'Git tag for version'
        required: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          ref: ${{ github.event.inputs.version_tag }}

      - name: Build Classifier
        run: |
          cd classifiers/${{ github.event.inputs.classifier }}
          ml_server build

      - name: Push to Registry
        run: |
          ml_server push --registry ${{ secrets.REGISTRY_URL }}
```

### 4. Kubernetes Deployment
Each classifier version gets its own deployment:

`k8s/classifier-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sentiment-analyzer-v2-3-1
  labels:
    app: sentiment-analyzer
    version: v2.3.1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sentiment-analyzer
      version: v2.3.1
  template:
    metadata:
      labels:
        app: sentiment-analyzer
        version: v2.3.1
    spec:
      containers:
      - name: classifier
        image: registry.example.com/multi-classifier-repo-sentiment:v2.3.1
        env:
        - name: MAX_CONCURRENT_PREDICTIONS
          value: "1"  # Single request per pod
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: sentiment-analyzer
spec:
  selector:
    app: sentiment-analyzer
    version: v2.3.1  # Pin to specific version
  ports:
  - port: 8000
    targetPort: 8000
```

### 5. Service Mesh for Canary Deployments
Use Istio or similar for traffic splitting:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: sentiment-analyzer
spec:
  http:
  - match:
    - uri:
        prefix: /sentiment-analyzer
    route:
    - destination:
        host: sentiment-analyzer
        subset: v2-3-1
      weight: 90
    - destination:
        host: sentiment-analyzer
        subset: v2-4-0
      weight: 10  # Canary deployment
```

## Development Workflow

### 1. Local Development
```bash
# Work on specific classifier
cd classifiers/sentiment
ml_server serve mlserver.yaml

# Test endpoint
curl http://localhost:8000/sentiment-analyzer/predict
```

### 2. Building Multiple Classifiers
```bash
# Build all classifiers in a repository
for classifier in classifiers/*/; do
  cd $classifier
  ml_server build --tag-prefix "${REPO_NAME}-$(basename $classifier)"
  cd ../..
done
```

### 3. Version Bumping
Create `scripts/bump_version.sh`:
```bash
#!/bin/bash
CLASSIFIER=$1
VERSION_TYPE=$2  # major, minor, patch

cd classifiers/$CLASSIFIER
# Update version in mlserver.yaml
python -c "
import yaml
with open('mlserver.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Bump version logic here
version_parts = config['classifier']['version'].split('.')
if '${VERSION_TYPE}' == 'patch':
    version_parts[2] = str(int(version_parts[2]) + 1)
# ... more logic

config['classifier']['version'] = '.'.join(version_parts)

with open('mlserver.yaml', 'w') as f:
    yaml.dump(config, f)
"

# Create git tag
git tag "${CLASSIFIER}-v$(grep version mlserver.yaml | head -1 | cut -d' ' -f2)"
```

## Migration Path

### Phase 1: Update Configuration (Week 1)
1. Modify `get_base_path()` to support optional versioning
2. Add configuration flag `include_version_in_url`
3. Enhance metadata responses

### Phase 2: Multi-Classifier Support (Week 2)
1. Update CLI to support `--classifier-path` argument
2. Modify build command to handle subdirectories
3. Create template for multi-classifier repos

### Phase 3: CI/CD Updates (Week 3)
1. Update GitHub Actions workflows
2. Implement hierarchical tagging
3. Test with pilot project

### Phase 4: Production Rollout (Week 4)
1. Deploy first multi-classifier repository
2. Monitor and collect metrics
3. Document lessons learned

## Benefits of This Approach

1. **Backward Compatible**: Existing single-classifier repos continue to work
2. **Flexible Versioning**: Choose between versioned and versionless URLs
3. **Multi-Classifier Support**: Single repo can host multiple related classifiers
4. **Clear Deployment Path**: Each version is a separate immutable deployment
5. **Simplified Client Integration**: Clients use stable URLs, versions tracked via metadata
6. **Kubernetes Native**: Leverages K8s deployment strategies and service mesh

## Example Client Integration

```python
import requests

class MLClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.last_metadata = None

    def predict(self, classifier_name: str, data: dict):
        # URL doesn't include version
        url = f"{self.base_url}/{classifier_name}/predict"

        response = requests.post(url, json={"payload": data})
        result = response.json()

        # Track version from metadata
        self.last_metadata = result.get("metadata", {})
        print(f"Used {self.last_metadata.get('classifier')} "
              f"v{self.last_metadata.get('version')} "
              f"(git: {self.last_metadata.get('git_tag')})")

        return result["predictions"]

# Client doesn't need to know about versions
client = MLClient("http://ml-service.internal")
predictions = client.predict("sentiment-analyzer", {"text": "Great product!"})
```

## Monitoring and Observability

### Metrics to Track
- Requests per classifier version
- Response times by version
- Error rates by version
- Version adoption rate (for canary deployments)

### Prometheus Metrics
```python
# Add to metrics.py
classifier_version_info = Info(
    'mlserver_classifier_version',
    'Classifier version information',
    ['repository', 'classifier', 'version', 'git_tag']
)

# Set at startup
classifier_version_info.labels(
    repository=config.classifier.repository,
    classifier=config.classifier.name,
    version=config.classifier.version,
    git_tag=git_info.tag
).set({'deployed': '1'})
```

## Security Considerations

1. **Image Scanning**: All classifier images scanned before deployment
2. **Version Pinning**: Production always uses specific versions, never 'latest'
3. **RBAC**: Different teams can manage different classifiers in same repo
4. **Secrets Management**: Model artifacts encrypted, credentials in K8s secrets

## Next Steps

1. Review and approve design decisions
2. Implement configuration changes for versionless URLs
3. Create multi-classifier template repository
4. Update CI/CD pipelines
5. Plan pilot migration