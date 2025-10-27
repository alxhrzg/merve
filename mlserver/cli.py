"""Modern CLI for ML Server using Typer."""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List
from enum import Enum

import typer
import yaml
import uvicorn
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import AppConfig
from .server import create_app
from .logging_conf import configure_logging
from .version import get_version_info
from .container import (
    build_container,
    list_images,
    remove_images,
    check_docker_availability
)
from .version_control import (
    GitVersionManager,
    safe_push_container,
    VersionControlError
)
from .multi_classifier import (
    load_multi_classifier_config,
    extract_single_classifier_config,
    detect_multi_classifier_config,
    list_available_classifiers,
    get_default_classifier
)

# Create the main app
app = typer.Typer(
    name="mlserver",
    help="🚀 ML Server - FastAPI-based ML model serving",
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    no_args_is_help=True,
)

console = Console()


#import typer.core
#typer.core.rich = None  # force plain Click help formatting

class LogLevel(str, Enum):
    """Log level options."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BumpType(str, Enum):
    """Version bump type options."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def resolve_relative_paths(init_kwargs: dict, config_dir: str) -> dict:
    """Resolve relative file paths in init_kwargs to be relative to config file location."""
    resolved_kwargs = {}

    for key, value in init_kwargs.items():
        if isinstance(value, str) and _is_likely_file_path(key, value):
            resolved_kwargs[key] = _resolve_path(value, config_dir)
        else:
            resolved_kwargs[key] = value

    return resolved_kwargs


def _is_likely_file_path(key: str, value: str) -> bool:
    """Check if a key-value pair likely represents a file path."""
    path_indicators = ['path', 'file', 'model', 'preprocessor', 'feature_order']
    key_suggests_path = any(indicator in key.lower() for indicator in path_indicators)

    is_relative = (
        value.startswith('./') or
        value.startswith('../') or
        (not value.startswith('/') and ':' not in value[:3])
    )

    return key_suggests_path and is_relative


def _resolve_path(path: str, config_dir: str) -> str:
    """Resolve a single path relative to config directory."""
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(config_dir, path))


def detect_config_file(config_path: Optional[Path]) -> Path:
    """Detect which config file to use."""
    if config_path and config_path.exists():
        return config_path

    # Check default location
    default_config = Path("mlserver.yaml")
    if default_config.exists():
        return default_config

    # Check if specified path exists
    if config_path:
        raise typer.BadParameter(f"Config file not found: {config_path}")

    raise typer.BadParameter("No config file found. Please specify with --config or create mlserver.yaml")


