"""
GitHub Actions CI/CD workflow generation for MLServer projects.
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple


def get_git_remote_info(project_path: str = ".") -> Optional[Dict[str, str]]:
    """Extract GitHub repository information from git remote."""
    try:
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=project_path,
            stderr=subprocess.DEVNULL
        ).decode().strip()

        if not remote_url:
            return None

        # Parse GitHub repository from URL
        # Handle both HTTPS and SSH formats:
        # - https://github.com/owner/repo.git
        # - git@github.com:owner/repo.git

        if "github.com" not in remote_url:
            return None

        # Extract owner and repo
        if remote_url.startswith("git@"):
            # SSH format: git@github.com:owner/repo.git
            match = re.search(r'github\.com:([^/]+)/(.+?)(?:\.git)?$', remote_url)
        else:
            # HTTPS format: https://github.com/owner/repo.git
            match = re.search(r'github\.com/([^/]+)/(.+?)(?:\.git)?$', remote_url)

        if match:
            owner = match.group(1)
            repo = match.group(2)
            return {
                "owner": owner,
                "repo": repo,
                "url": remote_url,
                "is_github": True
            }

        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_mlserver_source_url(project_path: str = ".") -> str:
    """Determine the MLServer source URL for installation in CI/CD.

    Returns the git URL to use for installing MLServer in the workflow.
    """
    # Try to detect if we're in a development setup
    try:
        # Check if mlserver module has a git repository
        import mlserver
        mlserver_path = Path(mlserver.__file__).parent.parent

        if (mlserver_path / '.git').exists():
            # We're in a git repository - try to get remote URL
            try:
                remote_url = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=str(mlserver_path),
                    stderr=subprocess.DEVNULL
                ).decode().strip()

                if remote_url:
                    return remote_url
            except:
                pass
    except:
        pass

    # Default to the main repository
    return "https://github.com/alxhrzg/merve.git"


def generate_build_and_push_workflow(
    repo_name: str,
    mlserver_source_url: str,
    python_version: str = "3.11",
    registry_config: Optional[Dict] = None
) -> str:
    """Generate the ml-classifier-container-build.yml workflow content.

    Args:
        repo_name: Name of the repository
        mlserver_source_url: Git URL for MLServer installation
        python_version: Python version to use
        registry_config: Registry configuration from mlserver.yaml deployment.registry section
    """

    # Get MLServer version for workflow versioning
    try:
        from mlserver import _version_info
        mlserver_version = _version_info.VERSION
        workflow_version = "2.0"  # Increment when workflow structure changes incompatibly
    except:
        mlserver_version = "unknown"
        workflow_version = "2.0"

    # Extract registry configuration
    if registry_config is None:
        registry_config = {}

    registry_type = registry_config.get('type', 'ghcr')

    # Extract ECR configuration
    ecr_config = registry_config.get('ecr', {})
    ecr_aws_region = ecr_config.get('aws_region', 'eu-central-1')
    ecr_role_arn = ecr_config.get('role_arn')
    ecr_registry_id = ecr_config.get('registry_id')
    ecr_repository_prefix = ecr_config.get('repository_prefix', 'ml-classifiers')

    # Validate ECR configuration if type is 'ecr'
    if registry_type == 'ecr':
        if not ecr_registry_id:
            raise ValueError(
                f"ECR registry type selected but registry_id is missing in mlserver.yaml.\n\n"
                f"Please add registry_id to mlserver.yaml under deployment.registry.ecr:\n"
                f"  registry_id: '123456789012'  # Your AWS account ID"
            )

    # Build AWS/ECR configuration strings for template
    # Role ARN: Always use GitHub variable (can differ per environment/repo)
    # Registry ID: Bake from mlserver.yaml (fixed for organization)
    # Region: Use environment variable from workflow env section
    aws_role_arn_value = "${{ vars.AWS_RUNNER_ROLE_ARN }}"

    if ecr_registry_id:
        ecr_registry_value = f"'{ecr_registry_id}'"
        ecr_registry_url = f"{ecr_registry_id}.dkr.ecr.{ecr_aws_region}.amazonaws.com"
    else:
        ecr_registry_value = "'${{ vars.ECR_REGISTRY_ID }}'"
        ecr_registry_url = "${{ vars.ECR_REGISTRY_ID }}.dkr.ecr." + ecr_aws_region + ".amazonaws.com"

    ecr_repo_prefix_value = f'"{ecr_repository_prefix}"'

    # Build header with current registry configuration
    if registry_type == 'ecr':
        config_info = f"""# Registry Configuration: AWS ECR
