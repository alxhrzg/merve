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
    registry: str = "ghcr.io"
) -> str:
    """Generate the ml-classifier-container-build.yml workflow content."""

    template = f"""name: Build & Publish ML Classifier Container

on:
  push:
    tags:
      - '*-v*-mlserver-*'  # Match hierarchical tag format

permissions:
  contents: read
  packages: write   # required to push to GHCR

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    env:
      REGISTRY: {registry}

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
          TAG_NAME="${{{{ GITHUB_REF#refs/tags/ }}}}"
          echo "Full tag: $TAG_NAME"

          # Example tag: classifier-v0.1.0-mlserver-abc123
          CLASSIFIER=$(echo "$TAG_NAME" | sed -E 's/^([a-zA-Z0-9_-]+)-v.*/\\1/')
          VERSION=$(echo "$TAG_NAME" | sed -E 's/^[a-zA-Z0-9_-]+-v([0-9]+\\.[0-9]+\\.[0-9]+)-.*/\\1/')
          MLSERVER=$(echo "$TAG_NAME" | sed -E 's/.*-mlserver-([a-f0-9]+)$/\\1/')
          CLASSIFIER_COMMIT="${{{{ GITHUB_SHA:0:7 }}}}"

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

      # Step 7: Verify container labels
      - name: Verify Container Labels
        shell: bash
        run: |
          set -euo pipefail
          echo "Inspecting container labels..."
          docker inspect "{repo_name}/${{{{ steps.parse.outputs.classifier }}}}:latest" | grep -A 20 '"Labels":' || true

      # Step 8: Test container
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
          for i in {{{{1..30}}}}; do
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

      # Step 9: Log in to GHCR (uses GITHUB_TOKEN)
      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: {registry}
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      # Step 10: Tag and Push to GHCR
      - name: Push to GHCR
        id: push
        shell: bash
        run: |
          set -euo pipefail

          CLASSIFIER="${{{{ steps.parse.outputs.classifier }}}}"
          VERSION="${{{{ steps.parse.outputs.version }}}}"
          MLSERVER="${{{{ steps.parse.outputs.mlserver_commit }}}}"

          # ghcr requires lower-case owner/image names
          OWNER_LOWER="$(echo "${{{{ GITHUB_REPOSITORY_OWNER }}}}" | tr '[:upper:]' '[:lower:]')"

          IMAGE_BASE="${{OWNER_LOWER}}/{repo_name}-${{CLASSIFIER}}"
          IMAGE_LATEST="${{{{ env.REGISTRY }}}}/${{IMAGE_BASE}}:latest"
          IMAGE_VERSION="${{{{ env.REGISTRY }}}}/${{IMAGE_BASE}}:${{VERSION}}"
          IMAGE_FULLTAG="${{{{ env.REGISTRY }}}}/${{IMAGE_BASE}}:${{VERSION}}-mlserver-${{MLSERVER}}"

          echo "Using image repository: ${{{{ env.REGISTRY }}}}/${{IMAGE_BASE}}"

          # Tag local image to GHCR references
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_LATEST"
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_VERSION"
          docker tag "{repo_name}/${{CLASSIFIER}}:latest" "$IMAGE_FULLTAG"

          # Push all tags
          docker push "$IMAGE_LATEST"
          docker push "$IMAGE_VERSION"
          docker push "$IMAGE_FULLTAG"

          # Expose outputs for release notes
          {{{{
            echo "image_latest=$IMAGE_LATEST"
            echo "image_version=$IMAGE_VERSION"
            echo "image_fulltag=$IMAGE_FULLTAG"
          }}}} >> "$GITHUB_OUTPUT"

          echo "✅ Successfully pushed all images"

      # Step 11: Summary
      - name: Build Summary
        shell: bash
        run: |
          echo "## 🎉 Build & Push Complete" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Classifier:** ${{{{ steps.parse.outputs.classifier }}}}" >> $GITHUB_STEP_SUMMARY
          echo "**Version:** ${{{{ steps.parse.outputs.version }}}}" >> $GITHUB_STEP_SUMMARY
          echo "**Tag:** ${{{{ steps.parse.outputs.full_tag }}}}" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Published Images:**" >> $GITHUB_STEP_SUMMARY
          echo "- \`${{{{ steps.push.outputs.image_latest }}}}\`" >> $GITHUB_STEP_SUMMARY
          echo "- \`${{{{ steps.push.outputs.image_version }}}}\`" >> $GITHUB_STEP_SUMMARY
          echo "- \`${{{{ steps.push.outputs.image_fulltag }}}}\`" >> $GITHUB_STEP_SUMMARY
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
        registry=registry
    )

    with open(workflow_file, 'w') as f:
        f.write(workflow_content)

    files_created["workflow"] = str(workflow_file.relative_to(project_path))

    # Create a README for the workflows directory
    readme_file = workflows_dir / "README.md"
    if not readme_file.exists():
        readme_content = r"""# GitHub Actions Workflows

## ml-classifier-container-build.yml

Automatically builds and publishes Docker containers to GitHub Container Registry (GHCR) when hierarchical tags are pushed.

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

5. Pushes to GitHub Container Registry with multiple tags:
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

- **Python version**: Configurable in the workflow file
- **Registry**: Default is `ghcr.io` (GitHub Container Registry)
- **MLServer source**: Auto-detected from your setup

### Permissions

The workflow requires `packages: write` permission to push to GHCR.
This is automatically granted when using `GITHUB_TOKEN` in GitHub Actions.
"""
        with open(readme_file, 'w') as f:
            f.write(readme_content)

        files_created["readme"] = str(readme_file.relative_to(project_path))

    success_message = f"""✅ GitHub Actions CI/CD initialized successfully!

Repository: {git_info['owner']}/{git_info['repo']}
MLServer Source: {mlserver_url}

Created files:
  - {files_created.get('workflow', 'N/A')}
  - {files_created.get('readme', 'N/A')}

Next steps:
  1. Review the generated workflow file
  2. Commit the changes: git add .github && git commit -m "Add CI/CD workflow"
  3. Push to GitHub: git push
  4. Create a version tag: mlserver tag patch --classifier <name>
  5. Push the tag: git push --tags

The workflow will automatically build and publish your container to GHCR!
"""

    return True, success_message, files_created


def check_github_actions_setup(project_path: str = ".") -> bool:
    """Check if GitHub Actions workflow is set up."""
    workflow_file = Path(project_path) / ".github" / "workflows" / "ml-classifier-container-build.yml"
    return workflow_file.exists()
