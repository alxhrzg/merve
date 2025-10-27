# CLI Reference

## Overview

MLServer provides two CLI interfaces:
- **Classic CLI** (`ml_server`): Traditional command-line interface with argparse
- **Modern CLI** (`mlserver`): Rich, colorful interface using Typer framework

Both CLIs provide the same functionality, with the modern CLI offering enhanced visual output.

## Installation

Both CLIs are automatically installed with the package:

```bash
pip install mlserver-fastapi-wrapper

# Classic CLI
ml_server --help

# Modern CLI (with rich output)
mlserver --help
```

## Modern CLI (`mlserver`)

### Features
- 🎨 Colorful, formatted output
- 📊 Rich tables for data display
- ✨ Progress indicators
- 🔍 Better error messages
- 📝 Structured command groups

### Commands Overview

```bash
mlserver --help  # Show all commands with rich formatting
```

![CLI Output Example]
```
╭─ Commands ──────────────────────────────────────────────────────╮
│ serve              🚀 Start ML server with FastAPI              │
│ ainit              🤖 AI-powered initialization from notebook   │
│ tag                🏷️  Create version tag with reproducibility   │
│ build              📦 Build Docker container                    │
│ push               🚢 Push container to registry                │
│ status             📊 Show system status                        │
│ list-classifiers   📋 List available classifiers               │
│ version            ℹ️  Show version information                  │
│ images             🖼️  List Docker images                        │
│ clean              🧹 Remove Docker images                      │
╰──────────────────────────────────────────────────────────────────╯
```

---

## Core Commands

### `serve` - Start ML Server

Launch the ML inference server with FastAPI.

#### Syntax
```bash
# Classic CLI
ml_server serve [config] [options]

# Modern CLI
mlserver serve [config] [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `config` | Path to config file | Auto-detect |
| `--host` | Bind address | `0.0.0.0` |
| `--port` | Port number | `8000` |
| `--workers` | Number of processes | `1` |
| `--classifier` | Select classifier (multi-config) | Default from config |
| `--reload` | Auto-reload on changes | `false` |
| `--log-level` | Logging level | `INFO` |
| `--no-metrics` | Disable metrics | `false` |

#### Examples
```bash
# Auto-detect configuration
mlserver serve

# Specific configuration
mlserver serve mlserver.yaml

# Override settings
mlserver serve --port 9000 --workers 4

# Multi-classifier selection
mlserver serve multi.yaml --classifier production

# Development mode
mlserver serve --reload --log-level DEBUG
```

#### Output (Modern CLI)
```
╭─ ML Server Starting ─────────────────────────────────────────────╮
│ 📁 Config: mlserver.yaml                                         │
│ 🎯 Model: catboost-survival v1.0.0                              │
│ 🔧 Workers: 4                                                    │
│ 🌐 URL: http://0.0.0.0:8000                                    │
╰──────────────────────────────────────────────────────────────────╯