#   - AWS Region: {ecr_aws_region} (from mlserver.yaml, set in env.AWS_REGION)
#   - Registry ID: {ecr_registry_id} (from mlserver.yaml, baked into workflow)
#   - Role ARN: From GitHub repository variable 'AWS_RUNNER_ROLE_ARN'
#   - Repository Prefix: {ecr_repository_prefix} (from mlserver.yaml)
#
# Required GitHub Repository Variable:
#   - AWS_RUNNER_ROLE_ARN: IAM role ARN for OIDC (e.g., arn:aws:iam::123456789012:role/GitHubActionsRole)
#
# To update registry_id/region/prefix: modify mlserver.yaml and regenerate with mlserver init-github --force"""
    else:
        config_info = """# Registry Configuration: GitHub Container Registry (GHCR)
#   - Uses GITHUB_TOKEN for authentication
#   - Pushes to ghcr.io"""

    template = f"""# ============================================================================
# ML Classifier Container Build & Publish Workflow
# ============================================================================
# Generated by MLServer {mlserver_version}
# Workflow version: {workflow_version} (with configurable registry support)
#
{config_info}
#
# To change registry configuration, update mlserver.yaml and regenerate:
#   mlserver init-github --force
# ============================================================================
name: Build & Publish ML Classifier Container

on:
  push:
    tags:
      - '*-v*-mlserver-*'  # Match hierarchical tag format

permissions:
  contents: read
  packages: write   # required to push to GHCR
  id-token: write   # required for ECR OIDC authentication

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    env:
      # Registry type (configured from mlserver.yaml)
      REGISTRY_TYPE: "{registry_type}"
      AWS_REGION: "{ecr_aws_region}"

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          fetch-tags: true
      # Step 1: Parse hierarchical tag
      - name: Parse Hierarchical Tag
        id: parse
        shell: bash
        run: |
          set -euo pipefail
          TAG_NAME="${{GITHUB_REF#refs/tags/}}"
          echo "Full tag: $TAG_NAME"

          # Example tag: classifier-v0.1.0-mlserver-abc123
          CLASSIFIER=$(echo "$TAG_NAME" | sed -E 's/^([a-zA-Z0-9_-]+)-v.*/\\1/')
          VERSION=$(echo "$TAG_NAME" | sed -E 's/^[a-zA-Z0-9_-]+-v([0-9]+\\.[0-9]+\\.[0-9]+)-.*/\\1/')
          MLSERVER=$(echo "$TAG_NAME" | sed -E 's/.*-mlserver-([a-f0-9]+)$/\\1/')
          CLASSIFIER_COMMIT="${{GITHUB_SHA:0:7}}"

          echo "classifier=$CLASSIFIER"       >> "$GITHUB_OUTPUT"
          echo "version=$VERSION"            >> "$GITHUB_OUTPUT"
          echo "mlserver_commit=$MLSERVER"   >> "$GITHUB_OUTPUT"
          echo "classifier_commit=$CLASSIFIER_COMMIT" >> "$GITHUB_OUTPUT"
          echo "full_tag=$TAG_NAME"          >> "$GITHUB_OUTPUT"

          echo "Parsed:"
          echo "  Classifier: $CLASSIFIER"
          echo "  Version:    $VERSION"
          echo "  MLServer:   $MLSERVER"
          echo "  Classifier commit: $CLASSIFIER_COMMIT"

      # Step 2: Checkout classifier repository at tagged commit
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{{{ github.ref }}}}
          fetch-depth: 0

      # Step 3: Set up Python
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '{python_version}'

      # Step 4: Create venv and install MLServer at correct commit
      - name: Install MLServer at Correct Commit
        shell: bash
        run: |
          set -euo pipefail
          echo "Installing MLServer at commit ${{{{ steps.parse.outputs.mlserver_commit }}}}"
          python -m venv mlserver-venv
          source mlserver-venv/bin/activate
          pip install --upgrade pip
          pip install "git+{mlserver_source_url}@${{{{ steps.parse.outputs.mlserver_commit }}}}"

          # Verify installation with version command (from /tmp to avoid config parsing)
          echo "Verifying MLServer installation:"
          cd /tmp
          mlserver version --json
          cd -

          # Extract and verify commit from version output
          INSTALLED_COMMIT=$(cd /tmp && mlserver version --json | python -c "import sys, json; print(json.load(sys.stdin)['mlserver_tool']['commit'])")
          EXPECTED_COMMIT="${{{{ steps.parse.outputs.mlserver_commit }}}}"

          echo "Expected MLServer commit: $EXPECTED_COMMIT"
          echo "Installed MLServer commit: $INSTALLED_COMMIT"

          if [ "$INSTALLED_COMMIT" != "$EXPECTED_COMMIT" ]; then
            echo "❌ ERROR: MLServer commit mismatch!"
            echo "  Expected: $EXPECTED_COMMIT"
            echo "  Installed: $INSTALLED_COMMIT"
            exit 1
          fi

          echo "✅ MLServer installed successfully at commit ${{{{ steps.parse.outputs.mlserver_commit }}}}"

      # Step 5: Set up Docker Buildx
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      # Step 5a: Configure AWS credentials (ECR only)
      - name: 🔑 Configure AWS credentials
        if: env.REGISTRY_TYPE == 'ecr'
        uses: aws-actions/configure-aws-credentials@v5
        with:
          role-to-assume: {aws_role_arn_value}
          role-session-name: GitHubActions-${{{{ github.job }}}}
          aws-region: ${{{{ env.AWS_REGION }}}}

      # Step 5b: Login to Amazon ECR (ECR only)
      - name: 🔐 Login to Amazon ECR
        if: env.REGISTRY_TYPE == 'ecr'
        uses: aws-actions/amazon-ecr-login@v2
        with:
          registries: {ecr_registry_value}

      # Step 6: Build container (local image name)
      - name: Build Container
        shell: bash
        run: |
          set -euo pipefail
          source mlserver-venv/bin/activate
          echo "Building container for ${{{{ steps.parse.outputs.classifier }}}}"
          echo "  Version: ${{{{ steps.parse.outputs.version }}}}"
          echo "  Full tag: ${{{{ steps.parse.outputs.full_tag }}}}"
          python -m mlserver.cli build --classifier "${{{{ steps.parse.outputs.classifier }}}}"
          echo "Container built successfully"

      # Step 7: Inspect Build Artifacts
      - name: Inspect Build Artifacts
        shell: bash
        run: |
          set -euo pipefail
          echo "=================================================="
          echo "📋 BUILD ARTIFACTS INSPECTION"
          echo "=================================================="
          echo ""

          # Show Dockerfile
          echo "📄 Generated Dockerfile:"
          echo "--------------------------------------------------"
          if [ -f "Dockerfile" ]; then
            cat Dockerfile
          else
            echo "⚠️  Dockerfile not found in workspace"
          fi
          echo ""
          echo "=================================================="
          echo ""

          # Extract and show mlserver.yaml from the container
          echo "📄 Container mlserver.yaml (config inside container):"
          echo "--------------------------------------------------"

          # Create a temporary container to extract the config
          TEMP_CONTAINER=$(docker create "{repo_name}/${{{{ steps.parse.outputs.classifier }}}}:latest")

          # Copy mlserver.yaml from container
          if docker cp "$TEMP_CONTAINER:/app/mlserver.yaml" "./mlserver.yaml.container" 2>/dev/null; then
            cat "./mlserver.yaml.container"
            rm -f "./mlserver.yaml.container"
          else
            echo "⚠️  Could not extract mlserver.yaml from container"
          fi

          # Clean up temporary container
          docker rm "$TEMP_CONTAINER" >/dev/null 2>&1

          echo ""
          echo "=================================================="
          echo ""

          # Show summary
          echo "ℹ️  Note: For multi-classifier repos, the container mlserver.yaml"
          echo "   contains only the configuration for classifier: ${{{{ steps.parse.outputs.classifier }}}}"
          echo "   (extracted from the multi-classifier source config)"
          echo ""

          # Also add to GitHub Actions step summary
          echo "## 📋 Build Artifacts" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### 📄 Generated Dockerfile" >> $GITHUB_STEP_SUMMARY
          echo '```dockerfile' >> $GITHUB_STEP_SUMMARY
          if [ -f "Dockerfile" ]; then
            cat Dockerfile >> $GITHUB_STEP_SUMMARY
          else
            echo "Dockerfile not found" >> $GITHUB_STEP_SUMMARY
          fi
          echo '```' >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY

          echo "### 📄 Container mlserver.yaml" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "> **Note**: For multi-classifier repos, this shows the extracted single-classifier config for \\\`${{{{ steps.parse.outputs.classifier }}}}\\\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo '```yaml' >> $GITHUB_STEP_SUMMARY

          # Re-extract for summary (the file was already removed)
          TEMP_CONTAINER2=$(docker create "{repo_name}/${{{{ steps.parse.outputs.classifier }}}}:latest")
          if docker cp "$TEMP_CONTAINER2:/app/mlserver.yaml" "./mlserver.yaml.container2" 2>/dev/null; then
            cat "./mlserver.yaml.container2" >> $GITHUB_STEP_SUMMARY
            rm -f "./mlserver.yaml.container2"
          else
            echo "Could not extract mlserver.yaml from container" >> $GITHUB_STEP_SUMMARY
          fi
          docker rm "$TEMP_CONTAINER2" >/dev/null 2>&1

          echo '```' >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY

      # Step 8: Verify container labels
      - name: Verify Container Labels
        shell: bash
        run: |
          set -euo pipefail
          echo "Inspecting container labels..."
          docker inspect "{repo_name}/${{{{ steps.parse.outputs.classifier }}}}:latest" | grep -A 20 '"Labels":' || true

      # Step 9: Test container
      - name: Test Container
        shell: bash
        run: |
          set -euo pipefail
          echo "Testing container..."

          # Start container
          docker run -d -p 8000:8000 --name test-container "{repo_name}/${{{{ steps.parse.outputs.classifier }}}}:latest"

          # Check if container is running
          echo "Waiting for container to be ready..."
          sleep 5

          if ! docker ps | grep -q test-container; then
            echo "❌ Container failed to start!"
            docker logs test-container
            exit 1
          fi

          echo "Container is running, checking health endpoint..."

          # Wait for health endpoint (disable exit-on-error for retry loop)
          set +e
          for i in {{1..30}}; do
            if curl -fsS "http://localhost:8000/healthz" >/dev/null 2>&1; then
              echo "✅ Health check passed after ${{i}} attempts"
              break
            fi
            echo "Attempt ${{i}}/30 failed, retrying..."
            sleep 2
          done
          set -e

          # Final health check (this will fail the build if not ready)
          echo "Final health check:"
          curl -f "http://localhost:8000/healthz"

          echo "Checking info endpoint:"
          curl -f "http://localhost:8000/info" || true

          echo "Container logs:"
          docker logs test-container | tail -20

          # Cleanup
          docker stop test-container
          docker rm test-container
          echo "✅ Container tests passed"

      # Step 10: Log in to GHCR (GHCR only)
      - name: Log in to GHCR
        if: env.REGISTRY_TYPE == 'ghcr'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      # Step 11: Tag and Push to Registry
      - name: Push to Registry
        id: push
        shell: bash
        run: |
          set -euo pipefail

          CLASSIFIER="${{{{ steps.parse.outputs.classifier }}}}"
          VERSION="${{{{ steps.parse.outputs.version }}}}"
          MLSERVER="${{{{ steps.parse.outputs.mlserver_commit }}}}"
          REGISTRY_TYPE="${{{{ env.REGISTRY_TYPE }}}}"

          echo "Registry type: $REGISTRY_TYPE"

          # Determine registry URL and image base based on registry type
          if [ "$REGISTRY_TYPE" = "ecr" ]; then
            # ECR configuration (hard-coded from mlserver.yaml)
            REGISTRY_URL="{ecr_registry_url}"
            REPOSITORY_PREFIX={ecr_repo_prefix_value}
            IMAGE_BASE="${{REPOSITORY_PREFIX}}/${{CLASSIFIER}}"
            echo "Using ECR registry: $REGISTRY_URL"
          else
            # GHCR configuration (default)
            REGISTRY_URL="ghcr.io"
            OWNER_LOWER="$(echo "${{{{ github.repository_owner }}}}" | tr '[:upper:]' '[:lower:]')"
            IMAGE_BASE="${{OWNER_LOWER}}/{repo_name}-${{CLASSIFIER}}"
            echo "Using GHCR registry: $REGISTRY_URL"
          fi

          # Build image references
          IMAGE_LATEST="${{REGISTRY_URL}}/${{IMAGE_BASE}}:latest"
          IMAGE_VERSION="${{REGISTRY_URL}}/${{IMAGE_BASE}}:${{VERSION}}"
          IMAGE_FULLTAG="${{REGISTRY_URL}}/${{IMAGE_BASE}}:${{VERSION}}-mlserver-${{MLSERVER}}"

          echo "Using image repository: ${{REGISTRY_URL}}/${{IMAGE_BASE}}"

          # Tag local image to registry references
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_LATEST"
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_VERSION"
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_FULLTAG"

          # Push all tags
          echo "Pushing images..."
          docker push "$IMAGE_LATEST"
          docker push "$IMAGE_VERSION"
          docker push "$IMAGE_FULLTAG"

          # Expose outputs for release notes
          {{
            echo "registry_type=$REGISTRY_TYPE"
            echo "registry_url=$REGISTRY_URL"
            echo "image_latest=$IMAGE_LATEST"
            echo "image_version=$IMAGE_VERSION"
            echo "image_fulltag=$IMAGE_FULLTAG"
          }} >> "$GITHUB_OUTPUT"

          echo "✅ Successfully pushed all images to $REGISTRY_TYPE"

      # Step 12: Summary
      - name: Build Summary
        shell: bash
        run: |
          echo "## 🎉 Build & Push Complete" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Classifier:** ${{{{ steps.parse.outputs.classifier }}}}" >> $GITHUB_STEP_SUMMARY
          echo "**Version:** ${{{{ steps.parse.outputs.version }}}}" >> $GITHUB_STEP_SUMMARY
          echo "**Tag:** ${{{{ steps.parse.outputs.full_tag }}}}" >> $GITHUB_STEP_SUMMARY
          echo "**Registry:** ${{{{ steps.push.outputs.registry_type }}}} (\\`${{{{ steps.push.outputs.registry_url }}}}\\`)" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Published Images:**" >> $GITHUB_STEP_SUMMARY
          echo "- \\`${{{{ steps.push.outputs.image_latest }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "- \\`${{{{ steps.push.outputs.image_version }}}}\\`" >> $GITHUB_STEP_SUMMARY
          echo "- \\`${{{{ steps.push.outputs.image_fulltag }}}}\\`" >> $GITHUB_STEP_SUMMARY
"""

    return template


