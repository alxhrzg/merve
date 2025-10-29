"""Mock predictor classes for testing."""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import List


class MockPredictor:
    """Simple mock predictor for testing."""

    def __init__(self, model_path: str = None, **kwargs):
        self.model_path = model_path
        # Create a simple mock model
        self.model = RandomForestClassifier(n_estimators=3, random_state=42)
        # Train on dummy data
        X_dummy = np.random.random((100, 5))
        y_dummy = np.random.randint(0, 2, 100)
        self.model.fit(X_dummy, y_dummy)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        if X.shape[1] != 5:
            # Pad or truncate to 5 features for consistency
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        if X.shape[1] != 5:
            # Pad or truncate to 5 features for consistency
            if X.shape[1] < 5:
                padding = np.zeros((X.shape[0], 5 - X.shape[1]))
                X = np.hstack([X, padding])
            else:
                X = X[:, :5]
        return self.model.predict_proba(X)


class MockPredictorWithPreprocessing:
    """Mock predictor with preprocessing for testing."""

    def __init__(self, model_path: str = None, preprocessor_path: str = None,
                 feature_order: List[str] = None, **kwargs):
        self.model_path = model_path
        self.preprocessor_path = preprocessor_path
        self.feature_order = feature_order or ["f1", "f2", "f3", "f4", "f5"]

        # Mock model and preprocessor
        self.model = RandomForestClassifier(n_estimators=3, random_state=42)
        self.preprocessor = StandardScaler()

        # Train on dummy data
        X_dummy = np.random.random((100, 5))
        y_dummy = np.random.randint(0, 2, 100)
        self.preprocessor.fit(X_dummy)
        self.model.fit(self.preprocessor.transform(X_dummy), y_dummy)

    def _as_dataframe(self, X: np.ndarray) -> pd.DataFrame:
        if not isinstance(X, np.ndarray):
            X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return pd.DataFrame(X, columns=self.feature_order[:X.shape[1]])

    def predict(self, X: np.ndarray) -> np.ndarray:
        df = self._as_dataframe(X)
        # Ensure we have the right number of columns
        for col in self.feature_order:
            if col not in df.columns:
                df[col] = 0
        df = df[self.feature_order]
        X_processed = self.preprocessor.transform(df)
        return self.model.predict(X_processed)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        df = self._as_dataframe(X)
        # Ensure we have the right number of columns
        for col in self.feature_order:
            if col not in df.columns:
                df[col] = 0
        df = df[self.feature_order]
        X_processed = self.preprocessor.transform(df)
        return self.model.predict_proba(X_processed)
