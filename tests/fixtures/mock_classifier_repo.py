"""Mock classifier repository fixture for testing the complete workflow."""

import os
import subprocess
import tempfile
import shutil
import yaml
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class MockClassifierRepo:
    """A mock ML classifier repository for testing."""

    def __init__(self, temp_dir: str, multi_classifier: bool = False):
        self.repo_path = Path(temp_dir)
        self.multi_classifier = multi_classifier
        self.config_path = self.repo_path / "mlserver.yaml"

        # Initialize git repo
        self._init_git()

        # Create predictor and artifacts
        self._create_predictor_files()

        # Create config
        if multi_classifier:
            self._create_multi_classifier_config()
        else:
            self._create_single_classifier_config()

        # Initial commit
        self._commit_all("Initial commit")

    def _init_git(self):
        """Initialize git repository."""
        subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True)

    def _create_predictor_files(self):
        """Create mock predictor class and model artifacts."""
        # Create predictors directory
        predictors_dir = self.repo_path / "predictors"
        predictors_dir.mkdir(exist_ok=True)

        # Create __init__.py
        (predictors_dir / "__init__.py").write_text("")

        # Create mock predictor class
        predictor_code = '''"""Mock predictor for testing."""
import numpy as np
import pickle
from pathlib import Path


class TestPredictor:
    """A simple test predictor."""

    def __init__(self, model_path: str = None, **kwargs):
        self.model_path = model_path
        # Load or create a simple model
        if model_path and Path(model_path).exists():
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
        else:
            # Create a dummy model
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(n_estimators=3, random_state=42)
            # Train on dummy data
            X_dummy = np.random.random((100, 5))
            y_dummy = np.random.randint(0, 2, 100)
            self.model.fit(X_dummy, y_dummy)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions."""
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        # Ensure 5 features
        if X.shape[1] != 5:
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get prediction probabilities."""
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        # Ensure 5 features
        if X.shape[1] != 5:
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict_proba(X)


class SentimentPredictor(TestPredictor):
    """Sentiment analysis predictor."""
    pass


class IntentPredictor(TestPredictor):
    """Intent classification predictor."""
    pass
'''
        (predictors_dir / "test_predictor.py").write_text(predictor_code)

        # Create models directory and artifacts
        models_dir = self.repo_path / "models"
        models_dir.mkdir(exist_ok=True)

        # Create a simple model artifact
        model = RandomForestClassifier(n_estimators=3, random_state=42)
        X_dummy = np.random.random((100, 5))
        y_dummy = np.random.randint(0, 2, 100)
        model.fit(X_dummy, y_dummy)

        with open(models_dir / "model.pkl", "wb") as f:
            pickle.dump(model, f)

        # Create preprocessor
        preprocessor = StandardScaler()
        preprocessor.fit(X_dummy)
        with open(models_dir / "preprocessor.pkl", "wb") as f:
            pickle.dump(preprocessor, f)

        # Create feature order file
        with open(models_dir / "feature_order.json", "w") as f:
            json.dump(["f1", "f2", "f3", "f4", "f5"], f)

    def _create_single_classifier_config(self):
        """Create single classifier configuration."""
        config = {
            "server": {
                "title": "Test ML Server",
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 1
            },
            "predictor": {
                "module": "predictors.test_predictor",
                "class_name": "TestPredictor",
                "init_kwargs": {
                    "model_path": "models/model.pkl"
                }
            },
            "classifier": {
                "name": "test-classifier",
                "version": "1.0.0",
                "description": "Test classifier for testing",
                "repository": "mlserver"
            },
            "api": {
                "version": "v1",
                "adapter": "records",
                "endpoints": {
                    "predict": True,
                    "batch_predict": True,
                    "predict_proba": True
                }
            },
            "observability": {
                "metrics": True,
                "structured_logging": False
            },
            "model": {
                "version": "1.0.0",
                "trained_at": "2024-01-01T00:00:00Z"
            }
        }

        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)

    def _create_multi_classifier_config(self):
        """Create multi-classifier configuration."""
        config = {
            "classifiers": [
                {
                    "name": "sentiment",
                    "server": {
                        "title": "Sentiment Analysis Server",
                        "host": "0.0.0.0",
                        "port": 8000
                    },
                    "predictor": {
                        "module": "predictors.test_predictor",
                        "class_name": "SentimentPredictor",
                        "init_kwargs": {
                            "model_path": "models/model.pkl"
                        }
                    },
                    "classifier": {
                        "name": "sentiment",
                        "version": "1.0.0",
                        "description": "Sentiment analysis classifier",
                        "repository": "mlserver"
                    },
                    "api": {
                        "adapter": "records",
                        "endpoints": {
                            "predict": True,
                            "batch_predict": True
                        }
                    },
                    "observability": {
                        "metrics": True
                    },
                    "model": {
                        "version": "1.0.0",
                        "trained_at": "2024-01-01T00:00:00Z"
                    }
                },
                {
                    "name": "intent",
                    "server": {
                        "title": "Intent Classification Server",
                        "host": "0.0.0.0",
                        "port": 8001
                    },
                    "predictor": {
                        "module": "predictors.test_predictor",
                        "class_name": "IntentPredictor",
                        "init_kwargs": {
                            "model_path": "models/model.pkl"
                        }
                    },
                    "classifier": {
                        "name": "intent",
                        "version": "2.0.0",
                        "description": "Intent classification",
                        "repository": "mlserver"
                    },
                    "api": {
                        "adapter": "records",
                        "endpoints": {
                            "predict": True,
                            "batch_predict": True
                        }
                    },
                    "observability": {
                        "metrics": True
                    },
                    "model": {
                        "version": "1.0.0",
                        "trained_at": "2024-01-01T00:00:00Z"
                    }
                }
            ],
            "default_classifier": "sentiment"
        }

        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)

    def _commit_all(self, message: str):
        """Add all files and commit."""
        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], cwd=self.repo_path, check=True, capture_output=True)

    def make_change(self, filename: str = "update.txt", content: str = "update"):
        """Make a change to the repository."""
        (self.repo_path / filename).write_text(content)
        self._commit_all(f"Update {filename}")

    def tag_version(self, classifier_name: str, bump_type: str) -> str:
        """Tag a version using the version control system."""
        from mlserver.version_control import GitVersionManager

        git_mgr = GitVersionManager(str(self.repo_path))
        return git_mgr.tag_version(bump_type, classifier_name)

    def get_classifier_names(self) -> List[str]:
        """Get list of classifier names."""
        if self.multi_classifier:
            from mlserver.multi_classifier import list_available_classifiers
            return list_available_classifiers(str(self.config_path))
        else:
            # Single classifier
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            return [config['classifier']['name']]

    def run_cli_command(self, *args) -> subprocess.CompletedProcess:
        """Run a CLI command in the repository context."""
        # Build full command
        cmd = ["/Users/peter/Desktop/enmacc/.venv/bin/python", "-m", "mlserver.cli"] + list(args)

        # Run command with repo as working directory
        result = subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)}
        )

        return result

    def serve_in_background(self, classifier_name: Optional[str] = None, port: int = 8000) -> subprocess.Popen:
        """Start server in background and return process."""
        args = ["serve"]

        if classifier_name and self.multi_classifier:
            args.extend(["--classifier", classifier_name])
        if port != 8000:
            args.extend(["--port", str(port)])

        cmd = ["/Users/peter/Desktop/enmacc/.venv/bin/python", "-m", "mlserver.cli"] + args

        # Start server process
        process = subprocess.Popen(
            cmd,
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)}
        )

        # Wait a bit for server to start
        import time
        time.sleep(2)

        return process

    def cleanup(self):
        """Clean up the repository."""
        # Nothing to do - temp dir will be cleaned up automatically
        pass