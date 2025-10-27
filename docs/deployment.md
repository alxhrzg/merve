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

### 1. Git Tagging Strategy (Enhanced with MLServer Tracking)

For multi-classifier repos, use **hierarchical tags with MLServer commit tracking**:

#### Tag Format
```
<classifier-name>-v<X.X.X>-mlserver-<commit-hash>
```

Example: `sentiment-v2.3.1-mlserver-b5dff2a`

This format provides:
- **Classifier version**: Semantic versioning for classifier code
- **MLServer version**: Tool/framework commit for reproducibility
- **Complete traceability**: Exact state of both classifier and MLServer

#### Creating Tags

Use the CLI tool (automatically includes MLServer commit):
```bash
# Create tags using mlserver CLI
mlserver tag --classifier sentiment patch   # v2.3.1
mlserver tag --classifier intent minor      # v1.1.0
mlserver tag --classifier ner major         # v3.0.0

# Tags created: sentiment-v2.3.1-mlserver-b5dff2a
#                intent-v1.1.0-mlserver-b5dff2a
#                ner-v3.0.0-mlserver-b5dff2a

# Push tags to remote
git push --tags
```

#### View Tag Status
```bash
# Show status of all classifiers
mlserver tag

# Output:
#                    🏷️  Classifier Version Status
# ┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
# ┃ Classifier ┃ Version ┃ MLServer  ┃ Status ┃ Action Required ┃
# ┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
# │ sentiment  │ 2.3.1   │ b5dff2a ✓ │ Ready  │ -               │
# │ intent     │ 1.1.0   │ b5dff2a ✓ │ Ready  │ -               │
# │ ner        │ 3.0.0   │ b5dff2a ✓ │ Ready  │ -               │
# └────────────┴─────────┴───────────┴────────┴─────────────────┘
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

### 3. GitHub Actions Workflows

#### Option A: Trigger on Git Tag Push (Recommended)

`.github/workflows/build-on-tag.yml`:
```yaml
name: Build and Deploy on Tag

on:
  push:
    tags:
      - '*-v*-mlserver-*'  # Match hierarchical tag format

jobs:
  parse-and-build:
    runs-on: ubuntu-latest
    steps:
      - name: Parse Hierarchical Tag
        id: parse
        run: |
          TAG_NAME="${GITHUB_REF#refs/tags/}"
          echo "Full tag: $TAG_NAME"

          # Parse: sentiment-v2.3.1-mlserver-b5dff2a
          CLASSIFIER=$(echo $TAG_NAME | sed -E 's/^([a-z0-9_-]+)-v.*/\1/')
          VERSION=$(echo $TAG_NAME | sed -E 's/^[a-z0-9_-]+-v([0-9]+\.[0-9]+\.[0-9]+)-.*/\1/')
          MLSERVER=$(echo $TAG_NAME | sed -E 's/.*-mlserver-([a-f0-9]+)$/\1/')

          echo "classifier=$CLASSIFIER" >> $GITHUB_OUTPUT
          echo "version=$VERSION" >> $GITHUB_OUTPUT
          echo "mlserver_commit=$MLSERVER" >> $GITHUB_OUTPUT

          echo "Parsed: classifier=$CLASSIFIER, version=$VERSION, mlserver=$MLSERVER"

      - uses: actions/checkout@v3
        with:
          ref: ${{ github.ref }}
          fetch-depth: 0  # Fetch all history for git operations

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install MLServer
        run: |
          pip install -e .

      - name: Validate Tag Matches Code
        run: |
          # Verify current code matches tag
          mlserver build --classifier ${{ github.ref_name }} --dry-run || true

      - name: Build Container
        run: |
          # Build with full hierarchical tag for validation
          mlserver build --classifier ${{ github.ref_name }}

      - name: Login to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ secrets.REGISTRY_URL }}
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Tag and Push Container
        run: |
          CLASSIFIER="${{ steps.parse.outputs.classifier }}"
          VERSION="${{ steps.parse.outputs.version }}"
          MLSERVER="${{ steps.parse.outputs.mlserver_commit }}"

          # Tag with version
          docker tag ${CLASSIFIER}:latest ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:${VERSION}
          docker tag ${CLASSIFIER}:latest ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:${VERSION}-mlserver-${MLSERVER}
          docker tag ${CLASSIFIER}:latest ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:latest

          # Push all tags
          docker push ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:${VERSION}
          docker push ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:${VERSION}-mlserver-${MLSERVER}
          docker push ${{ secrets.REGISTRY_URL }}/${CLASSIFIER}:latest

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          name: "${{ steps.parse.outputs.classifier }} v${{ steps.parse.outputs.version }}"
          body: |
            ## ${{ steps.parse.outputs.classifier }} v${{ steps.parse.outputs.version }}

            **Classifier Commit**: ${{ github.sha }}
            **MLServer Commit**: ${{ steps.parse.outputs.mlserver_commit }}
            **Container**: `${{ secrets.REGISTRY_URL }}/${{ steps.parse.outputs.classifier }}:${{ steps.parse.outputs.version }}`

            ### Reproducibility
            ```bash
            git checkout ${{ github.ref_name }}
            mlserver build --classifier ${{ steps.parse.outputs.classifier }}
            ```