@app.command()
def serve(
    config: Optional[Path] = typer.Argument(
        None,
        help="Path to config file (defaults to mlserver.yaml)",
        exists=False,  # We'll check existence ourselves
    ),
    classifier: Optional[str] = typer.Option(
        None,
        "--classifier", "-c",
        help="Classifier to serve (for multi-classifier configs)"
    ),
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Override host address"
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port", "-p",
        help="Override port number"
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers", "-w",
        help="Number of worker processes"
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload for development"
    ),
    log_level: LogLevel = typer.Option(
        LogLevel.INFO,
        "--log-level", "-l",
        help="Set log level"
    ),
):
    """🚀 Launch ML FastAPI server from YAML config."""
    try:
        # Detect config file
        config_file = detect_config_file(config)
        console.print(f"[green]✓[/green] Using configuration: [cyan]{config_file}[/cyan]")

        # Get config directory for path resolution
        config_path = config_file.resolve()
        config_dir = config_path.parent

        # Check if multi-classifier configuration
        if detect_multi_classifier_config(str(config_file)):
            console.print("[yellow]⚡[/yellow] Detected multi-classifier configuration")

            # Load multi-classifier config
            multi_config = load_multi_classifier_config(str(config_file))

            # Determine which classifier to use
            if not classifier:
                classifier = get_default_classifier(str(config_file))
                if not classifier:
                    available = list_available_classifiers(str(config_file))
                    console.print("[red]✗[/red] No classifier specified and no default configured", style="bold red")
                    console.print(f"Available classifiers: {', '.join(available)}")
                    console.print("Use [cyan]--classifier <name>[/cyan] to select one")
                    raise typer.Exit(1)
                console.print(f"[yellow]→[/yellow] Using default classifier: [cyan]{classifier}[/cyan]")
            else:
                console.print(f"[green]→[/green] Using classifier: [cyan]{classifier}[/cyan]")

            # Extract single classifier config
            try:
                cfg = extract_single_classifier_config(multi_config, classifier)
            except (ValueError, KeyError) as e:
                console.print(f"[red]✗[/red] Error: {e}", style="bold red")
                if log_level == LogLevel.DEBUG:
                    import traceback
                    console.print("[yellow]Full traceback:[/yellow]")
                    console.print(traceback.format_exc())
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]✗[/red] Unexpected error: {e}", style="bold red")
                if log_level == LogLevel.DEBUG:
                    import traceback
                    console.print("[yellow]Full traceback:[/yellow]")
                    console.print(traceback.format_exc())
                raise typer.Exit(1)

            # Resolve paths
            if cfg.predictor.init_kwargs:
                cfg.predictor.init_kwargs = resolve_relative_paths(
                    cfg.predictor.init_kwargs, str(config_dir)
                )
        else:
            # Single classifier configuration
            with open(config_file, "r") as f:
                raw = yaml.safe_load(f)

            # Resolve relative paths
            if "predictor" in raw and "init_kwargs" in raw["predictor"]:
                raw["predictor"]["init_kwargs"] = resolve_relative_paths(
                    raw["predictor"]["init_kwargs"], str(config_dir)
                )

            cfg = AppConfig.model_validate(raw)

        # Set project path
        cfg.set_project_path(str(config_dir))

        # Apply CLI overrides
        if host:
            cfg.server.host = host
        if port:
            cfg.server.port = port
        if workers:
            cfg.server.workers = workers

        # Override log level if specified
        cfg.server.log_level = log_level.value

        # Configure logging with the new logger settings
        logger_config = cfg.server.logger if cfg.server.logger else None
        if logger_config:
            configure_logging(
                level=cfg.server.log_level,
                structured=logger_config.structured,
                include_timestamp=logger_config.timestamp,
                show_tasks=logger_config.show_tasks,
                custom_format=logger_config.format
            )
        else:
            # Fallback to default behavior
            configure_logging(cfg.server.log_level, cfg.observability.structured_logging)

        # Create the app with config file name
        config_file_name = config_file.name
        fastapi_app = create_app(cfg, config_file_name=config_file_name)

        # Show startup info
        console.print(Panel.fit(
            f"[bold cyan]ML Server Starting[/bold cyan]\n\n"
            f"[yellow]→[/yellow] Host: [cyan]{cfg.server.host}:{cfg.server.port}[/cyan]\n"
            f"[yellow]→[/yellow] Workers: [cyan]{cfg.server.workers}[/cyan]\n"
            f"[yellow]→[/yellow] Model: [cyan]{cfg.predictor.class_name}[/cyan]\n"
            f"[yellow]→[/yellow] API: [cyan]http://{cfg.server.host}:{cfg.server.port}[/cyan]\n"
            f"[yellow]→[/yellow] Docs: [cyan]http://{cfg.server.host}:{cfg.server.port}/docs[/cyan]",
            title="🚀 Server Info",
            border_style="cyan"
        ))

        # Run the server
        # For multi-worker support, we need to use the factory function
        if cfg.server.workers > 1 and not reload:
            # Set environment variables for the factory function
            import os
            os.environ['MLSERVER_CONFIG_PATH'] = str(config_file)
            if classifier:
                os.environ['MLSERVER_CLASSIFIER'] = classifier

            uvicorn.run(
                "mlserver.server:app",  # Now we can use the factory function
                host=cfg.server.host,
                port=cfg.server.port,
                log_level=cfg.server.log_level.lower(),
                workers=cfg.server.workers,
                factory=True,  # Tell uvicorn this is a factory function
            )
        else:
            # Single worker or reload mode - use the app instance directly
            uvicorn.run(
                fastapi_app,
                host=cfg.server.host,
                port=cfg.server.port,
                log_level=cfg.server.log_level.lower(),
                workers=1,
                reload=reload,
                app_dir=str(config_dir) if reload else None,
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠[/yellow] Server stopped by user")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command()
def version(
    path: str = typer.Option(".", "--path", "-p", help="Path to classifier project"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    detailed: bool = typer.Option(False, "--detailed", help="Show detailed MLServer tool information"),
):
    """📦 Display version information for the classifier project.

    Use --detailed to show MLServer tool version, commit, and installation source.
    """
    version_info = get_version_info(path)

    if "error" in version_info:
        console.print(f"[red]✗[/red] Error: {version_info['error']}", style="bold red")
        raise typer.Exit(1)

    if json_output:
        # Add mlserver tool info to JSON output if detailed
        if detailed:
            from .version_control import get_mlserver_commit_hash
            import mlserver as mlserver_module
            mlserver_commit = get_mlserver_commit_hash()
            version_info["mlserver_tool"] = {
                "version": mlserver_module.__version__ if hasattr(mlserver_module, '__version__') else "unknown",
                "commit": mlserver_commit,
                "install_location": str(Path(mlserver_module.__file__).parent)
            }
        rprint(json.dumps(version_info, indent=2))
    else:
        # Create a nice table for version info
        table = Table(title="📦 Version Information", show_header=False, title_style="bold cyan")
        table.add_column("Property", style="yellow")
        table.add_column("Value", style="cyan")

        classifier = version_info["classifier"]
        model = version_info["model"]
        api = version_info["api"]
        git = version_info.get("git")
        issues = version_info.get("validation_issues", {})

        table.add_row("Classifier", f"{classifier['name']} v{classifier['version']}")
        table.add_row("Description", classifier['description'])
        table.add_row("Model Version", model['version'])
        table.add_row("API Version", api['version'])

        if git:
            table.add_row("Git Commit", f"{git['commit']} ({git['branch']})")
            if git['tag']:
                table.add_row("Git Tag", git['tag'])
            if git['is_dirty']:
                table.add_row("Status", "⚠️  Uncommitted changes")

        # Add MLServer tool information if --detailed
        if detailed:
            from .version_control import get_mlserver_commit_hash
            import mlserver as mlserver_module

            mlserver_commit = get_mlserver_commit_hash()
            mlserver_version = mlserver_module.__version__ if hasattr(mlserver_module, '__version__') else "unknown"
            mlserver_location = Path(mlserver_module.__file__).parent

            # Determine installation type
            install_type = "unknown"
            if (mlserver_location.parent / '.git').exists():
                install_type = "git (editable)"
            elif mlserver_location.parent.name.endswith('.egg-info') or mlserver_location.parent.name.endswith('.dist-info'):
                install_type = "package"
            elif 'site-packages' in str(mlserver_location):
                install_type = "pip"

            table.add_section()
            table.add_row("[bold]MLServer Tool[/bold]", "")
            table.add_row("  Version", mlserver_version)
            table.add_row("  Commit", mlserver_commit or "n/a")
            table.add_row("  Install Type", install_type)
            table.add_row("  Location", str(mlserver_location))

        console.print(table)

        # Container tags
        if version_info["container_tags"]:
            console.print("\n[bold cyan]Container Tags:[/bold cyan]")
            for tag in version_info["container_tags"]:
                console.print(f"  [yellow]→[/yellow] {tag}")

        # Validation issues
        if issues:
            console.print("\n[bold yellow]⚠️  Validation Issues:[/bold yellow]")
            for key, issue in issues.items():
                console.print(f"  [red]✗[/red] {issue}")


@app.command()
def build(
    classifier: Optional[str] = typer.Option(
        None,
        "--classifier", "-c",
        help="Classifier to build (can be simple name or full tag: name-vX.Y.Z-mlserver-hash)"
    ),
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Config file to use (auto-detected if not specified)"
    ),
    registry: Optional[str] = typer.Option(
        None,
        "--registry",
        help="Container registry URL"
    ),
    tag_prefix: Optional[str] = typer.Option(
        None,
        "--tag-prefix",
        help="Tag prefix for container names"
    ),
    build_arg: Optional[List[str]] = typer.Option(
        None,
        "--build-arg",
        help="Build arguments (key=value)"
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Do not use cache when building"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Verbose output"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip validation prompts and continue with build"
    ),
):
    """🏗️  Build Docker container for the classifier project.

    The --classifier parameter accepts both simple names and full hierarchical tags:
    - Simple: --classifier sentiment
    - Full tag: --classifier sentiment-v1.0.0-mlserver-b5dff2a

    When using a full tag, the build will validate that your current code matches
    the tag's expected commits and warn if there are mismatches.
    """
    if not check_docker_availability():
        console.print("[red]✗[/red] Docker is not available or not running", style="bold red")
        raise typer.Exit(1)

    console.print("[cyan]🏗️  Building container...[/cyan]")

    # Parse classifier name (handles both simple names and full tags)
    original_input = classifier
    if classifier:
        from .version_control import extract_classifier_name, parse_hierarchical_tag, get_tag_commits, get_mlserver_commit_hash
        from .version import get_git_info

        # Extract classifier name from full tag if provided
        classifier_name = extract_classifier_name(classifier)
        if not classifier_name:
            console.print(f"[red]✗[/red] Invalid classifier name format: {classifier}", style="bold red")
            raise typer.Exit(1)

        # If full tag was provided, validate commits
        parsed = parse_hierarchical_tag(original_input)
        if parsed['format'] == 'valid':
            console.print(f"[yellow]→[/yellow] Full tag provided: [cyan]{original_input}[/cyan]")
            console.print()

            # Get expected commits from tag
            tag_commits = get_tag_commits(original_input, path)
            expected_classifier_commit = tag_commits['classifier_commit']
            expected_mlserver_commit = parsed['mlserver_commit']

            # Get current commits
            git_info = get_git_info(path)
            current_classifier_commit = git_info.commit if git_info else None
            current_mlserver_commit = get_mlserver_commit_hash()

            # Normalize commit hashes to 7 characters for comparison
            def normalize_commit(commit):
                return commit[:7] if commit else None

            expected_classifier_commit_short = normalize_commit(expected_classifier_commit)
            current_classifier_commit_short = normalize_commit(current_classifier_commit)
            expected_mlserver_commit_short = normalize_commit(expected_mlserver_commit)
            current_mlserver_commit_short = normalize_commit(current_mlserver_commit)

            # Check for mismatches
            classifier_mismatch = (expected_classifier_commit_short and current_classifier_commit_short and
                                 expected_classifier_commit_short != current_classifier_commit_short)
            mlserver_mismatch = (expected_mlserver_commit_short and current_mlserver_commit_short and
                               expected_mlserver_commit_short != current_mlserver_commit_short)

            if classifier_mismatch or mlserver_mismatch:
                console.print("[yellow]⚠️  Warning: Current code doesn't match tag specifications[/yellow]")
                console.print()
                console.print("[dim]Tag specifies:[/dim]")
                console.print(f"  Classifier commit: {expected_classifier_commit_short or 'unknown'}")
                console.print(f"  MLServer commit:   {expected_mlserver_commit_short}")
                console.print()
                console.print("[dim]Current working directory:[/dim]")
                console.print(f"  Classifier commit: {current_classifier_commit_short or 'unknown'} {'[red]⚠️  MISMATCH[/red]' if classifier_mismatch else '[green]✓[/green]'}")
                console.print(f"  MLServer commit:   {current_mlserver_commit_short or 'unknown'} {'[red]⚠️  MISMATCH[/red]' if mlserver_mismatch else '[green]✓[/green]'}")
                console.print()
                console.print("[yellow]Building with CURRENT code.[/yellow] To build exact tagged version:")
                console.print(f"  [cyan]git checkout {original_input}[/cyan]")
                console.print()

                if not force:
                    if not typer.confirm("Continue with build?"):
                        console.print("[yellow]Build cancelled[/yellow]")
                        raise typer.Exit(0)
            else:
                console.print("[green]✓[/green] Current code matches tag specification")
                console.print()

        # Use extracted classifier name for the rest of the build
        classifier = classifier_name

    # Detect config file
    config_file = detect_config_file(config)

    # Check if multi-classifier config
    from .multi_classifier import detect_multi_classifier_config, list_available_classifiers

    if detect_multi_classifier_config(str(config_file)):
        # Multi-classifier config
        available = list_available_classifiers(str(config_file))

        if not classifier:
            console.print(f"[red]✗[/red] Multi-classifier config detected. Please specify which classifier to build:", style="bold red")
            console.print(f"Available classifiers: {', '.join(available)}")
            console.print(f"Usage: mlserver build --classifier <name>")
            raise typer.Exit(1)

        if classifier not in available:
            console.print(f"[red]✗[/red] Classifier '{classifier}' not found.", style="bold red")
            console.print(f"Available classifiers: {', '.join(available)}")
            raise typer.Exit(1)

        # For multi-classifier, we need to pass the specific classifier config
        # This is handled by build_container internally
        console.print(f"[yellow]→[/yellow] Building for classifier: {classifier}")

    result = build_container(
        project_path=str(path),
        config_file=str(config_file),
        classifier_name=classifier,
        tag_prefix=tag_prefix,
        registry=registry,
        build_args=dict(arg.split('=', 1) for arg in build_arg) if build_arg else None,
        no_cache=no_cache,
        mlserver_source_path=None  # Auto-detect
    )

    if result["success"]:
        console.print("[green]✓[/green] Successfully built container")
        console.print(f"[yellow]Tags:[/yellow] {', '.join(result['tags'])}")
        if verbose and result.get("build_output"):
            console.print("\n[dim]Build output:[/dim]")
            console.print(result["build_output"])
    else:
        console.print(f"[red]✗[/red] Build failed: {result['error']}", style="bold red")
        raise typer.Exit(1)


@app.command()
def push(
    registry: str = typer.Option(
        ...,
        "--registry", "-r",
        help="Container registry URL"
    ),
    classifier: Optional[str] = typer.Option(
        None,
        "--classifier", "-c",
        help="Classifier to push (required for multi-classifier configs)"
    ),
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
    tag_prefix: Optional[str] = typer.Option(
        None,
        "--tag-prefix",
        help="Tag prefix for container names"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force push even if not on tagged commit or tag exists"
    ),
    version_source: str = typer.Option(
        "auto",
        "--version-source",
        help="Version source: 'git-tag', 'config', or 'auto'"
    ),
):
    """📤 Push container to registry (requires tagged commit for specific classifier)."""
    if not check_docker_availability():
        console.print("[red]✗[/red] Docker is not available or not running", style="bold red")
        raise typer.Exit(1)

    console.print(f"[cyan]📤 Validating and pushing to {registry}...[/cyan]")
    if classifier:
        console.print(f"[yellow]→[/yellow] Classifier: {classifier}")

    # Use safe push with version control
    result = safe_push_container(
        project_path=str(path),
        registry=registry,
        classifier_name=classifier,
        tag_prefix=tag_prefix,
        force=force,
        version_source=version_source
    )

    if result["success"]:
        console.print(f"[green]✓[/green] Successfully pushed images")
        console.print(f"  [yellow]→[/yellow] Version: {result['version_used']} (from {result['version_source']})")
        if result.get("pushed_tags"):
            for tag in result["pushed_tags"]:
                console.print(f"  [yellow]→[/yellow] {tag}")
    else:
        console.print(f"[red]✗[/red] Push failed: {result['error']}", style="bold red")
        if result.get("validation_errors"):
            for error in result["validation_errors"]:
                console.print(f"  [red]→[/red] {error}")
        raise typer.Exit(1)

    if result.get("validation_warnings"):
        console.print(f"\n[yellow]⚠️  Warnings:[/yellow]")
        for warning in result["validation_warnings"]:
            console.print(f"  [yellow]→[/yellow] {warning}")

    if result.get("failed_tags"):
        console.print(f"\n[yellow]⚠️  Failed to push {len(result['failed_tags'])} images:[/yellow]")
        for error in result["failed_tags"]:
            console.print(f"  [red]✗[/red] {error}")


@app.command()
def images(
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
):
    """📋 List Docker images for the classifier project."""
    image_list = list_images(str(path))

    if not image_list:
        console.print("[yellow]No images found for this classifier project[/yellow]")
        return

    table = Table(title="🐳 Docker Images", title_style="bold cyan")
    table.add_column("Tag", style="cyan")
    table.add_column("Image ID", style="yellow")
    table.add_column("Created", style="green")
    table.add_column("Size", style="magenta")

    for image in image_list:
        table.add_row(
            image['tag'],
            image['image_id'],
            image['created'],
            image['size']
        )

    console.print(table)


@app.command()
def tag(
    bump_type: Optional[BumpType] = typer.Argument(
        None,
        help="Version bump type: major, minor, or patch"
    ),
    classifier: Optional[str] = typer.Option(
        None,
        "--classifier", "-c",
        help="Classifier name to tag (required for tagging)"
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Config file path (defaults to mlserver.yaml)"
    ),
    message: Optional[str] = typer.Option(
        None,
        "--message", "-m",
        help="Tag message (defaults to 'Release <classifier> vX.Y.Z')"
    ),
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
    allow_missing_mlserver: bool = typer.Option(
        False,
        "--allow-missing-mlserver",
        help="Allow tagging even if mlserver commit cannot be determined (dev/testing only)"
    ),
):
    """🏷️  Manage version tags for classifiers.

    Without arguments: Show tag status for all classifiers.
    With arguments: Create a version tag for a specific classifier.
    """
    try:
        git_mgr = GitVersionManager(str(path))

        # If no bump_type, show status table
        if not bump_type:
            # Detect config file
            config_file = detect_config_file(config)

            # Get status for all classifiers
            classifiers_status = git_mgr.get_all_classifiers_tag_status(str(config_file))

            # Get current mlserver commit for comparison
            from .version_control import get_mlserver_commit_hash, parse_hierarchical_tag
            current_mlserver_commit = get_mlserver_commit_hash() or "unknown"

            # Create table with MLServer commit column
            table = Table(title="🏷️  Classifier Version Status", title_style="bold cyan")
            table.add_column("Classifier", style="cyan")
            table.add_column("Version", style="yellow")
            table.add_column("MLServer", style="blue")
            table.add_column("Status", style="green")
            table.add_column("Action Required", style="magenta")

            for clf_name, status in classifiers_status.items():
                version = status['current_version'] or "No tags"
                status_text = status['status']
                recommendation = status['recommendation'] or "-"

                # Extract mlserver commit from the latest tag
                mlserver_commit = "-"
                if status.get('latest_tag'):
                    parsed = parse_hierarchical_tag(status['latest_tag'])
                    if parsed['format'] == 'valid':
                        tag_mlserver = parsed['mlserver_commit'][:7]
                        current_mlserver_short = current_mlserver_commit[:7]
                        if tag_mlserver == current_mlserver_short:
                            mlserver_commit = f"{tag_mlserver} [green]✓[/green]"
                        else:
                            mlserver_commit = f"{tag_mlserver} [yellow]⚠️[/yellow]"
                    else:
                        mlserver_commit = "[dim]n/a[/dim]"

                # Color coding for status
                if status['on_tagged_commit']:
                    status_style = "green"
                elif status['commits_since_tag'] and status['commits_since_tag'] > 0:
                    status_style = "yellow"
                else:
                    status_style = "red"

                table.add_row(
                    clf_name,
                    version,
                    mlserver_commit,
                    f"[{status_style}]{status_text}[/{status_style}]",
                    recommendation
                )

            console.print(table)
            console.print(f"\n[dim]Current MLServer commit: {current_mlserver_commit[:7]}[/dim]")
            return

        # Tagging mode - classifier is required
        if not classifier:
            console.print("[red]✗[/red] Classifier name is required for tagging", style="bold red")
            console.print("Use [cyan]--classifier <name>[/cyan] to specify the classifier")
            raise typer.Exit(1)

        # Check working directory status
        is_clean, error_msg = git_mgr.check_working_directory_clean()
        if not is_clean:
            console.print(f"[red]✗[/red] Cannot tag version: {error_msg}", style="bold red")
            console.print("[yellow]→[/yellow] Commit your changes first with: [cyan]git add . && git commit -m 'message'[/cyan]")
            raise typer.Exit(1)

        # Create the tag
        tag_info = git_mgr.tag_version(bump_type.value, classifier, message, allow_missing_mlserver)

        # Display success message with all details
        console.print(f"[green]✓[/green] Created tag: [cyan]{tag_info['tag_name']}[/cyan]")
        console.print()

        # Version info
        if tag_info['previous_version']:
            console.print(f"  [yellow]📝 Version:[/yellow] {tag_info['previous_version']} → {tag_info['version']} ({bump_type.value} bump)")
        else:
            console.print(f"  [yellow]📝 Version:[/yellow] {tag_info['version']} (initial release)")

        # MLServer info
        console.print(f"  [yellow]🔧 MLServer commit:[/yellow] {tag_info['mlserver_commit']}")

        # Get classifier commit for reference
        from .version import get_git_info
        git_info = get_git_info(path)
        if git_info:
            console.print(f"  [yellow]📦 Classifier commit:[/yellow] {git_info.commit}")

        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Push tags to remote: [cyan]git push --tags[/cyan]")
        console.print(f"  2. Build container: [cyan]mlserver build --classifier {classifier}[/cyan]")
        console.print(f"  3. Push to registry: [cyan]mlserver push --classifier {classifier} --registry <url>[/cyan]")

    except VersionControlError as e:
        console.print(f"[red]✗[/red] {e}", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command()
def clean(
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force removal without confirmation"
    ),
):
    """🧹 Remove Docker images for the classifier project."""
    if not check_docker_availability():
        console.print("[red]✗[/red] Docker is not available or not running", style="bold red")
        raise typer.Exit(1)

    # Get images to be removed
    image_list = list_images(str(path))
    if not image_list:
        console.print("[yellow]No images to remove[/yellow]")
        return

    # Confirm if not forced
    if not force:
        console.print(f"[yellow]⚠️  This will remove {len(image_list)} images[/yellow]")
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    console.print("[cyan]🧹 Cleaning images...[/cyan]")

    result = remove_images(str(path), force=True)

    if result["success"]:
        if result.get("removed_images"):
            console.print(f"[green]✓[/green] Removed {len(result['removed_images'])} images:")
            for image in result["removed_images"]:
                console.print(f"  [yellow]→[/yellow] {image}")
        else:
            console.print(result.get("message", "No images removed"))
    else:
        console.print(f"[red]✗[/red] Clean failed: {result['error']}", style="bold red")
        raise typer.Exit(1)

    if result.get("errors"):
        console.print(f"\n[yellow]⚠️  Removal errors:[/yellow]")
        for error in result["errors"]:
            console.print(f"  [red]✗[/red] {error}")


@app.command()
def run(
    classifier: Optional[str] = typer.Option(
        None,
        "--classifier", "-c",
        help="Classifier to run (required for multi-classifier configs)"
    ),
    path: str = typer.Option(
        ".",
        "--path",
        help="Path to classifier project"
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port to expose the container on"
    ),
    version: Optional[str] = typer.Option(
        None,
        "--version",
        help="Specific version to run (default: latest)"
    ),
    detach: bool = typer.Option(
        False,
        "--detach", "-d",
        help="Run container in background"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Container name"
    ),
    env: Optional[List[str]] = typer.Option(
        None,
        "--env", "-e",
        help="Environment variables (KEY=value)"
    ),
    volume: Optional[List[str]] = typer.Option(
        None,
        "--volume", "-v",
        help="Volume mounts (host:container)"
    ),
):
    """🚀 Run Docker container for the classifier."""
    if not check_docker_availability():
        console.print("[red]✗[/red] Docker is not available or not running", style="bold red")
        raise typer.Exit(1)

    # Detect config file
    config_file = detect_config_file(None)

    # Check if multi-classifier config
    from .multi_classifier import detect_multi_classifier_config, list_available_classifiers

    if detect_multi_classifier_config(str(config_file)):
        # Multi-classifier config
        available = list_available_classifiers(str(config_file))

        if not classifier:
            console.print(f"[red]✗[/red] Multi-classifier config detected. Please specify which classifier to run:", style="bold red")
            console.print(f"Available classifiers: {', '.join(available)}")
            console.print(f"Usage: mlserver run --classifier <name>")
            raise typer.Exit(1)

        if classifier not in available:
            console.print(f"[red]✗[/red] Classifier '{classifier}' not found.", style="bold red")
            console.print(f"Available classifiers: {', '.join(available)}")
            raise typer.Exit(1)

    # Get repository name
    from .version import get_repository_name
    repository = get_repository_name(path)

    # Construct image name
    if classifier:
        image_name = f"{repository}/{classifier}"
    else:
        image_name = repository

    # Add version tag
    if version:
        full_image = f"{image_name}:{version}"
    else:
        full_image = f"{image_name}:latest"

    console.print(f"[cyan]🚀 Running container {full_image}...[/cyan]")

    # Build docker run command
    docker_cmd = ["docker", "run"]

    if detach:
        docker_cmd.append("-d")
    else:
        docker_cmd.append("-it")

    # Add port mapping
    docker_cmd.extend(["-p", f"{port}:8000"])

    # Add container name if specified
    if name:
        docker_cmd.extend(["--name", name])
    else:
        # Auto-generate name if running specific classifier
        if classifier:
            import time
            timestamp = int(time.time())
            docker_cmd.extend(["--name", f"{classifier}-{timestamp}"])

    # Add environment variables
    if env:
        for env_var in env:
            docker_cmd.extend(["-e", env_var])

    # Add volume mounts
    if volume:
        for vol in volume:
            docker_cmd.extend(["-v", vol])

    # Add image name
    docker_cmd.append(full_image)

    # Execute docker run
    import subprocess

    if detach:
        # Run detached with output capture
        result = subprocess.run(docker_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            container_id = result.stdout.strip()
            console.print(f"[green]✓[/green] Container started in background")
            console.print(f"[yellow]→[/yellow] Container ID: {container_id[:12]}")
            console.print(f"[yellow]→[/yellow] Access at: http://localhost:{port}")
            console.print(f"[yellow]→[/yellow] Stop with: docker stop {container_id[:12]}")
        else:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            console.print(f"[red]✗[/red] Failed to run container: {error_msg}", style="bold red")
            raise typer.Exit(1)
    else:
        # Run interactively without capture (allows TTY)
        try:
            # Check if we have a TTY available
            import sys
            if sys.stdin.isatty():
                # We have TTY, run interactively
                result = subprocess.run(docker_cmd)
            else:
                # No TTY, remove -it flag and run without TTY
                docker_cmd[docker_cmd.index("-it")] = "--rm"
                result = subprocess.run(docker_cmd)

            if result.returncode == 0:
                console.print(f"[green]✓[/green] Container stopped")
            else:
                console.print(f"[red]✗[/red] Container exited with error code: {result.returncode}", style="bold red")
                raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]→[/yellow] Container interrupted")
            raise typer.Exit(0)
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to run container: {e}", style="bold red")
            raise typer.Exit(1)



@app.command()
def list_classifiers(
    config: Optional[Path] = typer.Argument(
        None,
        help="Path to multi-classifier config file"
    ),
):
    """📋 List available classifiers in multi-classifier config."""
    try:
        config_file = detect_config_file(config)

        if not detect_multi_classifier_config(str(config_file)):
            console.print("[yellow]Not a multi-classifier configuration[/yellow]")
            return

        classifiers = list_available_classifiers(str(config_file))
        default = get_default_classifier(str(config_file))

        table = Table(title="📦 Available Classifiers", title_style="bold cyan")
        table.add_column("Classifier", style="cyan")
        table.add_column("Default", style="yellow")

        for classifier in classifiers:
            is_default = "✓" if classifier == default else ""
            table.add_row(classifier, is_default)

        console.print(table)

        if default:
            console.print(f"\n[yellow]→[/yellow] Default classifier: [cyan]{default}[/cyan]")

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}", style="bold red")
        raise typer.Exit(1)


@app.command()
def status():
    """📊 Show ML Server status and system info."""
    table = Table(title="📊 ML Server Status", title_style="bold cyan")
    table.add_column("Component", style="yellow")
    table.add_column("Status", style="cyan")

    # Check Docker
    docker_available = check_docker_availability()
    docker_status = "[green]✓ Available[/green]" if docker_available else "[red]✗ Not available[/red]"
    table.add_row("Docker", docker_status)

    # Check for config files
    configs = []
    for config_name in ["mlserver.yaml", "config.yaml"]:
        if Path(config_name).exists():
            configs.append(config_name)

    config_status = f"[green]{', '.join(configs)}[/green]" if configs else "[yellow]No config found[/yellow]"
    table.add_row("Config Files", config_status)

    # Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    table.add_row("Python Version", python_version)

    # Check for virtual env
    venv = os.environ.get("VIRTUAL_ENV")
    venv_status = f"[green]{Path(venv).name}[/green]" if venv else "[yellow]None[/yellow]"
    table.add_row("Virtual Env", venv_status)

    console.print(table)


@app.callback()
def main_callback():
    """🚀 ML Server - Modern CLI for ML model serving."""
    pass


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()