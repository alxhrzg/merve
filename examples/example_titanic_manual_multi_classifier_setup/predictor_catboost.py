"""
CatBoost Predictor for Titanic survival prediction.
This version works with the multi-classifier setup.
"""

import pickle
import json
import numpy as np
import pandas as pd
from typing import List, Any, Optional
from pathlib import Path


class CatBoostSurvivalPredictor:
    """CatBoost-based Titanic survival predictor."""

    def __init__(self,
                 model_path: str = "./artifacts/catboost-survival/model.pkl",
                 features_path: str = "./artifacts/catboost-survival/features.json",
                 categorical_indices_path: str = "./artifacts/catboost-survival/categorical_indices.json"):
        """Initialize the CatBoost predictor.

        Args:
            model_path: Path to the trained CatBoost model
            features_path: Path to the feature list
            categorical_indices_path: Path to categorical feature indices
        """
        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load feature order
        with open(features_path, 'r') as f:
            self.feature_order = json.load(f)

        # Load categorical indices
        with open(categorical_indices_path, 'r') as f:
            self.categorical_indices = json.load(f)

        print(f"Loaded CatBoost model with features: {self.feature_order}")

    def predict(self, X: np.ndarray) -> List[int]:
        """Make predictions.

        Args:
            X: Input features as numpy array

        Returns:
            List of predictions (0 or 1 for survival)
        """
        # Ensure X is 2D
        if X.ndim == 1:
            X = X.reshape(1, -1)

        # Create DataFrame with proper feature names for better handling
        df = pd.DataFrame(X, columns=self.feature_order)

        # Make predictions
        predictions = self.model.predict(df)

        # Convert to list of integers
        return [int(pred) for pred in predictions]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get prediction probabilities.

        Args:
            X: Input features as numpy array

        Returns:
            Array of shape (n_samples, 2) with probabilities
        """
        # Ensure X is 2D
        if X.ndim == 1:
            X = X.reshape(1, -1)

        # Create DataFrame
        df = pd.DataFrame(X, columns=self.feature_order)

        # Get probabilities
        probabilities = self.model.predict_proba(df)

        return probabilities

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            "model_type": "CatBoostClassifier",
            "features": self.feature_order,
            "categorical_features": [self.feature_order[i] for i in self.categorical_indices],
            "n_features": len(self.feature_order)
        }