```

#### Option B: Manual Workflow Dispatch

`.github/workflows/build-dispatch.yml`:
```yaml
name: Manual Build and Deploy

on:
  workflow_dispatch:
    inputs:
      full_tag:
        description: 'Full hierarchical tag (e.g., sentiment-v2.3.1-mlserver-b5dff2a)'
        required: true
        type: string

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Validate Tag Format
        run: |
          TAG="${{ github.event.inputs.full_tag }}"
          if ! echo "$TAG" | grep -qE '^[a-z0-9_-]+-v[0-9]+\.[0-9]+\.[0-9]+-mlserver-[a-f0-9]+$'; then
            echo "❌ Invalid tag format"
            echo "Expected: <classifier>-v<X.X.X>-mlserver-<hash>"
            echo "Got: $TAG"
            exit 1
          fi
          echo "✅ Tag format valid"

      - uses: actions/checkout@v3
        with:
          ref: ${{ github.event.inputs.full_tag }}

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install and Build
        run: |
          pip install -e .
          mlserver build --classifier ${{ github.event.inputs.full_tag }} --force
```

#### Option C: Pull Request Validation

`.github/workflows/validate-pr.yml`:
```yaml
name: Validate PR

on:
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install MLServer
        run: pip install -e ".[test]"

      - name: Check Tag Status
        run: |
          # Show which classifiers need tagging
          mlserver tag || true

      - name: Run Tests
        run: pytest tests/

      - name: Validate Configs
        run: |
          # Validate all classifier configs
          for config in classifiers/*/mlserver.yaml; do
            mlserver validate $config
          done
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
mlserver serve mlserver.yaml

# Test endpoint
curl http://localhost:8000/sentiment-analyzer/predict
```

### 2. Building Multiple Classifiers
```bash
# Build all classifiers in a repository with hierarchical tags
for classifier in classifiers/*/; do
  classifier_name=$(basename $classifier)

  # Create hierarchical tag (automatically includes MLServer commit)
  mlserver tag --classifier $classifier_name patch

  # Build with the created tag
  latest_tag=$(git describe --tags --match "${classifier_name}-v*" --abbrev=0)
  mlserver build --classifier $latest_tag
done
```

### 3. Version Bumping with Hierarchical Tags

**Recommended**: Use the `mlserver tag` command for automatic hierarchical tagging:

```bash
# Patch release (bug fixes) - auto-increments version and includes MLServer commit
mlserver tag --classifier sentiment patch

# Output:
# ✓ Created tag: sentiment-v1.0.3-mlserver-b5dff2a
#
#   📝 Version: 1.0.2 → 1.0.3 (patch bump)
#   🔧 MLServer commit: b5dff2a
#   📦 Classifier commit: c5f9997

# Minor release (new features)
mlserver tag --classifier intent minor

# Major release (breaking changes)
mlserver tag --classifier fraud-detection major

# Push tags to remote
git push --tags
```

**Manual Alternative** (not recommended):

If you need custom scripting, create `scripts/bump_version.sh`:
```bash
#!/bin/bash
CLASSIFIER=$1
VERSION_TYPE=$2  # major, minor, patch

# Use the mlserver CLI command instead of manual tag creation
mlserver tag --classifier $CLASSIFIER $VERSION_TYPE

# Push to remote
git push --tags
```

**Tag Status Overview**:
```bash
# View status of all classifiers in repository
mlserver tag

# Shows table with current versions, MLServer commits, and recommended actions
```

## Migration Path for Existing Projects

If you have existing projects using older tagging formats, follow this migration guide:

### Step 1: Understand Your Current Tags (5 minutes)
```bash
# List existing tags
git tag -l

# Existing tags might look like:
# v1.0.0
# v1.0.1
# sentiment-v1.0.0
```

### Step 2: Update to Hierarchical Tags (10 minutes)
```bash
# For single-classifier repos
# Old format: v1.0.0
# New format: <classifier-name>-v1.0.0-mlserver-<hash>

# Create first hierarchical tag from current version
mlserver tag --classifier <your-classifier-name> patch