def init_github_actions(
    project_path: str = ".",
    python_version: str = "3.11",
    registry: str = "ghcr.io",
    force: bool = False
) -> Tuple[bool, str, Dict[str, str]]:
    """
    Initialize GitHub Actions CI/CD for the project.

    Args:
        project_path: Path to the project directory
        python_version: Python version to use
        registry: Registry URL (deprecated - use mlserver.yaml instead)
        force: Force overwrite of existing workflow files

    Returns:
        Tuple of (success, message, files_created)
    """
    project_path = Path(project_path).resolve()

    # Check if we're in a git repository
    if not (project_path / ".git").exists():
        return False, "Not a git repository. Initialize git first with: git init", {}

    # Get git remote info
    git_info = get_git_remote_info(str(project_path))
    if not git_info:
        return False, "No GitHub remote found. Add GitHub remote first with: git remote add origin <url>", {}

    # Get repository name from directory or git
    from .version import get_repository_name
    repo_name = get_repository_name(str(project_path))

    # Get MLServer source URL
    mlserver_url = get_mlserver_source_url(str(project_path))

    # Read registry configuration from mlserver.yaml if it exists
    registry_config = None
    mlserver_yaml_path = project_path / "mlserver.yaml"
    if mlserver_yaml_path.exists():
        try:
            import yaml
            with open(mlserver_yaml_path, 'r') as f:
                config = yaml.safe_load(f)
                if config and 'deployment' in config and 'registry' in config['deployment']:
                    registry_config = config['deployment']['registry']
        except Exception as e:
            # If we can't read the config, fall back to defaults
            pass

    # Create .github/workflows directory
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Check if ml-classifier-container-build.yml already exists
    workflow_file = workflows_dir / "ml-classifier-container-build.yml"
    files_created = {}

    if workflow_file.exists() and not force:
        return False, f"Workflow file already exists: {workflow_file}\nUse --force to overwrite", {}

    # Generate and write workflow
    workflow_content = generate_build_and_push_workflow(
        repo_name=repo_name,
        mlserver_source_url=mlserver_url,
        python_version=python_version,
        registry_config=registry_config
    )

    with open(workflow_file, 'w') as f:
        f.write(workflow_content)

    files_created["workflow"] = str(workflow_file.relative_to(project_path))

    # Create a README for the workflows directory
    readme_file = workflows_dir / "README.md"
    if not readme_file.exists():
        readme_content = r"""# GitHub Actions Workflows

## ml-classifier-container-build.yml

Automatically builds and publishes Docker containers to container registries when hierarchical tags are pushed.

### Supported Registries

1. **GHCR (GitHub Container Registry)** - Default, no additional setup required
2. **ECR (AWS Elastic Container Registry)** - Configured via mlserver.yaml

### Trigger

Workflow is triggered when a tag matching the pattern `*-v*-mlserver-*` is pushed.

Example tag: `sentiment-v1.0.0-mlserver-abc123d`

### What it does

1. Parses the hierarchical tag to extract:
   - Classifier name
   - Version number
   - MLServer commit hash
   - Classifier commit hash

2. Installs MLServer at the exact commit specified in the tag

3. Builds the Docker container for the classifier

4. Tests the container (health checks)

5. Authenticates with the configured registry (GHCR or ECR)

6. Pushes images with multiple tags:
   - `latest`
   - `{version}`
   - `{version}-mlserver-{commit}`

### Usage

Create and push a hierarchical tag using:

```bash
mlserver tag patch --classifier <classifier-name>
git push --tags
```

The workflow will automatically build and publish your container.

### Configuration

Registry configuration is read from `mlserver.yaml` under `deployment.registry` and **baked into the generated workflow file**.

#### GHCR (Default)

No additional setup required. Uses `GITHUB_TOKEN` automatically.

```yaml
deployment:
  registry:
    type: "ghcr"
```

#### ECR

**Step 1**: Configure ECR settings in `mlserver.yaml` under `deployment.registry`:

```yaml
deployment:
  registry:
    type: "ecr"
    ecr:
      aws_region: "eu-central-1"          # AWS region for ECR (required)
      registry_id: "123456789012"         # AWS account ID (required)
      repository_prefix: "ml-classifiers" # Repository prefix (optional, default: "ml-classifiers")
```

**Step 2**: Set GitHub repository variable for IAM role:
- Go to: Settings → Secrets and variables → Actions → Variables
- Add variable: `AWS_RUNNER_ROLE_ARN` = `arn:aws:iam::123456789012:role/GitHubActionsRole`

**Step 3**: Generate/update the workflow:

```bash
mlserver init-github --force
git add .github && git commit -m "Update workflow for ECR"
git push
```

**Note**: Registry ID and region are baked into the workflow from mlserver.yaml. The IAM role ARN comes from GitHub repository variable (allows per-repo/per-environment configuration).

### Permissions

- **GHCR**: Requires `packages: write` (automatically granted with `GITHUB_TOKEN`)
- **ECR**: Requires `id-token: write` for OIDC authentication and GitHub repository variable `AWS_RUNNER_ROLE_ARN`
"""
        with open(readme_file, 'w') as f:
            f.write(readme_content)

        files_created["readme"] = str(readme_file.relative_to(project_path))

    # Build registry-specific instructions
    registry_type = registry_config.get('type', 'ghcr') if registry_config else 'ghcr'
    if registry_type == 'ecr':
        ecr_info = registry_config.get('ecr', {})
        registry_instructions = f"""
Registry: AWS ECR
  - Region: {ecr_info.get('aws_region', 'eu-central-1')} (baked into workflow)
  - Registry ID: {ecr_info.get('registry_id', 'N/A')} (baked into workflow)

⚠️  IMPORTANT: Set GitHub repository variable:
   - AWS_RUNNER_ROLE_ARN: Your IAM role ARN for OIDC authentication

   Go to: Settings → Secrets and variables → Actions → Variables
"""
    else:
        registry_instructions = "\nRegistry: GitHub Container Registry (GHCR)"

    success_message = f"""✅ GitHub Actions CI/CD initialized successfully!

Repository: {git_info['owner']}/{git_info['repo']}
MLServer Source: {mlserver_url}
{registry_instructions}

Created files:
  - {files_created.get('workflow', 'N/A')}
  - {files_created.get('readme', 'N/A')}

Next steps:
  1. Review the generated workflow file
  2. Commit the changes: git add .github && git commit -m "Add CI/CD workflow"
  3. Push to GitHub: git push
  4. Create a version tag: mlserver tag patch --classifier <name>
  5. Push the tag: git push --tags

The workflow will automatically build and publish your container!
"""

    return True, success_message, files_created


