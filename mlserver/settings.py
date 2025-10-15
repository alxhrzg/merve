"""
Global settings singleton for mlserver-fastapi-wrapper.

This module provides centralized configuration management for all hardcoded values
in the project, allowing global settings to be configured from a single place.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
from pydantic import BaseModel, Field


class ServerSettings(BaseModel):
    """Server-related settings."""
    default_host: str = Field(default="0.0.0.0", description="Default server host")
    default_port: int = Field(default=8000, description="Default server port")
    default_log_level: str = Field(default="INFO", description="Default log level")
    default_workers: int = Field(default=1, description="Default number of worker processes")
    health_endpoint_port: int = Field(default=8000, description="Health check endpoint port")
    container_test_port: int = Field(default=8012, description="Container test port")


class MonitoringSettings(BaseModel):
    """Monitoring and observability settings."""
    prometheus_host: str = Field(default="localhost", description="Prometheus host")
    prometheus_port: int = Field(default=9090, description="Prometheus port")
    grafana_host: str = Field(default="localhost", description="Grafana host")
    grafana_port: int = Field(default=3000, description="Grafana port")
    grafana_credentials: str = Field(default="admin/admin123", description="Grafana default credentials")
    metrics_endpoint: str = Field(default="/metrics", description="Metrics endpoint path")


class ContainerSettings(BaseModel):
    """Container and Docker-related settings."""
    default_base_image: str = Field(default="python:3.11-slim", description="Default Docker base image")
    python_version_threshold: str = Field(default="3.11", description="Python version threshold for tomli usage")
    temp_dir: str = Field(default="/tmp", description="Temporary directory for container operations")
    excluded_patterns: List[str] = Field(
        default_factory=lambda: [
            ".vscode", ".idea", "*.log", "*.tmp", "catboost_info", "*.swp",
            ".git", ".gitignore", "__pycache__", "*.pyc", ".pytest_cache",
            ".coverage", "htmlcov", ".DS_Store", "node_modules", ".env",
            "venv", ".venv"
        ],
        description="File patterns to exclude from container builds"
    )


class FilesSettings(BaseModel):
    """File system and path settings."""
    server_log_file: str = Field(default="server.log", description="Server log file name")
    server_pid_file: str = Field(default="server.pid", description="Server PID file name")
    global_config_file: str = Field(default="global_config.yaml", description="Global configuration file name")
    venv_path: str = Field(default=".venv", description="Python virtual environment path")
    ml_server_path: str = Field(default="mlserver", description="Full path to mlserver executable")


class DevelopmentSettings(BaseModel):
    """Development and testing settings."""
    test_base_url: str = Field(default="http://localhost:8000", description="Base URL for testing")
    load_test_users: int = Field(default=5, description="Default number of users for load testing")
    load_test_spawn_rate: int = Field(default=1, description="Default spawn rate for load testing")
    load_test_duration: int = Field(default=60, description="Default load test duration in seconds")


class LoadTestingSettings(BaseModel):
    """Load testing specific settings."""
    stress_test_users: int = Field(default=50, description="Users for stress testing")
    stress_test_spawn_rate: int = Field(default=10, description="Spawn rate for stress testing")
    stress_test_duration: int = Field(default=300, description="Stress test duration in seconds")
    endurance_test_users: int = Field(default=10, description="Users for endurance testing")
    endurance_test_spawn_rate: int = Field(default=2, description="Spawn rate for endurance testing")
    endurance_test_duration: int = Field(default=1800, description="Endurance test duration in seconds")


class GlobalSettings(BaseModel):
    """Global settings container."""
    server: ServerSettings = Field(default_factory=ServerSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    container: ContainerSettings = Field(default_factory=ContainerSettings)
    files: FilesSettings = Field(default_factory=FilesSettings)
    development: DevelopmentSettings = Field(default_factory=DevelopmentSettings)
    load_testing: LoadTestingSettings = Field(default_factory=LoadTestingSettings)

    @classmethod
    def from_yaml(cls, config_path: str) -> 'GlobalSettings':
        """Load settings from YAML configuration file."""
        config_file = Path(config_path)
        if not config_file.exists():
            return cls()  # Return default settings if file doesn't exist

        with open(config_file, 'r') as f:
            data = yaml.safe_load(f) or {}

        # Apply environment variable overrides
        data = cls._apply_env_overrides(data)
        return cls.model_validate(data)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """Apply environment variable overrides to config data."""
        # Override file settings from environment
        if 'files' not in data:
            data['files'] = {}

        env_mappings = {
            'MLSERVER_LOG_FILE': ('files', 'server_log_file'),
            'MLSERVER_PID_FILE': ('files', 'server_pid_file'),
            'MLSERVER_GLOBAL_CONFIG': ('files', 'global_config_file'),
            'MLSERVER_VENV_PATH': ('files', 'venv_path'),
            'MLSERVER_EXEC_PATH': ('files', 'ml_server_path'),
            'MLSERVER_DEFAULT_HOST': ('server', 'default_host'),
            'MLSERVER_DEFAULT_PORT': ('server', 'default_port'),
            'MLSERVER_LOG_LEVEL': ('server', 'default_log_level'),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                if section not in data:
                    data[section] = {}
                # Convert port to int if needed
                if 'port' in key.lower():
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                data[section][key] = value

        return data

    def to_yaml(self, config_path: str) -> None:
        """Save current settings to YAML configuration file."""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)

    def get_prometheus_url(self) -> str:
        """Get full Prometheus URL."""
        return f"http://{self.monitoring.prometheus_host}:{self.monitoring.prometheus_port}"

    def get_grafana_url(self) -> str:
        """Get full Grafana URL."""
        return f"http://{self.monitoring.grafana_host}:{self.monitoring.grafana_port}"

    def get_server_url(self) -> str:
        """Get full server URL."""
        return f"http://{self.server.default_host}:{self.server.default_port}"

    def get_health_url(self) -> str:
        """Get full health check URL."""
        return f"http://localhost:{self.server.health_endpoint_port}/healthz"

    def get_metrics_url(self) -> str:
        """Get full metrics URL."""
        return f"http://localhost:{self.server.health_endpoint_port}{self.monitoring.metrics_endpoint}"


class SettingsSingleton:
    """Singleton class to manage global settings."""
    _instance: Optional['SettingsSingleton'] = None
    _settings: Optional[GlobalSettings] = None

    def __new__(cls) -> 'SettingsSingleton':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._settings is None:
            self._load_settings()

    def _load_settings(self) -> None:
        """Load settings from global configuration file with hierarchical override support."""
        # Priority order (later overrides earlier):
        # 1. Built-in defaults
        # 2. Global config (global_config.yaml at project root)
        # 3. Environment variables

        # Look for global_config.yaml in multiple locations
        config_search_paths = [
            Path.cwd() / "global_config.yaml",
            Path(__file__).parent.parent / "global_config.yaml",
            Path.home() / ".mlserver" / "global_config.yaml",
        ]

        # Also check environment variable for config path
        env_config_path = os.getenv('MLSERVER_GLOBAL_CONFIG_PATH')
        if env_config_path:
            config_search_paths.insert(0, Path(env_config_path))

        config_path = None
        for path in config_search_paths:
            if path.exists():
                config_path = str(path)
                break

        if config_path:
            self._settings = GlobalSettings.from_yaml(config_path)
        else:
            self._settings = GlobalSettings()

    @property
    def settings(self) -> GlobalSettings:
        """Get the global settings instance."""
        if self._settings is None:
            self._load_settings()
        return self._settings

    def reload_settings(self, config_path: Optional[str] = None) -> None:
        """Reload settings from configuration file."""
        if config_path:
            self._settings = GlobalSettings.from_yaml(config_path)
        else:
            self._load_settings()

    def save_settings(self, config_path: Optional[str] = None) -> None:
        """Save current settings to configuration file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "global_config.yaml"

        if self._settings:
            self._settings.to_yaml(str(config_path))


# Global settings instance
_settings_singleton = SettingsSingleton()
settings = _settings_singleton.settings


def get_settings() -> GlobalSettings:
    """Get the global settings instance."""
    return settings


def reload_settings(config_path: Optional[str] = None) -> None:
    """Reload global settings from configuration file."""
    _settings_singleton.reload_settings(config_path)


def save_settings(config_path: Optional[str] = None) -> None:
    """Save current global settings to configuration file."""
    _settings_singleton.save_settings(config_path)