# Example output:
# ✓ Created tag: sentiment-v1.0.1-mlserver-b5dff2a
```

### Step 3: Update CI/CD Workflows (30 minutes)
1. Update GitHub Actions to use new tag format (see workflows above)
2. Change tag triggers: `tags: ['*-v*-mlserver-*']`
3. Add tag parsing logic to extract classifier, version, and MLServer commit

### Step 4: Update Container Build Process (15 minutes)
```bash
# Old command:
# docker build -t my-classifier:v1.0.0 .

# New command with hierarchical tag:
mlserver build --classifier sentiment-v1.0.1-mlserver-b5dff2a

# Or let MLServer detect the latest tag automatically:
mlserver build --classifier sentiment
```

### Step 5: Validate Reproducibility (10 minutes)
```bash
# Check that your tags include full reproducibility info
git show sentiment-v1.0.1-mlserver-b5dff2a

# Verify you can rebuild from any historical tag
git checkout sentiment-v1.0.1-mlserver-b5dff2a
mlserver build --classifier sentiment-v1.0.1-mlserver-b5dff2a
```

### Backward Compatibility Notes

- **Existing containers**: Continue to work without changes
- **Old tags**: Remain in git history, no need to delete
- **Gradual migration**: New releases use hierarchical tags, old ones remain unchanged
- **API endpoints**: No changes required (versionless design recommended)

## Benefits of Hierarchical Versioning

1. **Complete Reproducibility**: Tags capture both classifier code AND MLServer tool versions
   - Example: `sentiment-v2.3.1-mlserver-b5dff2a` contains exact commits for both
   - Can rebuild identical container months or years later
   - No dependency on external registries for version tracking

2. **Multi-Classifier Support**: Single repository can host multiple related classifiers
   - Each classifier has independent versioning
   - Shared utilities and dependencies across classifiers
   - Centralized repository management

3. **Backward Compatible**: Existing single-classifier repos continue to work
   - Gradual migration path
   - No breaking changes to existing deployments
   - Old tags remain valid

4. **CI/CD Integration**: Seamless GitHub Actions workflow
   - Automatic builds on tag push
   - Tag parsing extracts classifier, version, and MLServer commit
   - Validation ensures code matches tag specifications

5. **Clear Deployment Path**: Each version is a separate immutable deployment
   - Kubernetes deployments per version
   - Easy rollback to any previous version
   - Canary and blue-green deployment support

6. **Simplified Client Integration**: Clients use stable URLs, versions tracked via metadata
   - Versionless endpoints: `/sentiment-analyzer/predict`
   - Version information in response metadata
   - No client code changes for version updates

7. **Developer Experience**: Simple CLI commands handle complexity
   - `mlserver tag --classifier sentiment patch` - one command for version bump
   - Automatic MLServer commit detection
   - Visual status table for all classifiers

8. **Audit Trail**: Complete version history with traceability
   - Git tags provide permanent version markers
   - Container labels include all version metadata
   - Prometheus metrics track version usage

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

## Next Steps for Implementation

### For New Projects

1. **Set up classifier configuration**
   - Create `mlserver.yaml` with classifier metadata
   - Define predictor class and model artifacts

2. **Initialize version control**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"

   # Create first hierarchical tag
   mlserver tag --classifier <your-classifier-name> patch
   ```

3. **Set up CI/CD pipeline**
   - Copy GitHub Actions workflow from examples above
   - Configure container registry credentials
   - Test with first tag push

4. **Deploy to Kubernetes**
   - Use deployment manifests from this guide
   - Configure resource limits based on model requirements
   - Set up monitoring and observability

### For Existing Projects

1. **Migrate to hierarchical tags** (see Migration Path section above)
2. **Update CI/CD workflows** to handle new tag format
3. **Test reproducibility** with historical builds
4. **Update documentation** for your team

### For Multi-Classifier Repositories

1. **Organize repository structure**
   ```
   classifiers/
   ├── classifier-a/
   │   ├── mlserver.yaml
   │   └── predictor.py
   └── classifier-b/
       ├── mlserver.yaml
       └── predictor.py
   ```

2. **Tag each classifier independently**
   ```bash
   mlserver tag --classifier classifier-a patch
   mlserver tag --classifier classifier-b minor
   ```

3. **Build and deploy separately**
   ```bash
   mlserver build --classifier classifier-a-v1.0.1-mlserver-b5dff2a
   mlserver build --classifier classifier-b-v1.1.0-mlserver-b5dff2a
   ```

### Additional Resources

- **CLI Reference**: See `docs/cli-reference.md` for detailed command documentation
- **Examples**: Check `examples/` directory for sample configurations
- **Testing**: Review `TEST_IMPROVEMENT_BACKLOG.md` for test coverage details