def check_github_actions_setup(project_path: str = ".") -> bool:
    """Check if GitHub Actions workflow is set up."""
    workflow_file = Path(project_path) / ".github" / "workflows" / "ml-classifier-container-build.yml"
    return workflow_file.exists()


def parse_workflow_version(workflow_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse MLServer version and workflow version from workflow file.

    Returns:
        Tuple of (mlserver_version, workflow_version) or (None, None) if not found
    """
    try:
        with open(workflow_path, 'r') as f:
            content = f.read()

        # Look for version markers in first few lines
        mlserver_version = None
        workflow_version = None

        for line in content.split('\n')[:10]:  # Check first 10 lines
            if '# Generated by MLServer' in line:
                # Extract: # Generated by MLServer 0.3.2.dev9
                parts = line.split('MLServer')
                if len(parts) > 1:
                    mlserver_version = parts[1].strip()
            elif '# Workflow version:' in line:
                # Extract: # Workflow version: 1.0 (with optional comment)
                # Extract only the version number, ignore comments in parentheses
                parts = line.split(':')
                if len(parts) > 1:
                    version_str = parts[1].strip()
                    # Extract just the version number (before any space or parenthesis)
                    version_parts = version_str.split()
                    if version_parts:
                        workflow_version = version_parts[0]

        return mlserver_version, workflow_version
    except Exception:
        return None, None


def validate_workflow_compatibility(
    project_path: str = ".",
    strict: bool = False
) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """
    Validate that GitHub Actions workflow is compatible with current MLServer version.

    Args:
        project_path: Path to project
        strict: If True, fail on any version mismatch. If False, only warn.

    Returns:
        Tuple of (is_valid, warning_message, details)
    """
    workflow_file = Path(project_path) / ".github" / "workflows" / "ml-classifier-container-build.yml"

    if not workflow_file.exists():
        return False, "Workflow file does not exist", {}

    # Get current MLServer version
    try:
        from mlserver import _version_info
        current_mlserver_version = _version_info.VERSION
        current_workflow_version = "2.0"  # Should match generate_build_and_push_workflow()
    except:
        current_mlserver_version = "unknown"
        current_workflow_version = "2.0"

    # Parse versions from workflow file
    file_mlserver_version, file_workflow_version = parse_workflow_version(workflow_file)

    details = {
        "current_mlserver": current_mlserver_version,
        "current_workflow": current_workflow_version,
        "file_mlserver": file_mlserver_version or "unknown",
        "file_workflow": file_workflow_version or "unknown",
    }

    # If no version markers found, this is an old/manually created workflow
    if file_mlserver_version is None or file_workflow_version is None:
        warning = (
            "Workflow file is missing version markers (generated by old MLServer or manually created). "
            "Consider regenerating with: mlserver init-github --force"
        )
        return not strict, warning if not strict else None, details

    # Check workflow version compatibility
    if file_workflow_version != current_workflow_version:
        warning = (
            f"Workflow version mismatch! File has v{file_workflow_version}, "
            f"but current MLServer expects v{current_workflow_version}. "
            "Regenerate with: mlserver init-github --force"
        )
        return False, warning, details

    # Workflow version matches - compatible
    return True, None, details
