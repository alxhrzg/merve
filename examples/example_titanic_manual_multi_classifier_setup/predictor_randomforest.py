"""
RandomForest Predictor for Titanic survival prediction.
This is the second classifier in our multi-classifier setup.
"""

import pickle
import json
import numpy as np
import pandas as pd
from typing import List, Any, Optional, Dict
from pathlib import Path


class RandomForestSurvivalPredictor:
    """RandomForest-based Titanic survival predictor."""

    def __init__(self,
                 model_path: str = "./artifacts/randomforest-survival/model.pkl",
                 features_path: str = "./artifacts/randomforest-survival/features.json",
                 encoders_path: str = "./artifacts/randomforest-survival/label_encoders.pkl",
                 scaler_path: str = "./artifacts/randomforest-survival/scaler.pkl"):
        """Initialize the RandomForest predictor.

        Args:
            model_path: Path to the trained RandomForest model
            features_path: Path to the feature list
            encoders_path: Path to label encoders
            scaler_path: Path to the scaler
        """
        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load feature order
        with open(features_path, 'r') as f:
            self.feature_order = json.load(f)

        # Load label encoders
        with open(encoders_path, 'rb') as f:
            self.label_encoders = pickle.load(f)

        # Load scaler
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)

        self.categorical_features = ['Sex', 'Embarked', 'Title']
        self.numerical_features = ['Age', 'Fare', 'FamilySize']

        print(f"Loaded RandomForest model with features: {self.feature_order}")

    def preprocess(self, X: pd.DataFrame) -> np.ndarray:
        """Preprocess input data.

        Args:
            X: Input DataFrame

        Returns:
            Preprocessed numpy array
        """
        X_processed = X.copy()

        # Encode categorical features
        for cat in self.categorical_features:
            if cat in X_processed.columns and cat in self.label_encoders:
                # Handle unknown categories by using the most frequent category
                le = self.label_encoders[cat]
                X_processed[cat] = X_processed[cat].apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else 0
                )

        # Scale numerical features
        if all(feat in X_processed.columns for feat in self.numerical_features):
            X_processed[self.numerical_features] = self.scaler.transform(
                X_processed[self.numerical_features]
            )

        return X_processed.values

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

        # Create DataFrame with proper feature names
        df = pd.DataFrame(X, columns=self.feature_order)

        # Preprocess
        X_processed = self.preprocess(df)

        # Make predictions
        predictions = self.model.predict(X_processed)

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

        # Preprocess
        X_processed = self.preprocess(df)

        # Get probabilities
        probabilities = self.model.predict_proba(X_processed)

        return probabilities

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            "model_type": "RandomForestClassifier",
            "features": self.feature_order,
            "categorical_features": self.categorical_features,
            "numerical_features": self.numerical_features,
            "n_features": len(self.feature_order),
            "n_estimators": self.model.n_estimators
        }