✅ Server ready at http://localhost:8000
📊 Metrics at http://localhost:8000/metrics
📚 Docs at http://localhost:8000/docs
```

---

### `ainit` - AI-Powered Initialization

Generate complete ML server setup from Jupyter notebooks using AI analysis.

#### Syntax
```bash
ml_server ainit <notebook> [options]
mlserver ainit <notebook> [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `notebook` | Path to Jupyter notebook | Required |
| `--output-dir` | Output directory | `./` |
| `--model-type` | Force model type | Auto-detect |
| `--config-only` | Only generate config | `false` |
| `--force` | Overwrite existing files | `false` |

#### Examples
```bash
# Generate from notebook
mlserver ainit notebook.ipynb

# Custom output directory
mlserver ainit notebook.ipynb --output-dir ./api

# Force model type
mlserver ainit notebook.ipynb --model-type catboost

# Config only (no predictor generation)
mlserver ainit notebook.ipynb --config-only
```

#### Generated Files
```
./
├── mlserver.yaml         # Configuration file
├── predictor.py          # Predictor class
├── requirements.txt      # Dependencies
├── Dockerfile           # Container definition
└── README.md            # Documentation
```

---

### `tag` - Version Tagging & Reproducibility

Create semantic version tags with full reproducibility tracking. Tags include both classifier and MLServer tool commits for complete traceability.

#### Hierarchical Tag Format

Tags follow the format: `<classifier-name>-v<X.X.X>-mlserver-<commit-hash>`

Example: `sentiment-v1.0.3-mlserver-b5dff2a`

This format ensures:
- **Semantic versioning** for classifier code
- **MLServer tool version** tracking
- **Complete reproducibility** - exact commits for both classifier and MLServer

#### Syntax
```bash
# Create new tag
mlserver tag --classifier <name> <major|minor|patch>

# Show tag status for all classifiers
mlserver tag

# Show tag status with MLServer commit info
mlserver tag --detailed
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--classifier <name>` | Classifier to tag | Required for tagging |
| `<bump>` | Version bump type | Required: major\|minor\|patch |
| `--force` | Allow tagging with uncommitted changes | `false` |
| `--allow-missing-mlserver` | Tag without MLServer commit (dev mode) | `false` |

#### Examples

**Create Tags:**
```bash
# Patch release (bug fixes)
mlserver tag --classifier sentiment patch

# Minor release (new features, backward compatible)
mlserver tag --classifier intent minor

# Major release (breaking changes)
mlserver tag --classifier fraud major
```

**Output:**
```
✓ Created tag: sentiment-v1.0.3-mlserver-b5dff2a

  📝 Version: 1.0.2 → 1.0.3 (patch bump)
  🔧 MLServer commit: b5dff2a
  📦 Classifier commit: c5f9997

Next steps:
  1. Push tags to remote: git push --tags
  2. Build container: mlserver build --classifier sentiment
  3. Push to registry: mlserver push --registry <url>
```

**View Status:**
```bash
# Show all classifier tag status
mlserver tag
```

**Output:**
```
                      🏷️  Classifier Version Status
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Classifier        ┃ Version ┃ MLServer  ┃ Status ┃ Action Required ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ sentiment         │ 1.0.3   │ b5dff2a ✓ │ Ready  │ -               │
│ intent            │ 2.0.1   │ b5dff2a ✓ │ Ready  │ -               │
│ fraud             │ 0.5.0   │ a3c2f1d ⚠ │ Behind │ Update MLServer │
└───────────────────┴─────────┴───────────┴────────┴─────────────────┘

Current MLServer commit: b5dff2a
```

#### Tag Validation

Tags are validated before creation:
- ✅ Working directory must be clean (or use `--force`)
- ✅ Classifier code must be committed
- ✅ MLServer commit must be available (or use `--allow-missing-mlserver`)
- ✅ Version must follow semantic versioning

#### Reproducibility Workflow

1. **Tag Creation**: Captures exact state
   ```bash
   mlserver tag --classifier sentiment patch
   # Creates: sentiment-v1.0.3-mlserver-b5dff2a
   ```

2. **Build Container**: Uses tag information
   ```bash
   mlserver build --classifier sentiment-v1.0.3-mlserver-b5dff2a
   ```
   - Validates current code matches tag
   - Adds container labels with all commit info
   - Warns if code has changed since tag

3. **Reproduce Exact Build**: Checkout and rebuild
   ```bash
   git checkout sentiment-v1.0.3-mlserver-b5dff2a
   mlserver build --classifier sentiment
   ```

#### Multi-Classifier Tagging

Each classifier is tagged independently:
```bash
# Tag different classifiers at different versions
mlserver tag --classifier sentiment patch  # v1.0.3
mlserver tag --classifier intent minor     # v2.1.0
mlserver tag --classifier fraud major      # v3.0.0

# View all tags
mlserver tag
```

---

### `build` - Build Docker Container

Build a Docker container for the ML server with full reproducibility tracking.

#### Syntax
```bash
ml_server build [options]
mlserver build [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--classifier <name>` | Classifier name or full hierarchical tag | Auto-detect |
| `--tag` | Container tag override | Auto-generate from git tag |
| `--registry` | Registry URL | None |
| `--config` | Config file path | Auto-detect |
| `--no-cache` | Disable Docker cache | `false` |
| `--platform` | Target platform | `linux/amd64` |
| `--push` | Push after build | `false` |
| `--force` | Skip validation warnings | `false` |

#### Examples

**Simple Build:**
```bash
# Auto-build with version tag
mlserver build

# Build specific classifier
mlserver build --classifier sentiment
```

**Build with Full Hierarchical Tag:**
```bash
# Build exact tagged version (with validation)
mlserver build --classifier sentiment-v1.0.3-mlserver-b5dff2a

# Output shows validation:
🏗️  Building container...
→ Full tag provided: sentiment-v1.0.3-mlserver-b5dff2a

✓ Current code matches tag specification

→ Building for classifier: sentiment
```

**Validation Warnings:**
```bash
# If code doesn't match tag
mlserver build --classifier sentiment-v1.0.2-mlserver-old123

⚠️  Warning: Current code doesn't match tag specifications

Tag specifies:
  Classifier commit: 08472c7
  MLServer commit:   old123

Current working directory:
  Classifier commit: c5f9997 ⚠️  MISMATCH
  MLServer commit:   b5dff2a ⚠️  MISMATCH

Building with CURRENT code. To build exact tagged version:
  git checkout sentiment-v1.0.2-mlserver-old123

# Use --force to skip prompt
mlserver build --classifier sentiment-v1.0.2-mlserver-old123 --force
```

**Advanced Builds:**
```bash
# Custom tag
mlserver build --tag my-model:v1.0.0

# Build and push
mlserver build --registry gcr.io/project --push

# Fresh build
mlserver build --no-cache

# Multi-platform
mlserver build --platform linux/amd64,linux/arm64
```

#### Container Labels

Built containers include comprehensive labels for full traceability:
```dockerfile
# Classifier information
LABEL com.classifier.name="sentiment"
LABEL com.classifier.version="1.0.3"
LABEL com.classifier.git_tag="sentiment-v1.0.3-mlserver-b5dff2a"
LABEL com.classifier.git_commit="c5f9997"
LABEL com.classifier.git_branch="main"

# MLServer tool information
LABEL com.mlserver.version="0.3.2"
LABEL com.mlserver.commit="b5dff2a"
LABEL com.mlserver.git_url="https://github.com/org/mlserver"

# OCI standard labels
LABEL org.opencontainers.image.version="1.0.3"
LABEL org.opencontainers.image.created="2025-10-27T10:30:00Z"
LABEL org.opencontainers.image.title="sentiment ML Server"
```

#### Reproducibility

Container labels enable exact reproduction:
```bash
# Inspect container to get tag
docker inspect my-container | grep com.classifier.git_tag

# Checkout exact version
git checkout sentiment-v1.0.3-mlserver-b5dff2a

# Rebuild identically
mlserver build --classifier sentiment
```

#### Output
```
🏗️  Building Docker container...
→ Classifier: sentiment v1.0.3
→ MLServer: b5dff2a
→ Base image: python:3.9-slim

📝 Installing dependencies...
✅ Built: sentiment:v1.0.3
📏 Size: 450 MB
🏷️  Labels: 17 added for traceability
```

---

### `push` - Push Container

Push built container to a registry.

#### Syntax
```bash
ml_server push [options]
mlserver push [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--registry` | Registry URL | Required |
| `--tag` | Container tag | Latest built |
| `--all` | Push all tags | `false` |

#### Examples
```bash
# Push latest
mlserver push --registry gcr.io/project

# Push specific tag
mlserver push --registry gcr.io/project --tag v1.0.0

# Push all versions
mlserver push --registry gcr.io/project --all
```

---

### `status` - System Status (Modern CLI Only)

Display comprehensive system and server status.

#### Syntax
```bash
mlserver status [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--url` | Server URL | `http://localhost:8000` |
| `--detailed` | Show detailed info | `false` |

#### Output
```
╭─ Server Status ──────────────────────────────────────────────────╮
│ Status       │ ✅ Healthy                                        │
│ Model        │ catboost-survival v1.0.0                         │
│ Uptime       │ 2 hours, 15 minutes                              │
│ Requests     │ 1,234                                            │
│ Avg Latency  │ 45ms                                             │
│ Errors       │ 2 (0.16%)                                        │
╰──────────────────────────────────────────────────────────────────╯
```

---

### `list-classifiers` - List Available Models

Show all classifiers in a multi-classifier configuration.

#### Syntax
```bash
mlserver list-classifiers [config]
```

#### Output
```
╭─ Available Classifiers ──────────────────────────────────────────╮
│ Name         │ Version │ Status     │ Description              │
├──────────────┼─────────┼────────────┼──────────────────────────┤
│ catboost     │ 1.0.0   │ Default ✓  │ CatBoost model          │
│ randomforest │ 2.0.0   │ Available  │ RandomForest model      │
│ xgboost      │ 1.5.0   │ Available  │ XGBoost model           │
╰──────────────────────────────────────────────────────────────────╯
```

---

### `version` - Version Information

Display version and environment information, including MLServer tool details.

#### Syntax
```bash
ml_server version [options]
mlserver version [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--json` | JSON output | `false` |
| `--detailed` | Include MLServer tool information | `false` |

#### Examples
```bash
# Basic version (classifier only)
mlserver version

# JSON format
mlserver version --json

# With MLServer tool details
mlserver version --detailed
```

#### Output (Modern CLI)

**Basic:**
```
╭─ MLServer Version ───────────────────────────────────────────────╮
│ Classifier   │ sentiment                                        │
│ Version      │ 1.0.3                                            │
│ Python       │ 3.9.15                                           │
│ FastAPI      │ 0.110.0                                          │
│ Platform     │ Darwin 24.0.0                                    │
╰──────────────────────────────────────────────────────────────────╯
```

**Detailed (with `--detailed` flag):**
```
╭─ MLServer Version ───────────────────────────────────────────────╮
│ Classifier   │ sentiment                                        │
│ Version      │ 1.0.3                                            │
│ Python       │ 3.9.15                                           │
│ FastAPI      │ 0.110.0                                          │
│ Platform     │ Darwin 24.0.0                                    │
│                                                                  │
│ MLServer Tool                                                    │
│   Version    │ 0.3.2.dev0                                       │
│   Commit     │ b5dff2a                                          │
│   Install    │ git (editable)                                   │
│   Location   │ /path/to/mlserver                                │
╰──────────────────────────────────────────────────────────────────╯
```

**JSON Output:**
```bash
mlserver version --json --detailed
```

```json
{
  "classifier": {
    "name": "sentiment",
    "version": "1.0.3"
  },
  "python": "3.9.15",
  "fastapi": "0.110.0",
  "platform": "Darwin 24.0.0",
  "mlserver_tool": {
    "version": "0.3.2.dev0",
    "commit": "b5dff2a",
    "install_type": "git (editable)",
    "location": "/path/to/mlserver"
  }
}
```

#### Use Cases

**Development:**
```bash
# Check which MLServer version you're developing with
mlserver version --detailed

# Verify you're using editable install
mlserver version --detailed | grep "Install"
```

**Debugging:**
```bash
# Get full version info for bug reports
mlserver version --detailed --json > version-info.json
```

**CI/CD:**
```bash
# Verify MLServer commit in build pipeline
mlserver version --detailed | grep "Commit"
```

---

### `images` - List Docker Images

List all built ML server Docker images.

#### Syntax
```bash
ml_server images [options]
mlserver images [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format | `table` |
| `--filter` | Filter images | None |

#### Output
```
╭─ Docker Images ──────────────────────────────────────────────────╮
│ Repository   │ Tag     │ Size    │ Created              │       │
├──────────────┼─────────┼─────────┼──────────────────────┼───────┤
│ ml-model     │ v1.0.0  │ 450 MB  │ 2 hours ago         │       │
│ ml-model     │ v0.9.0  │ 445 MB  │ 1 day ago           │       │
│ ml-model     │ latest  │ 450 MB  │ 2 hours ago         │       │
╰──────────────────────────────────────────────────────────────────╯
```

---

### `clean` - Remove Docker Images

Clean up built ML server Docker images.

#### Syntax
```bash
ml_server clean [options]
mlserver clean [options]
```

#### Options
| Option | Description | Default |
|--------|-------------|---------|
| `--all` | Remove all images | `false` |
| `--force` | Skip confirmation | `false` |
| `--keep-latest` | Keep latest version | `true` |

#### Examples
```bash
# Interactive clean
mlserver clean

# Remove all
mlserver clean --all --force

# Keep only latest
mlserver clean --keep-latest
```

---

## Environment Variables

Override CLI defaults using environment variables:

```bash
# Server configuration
export MLSERVER_HOST="0.0.0.0"
export MLSERVER_PORT="8080"
export MLSERVER_WORKERS="4"

# Logging
export MLSERVER_LOG_LEVEL="DEBUG"
export MLSERVER_STRUCTURED_LOGGING="true"

# Metrics
export MLSERVER_METRICS="true"
export MLSERVER_METRICS_PORT="9090"

# API settings
export MLSERVER_CORS_ENABLED="true"
export MLSERVER_MAX_CONCURRENT_REQUESTS="100"
```

## Configuration File Detection

The CLI automatically detects configuration files in this order:

1. Explicitly provided path
2. `mlserver.yaml` (preferred)
3. `config.yaml`
4. `mlserver_multi.yaml`
5. Any `*.yaml` with valid configuration

## Advanced Usage

### Multi-Classifier Deployment

```bash
# List available classifiers
mlserver list-classifiers multi.yaml

# Deploy specific classifier
mlserver serve multi.yaml --classifier production

# Deploy multiple instances
mlserver serve multi.yaml --classifier staging --port 8001 &
mlserver serve multi.yaml --classifier production --port 8002 &
```

### Development Workflow

```bash
# Start with auto-reload
mlserver serve --reload --log-level DEBUG

# Monitor logs
mlserver logs --follow

# Check status
mlserver status --detailed

# Run tests
mlserver test
```

### Production Deployment

```bash
# Build container
mlserver build --tag prod:v1.0.0

# Run health checks
mlserver health --url https://api.example.com

# Push to registry
mlserver push --registry gcr.io/project --tag prod:v1.0.0

# Deploy to Kubernetes
kubectl apply -f deployment.yaml
```

## Debugging

### Verbose Output

```bash
# Maximum verbosity
mlserver serve -vvv

# Debug logging
mlserver serve --log-level DEBUG

# Trace requests
mlserver serve --trace
```

### Dry Run

```bash
# Preview without starting
mlserver serve --dry-run

# Preview build
mlserver build --dry-run
```

### Configuration Validation

```bash
# Validate config
mlserver validate mlserver.yaml

# Print resolved config
mlserver config --print
```

## Common Issues

### Port Already in Use

```bash
# Use different port
mlserver serve --port 8001

# Kill existing process
lsof -ti:8000 | xargs kill -9
```

### Module Not Found

```bash
# Check Python path
mlserver debug --python-path

# Verify module
mlserver validate --check-imports
```

### Permission Denied

```bash
# Use sudo for system ports
sudo mlserver serve --port 80

# Or use high port
mlserver serve --port 8080
```

## Shell Completion

Enable tab completion for commands:

```bash
# Bash
mlserver --install-completion bash
source ~/.bashrc

# Zsh
mlserver --install-completion zsh
source ~/.zshrc

# Fish
mlserver --install-completion fish
```

## Tips and Tricks

### Quick Commands

```bash
# Serve with defaults
mlserver serve

# Quick status check
mlserver status

# List models
mlserver ls

# Show logs
mlserver logs
```

### Aliases

Add to your shell profile:

```bash
alias mls='mlserver serve'
alias mlb='mlserver build'
alias mlp='mlserver push'
alias mli='mlserver info'
```

### Docker Integration

```bash
# Build and run locally
mlserver build --tag local
docker run -p 8000:8000 local

# Multi-stage deployment
mlserver build --target development --tag dev
mlserver build --target production --tag prod
```