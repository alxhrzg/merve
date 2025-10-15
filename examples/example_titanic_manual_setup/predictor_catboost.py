
"""
Example predictor implementation to demonstrate integration.
This class loads artifacts once in __init__ (kept in memory). It exposes
predict() and predict_proba(). Replace loading with your real artifacts.
"""
from __future__ import annotations
from typing import Any, List, Optional
import json
import joblib
import numpy as np
import pandas as pd


class CatBoostPredictor:
    def __init__(
        self,
        model_path: str,
        preprocessor_path: str,
        feature_order: Optional[List[str]] = None,
        feature_order_path: Optional[str] = None,
    ):
        self.model_path = model_path
        self.preprocessor_path = preprocessor_path
        # Load once — these stay resident in memory
        # Using joblib for safer deserialization
        self.model = joblib.load(model_path)
        self.preproc = joblib.load(preprocessor_path)

        if feature_order is not None:
            self.feature_order = list(feature_order)
        elif feature_order_path is not None:
            with open(feature_order_path, "r") as f:
                self.feature_order = json.load(f)
        else:
            # Strongly recommended to provide, since the preprocessor was fit on named columns
            self.feature_order = None

    def _as_dataframe(self, X: np.ndarray) -> pd.DataFrame:
        if not isinstance(X, np.ndarray):
            X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if self.feature_order is None:
            raise ValueError(
                "feature_order is required to reconstruct a DataFrame for the preprocessor. "
                "Pass it via init kwargs or feature_order_path."
            )
        return pd.DataFrame(X, columns=self.feature_order)

    def _transform(self, X: np.ndarray) -> np.ndarray:
        if self.preproc is not None:
            df = self._as_dataframe(X)
            return self.preproc.transform(df)
        return X

    def predict(self, X: np.ndarray):
        X2 = self._transform(X)
        return self.model.predict(X2)

    def predict_proba(self, X: np.ndarray):
        X2 = self._transform(X)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X2)
        raise AttributeError("Underlying model has no predict_proba")
