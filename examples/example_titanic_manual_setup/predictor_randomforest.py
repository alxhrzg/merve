"""RandomForest predictor for Titanic survival."""
import pickle
import json
import numpy as np
import pandas as pd
from typing import List, Union, Any
from pathlib import Path


class RandomForestSurvivalPredictor:
    """RandomForest predictor for Titanic survival prediction."""

    def __init__(self,
                 model_path: str,
                 features_path: str,
                 encoders_path: str,
                 scaler_path: str):
        """Initialize predictor with model and preprocessing artifacts."""
        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load features
        with open(features_path, 'r') as f:
            self.feature_names = json.load(f)

        # Load encoders
        with open(encoders_path, 'rb') as f:
            self.label_encoders = pickle.load(f)

        # Load scaler
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)

    def preprocess(self, data: pd.DataFrame) -> np.ndarray:
        """Preprocess input data."""
        # Ensure all expected features are present
        for feature in self.feature_names:
            if feature not in data.columns:
                # Handle feature engineering
                if feature == 'FamilySize':
                    data['FamilySize'] = data.get('SibSp', 0) + data.get('Parch', 0) + 1
                elif feature == 'IsAlone':
                    data['IsAlone'] = (data.get('FamilySize', 1) == 1).astype(int)

        # Apply label encoding for categorical features
        for col in ['sex', 'embarked', 'Title']:
            if col in data.columns and col in self.label_encoders:
                # Map string values to encoded values
                data[col] = self.label_encoders[col].transform(data[col].astype(str))

        # Select and order features
        X = data[self.feature_names].values

        # Scale features
        X_scaled = self.scaler.transform(X)

        return X_scaled

    def predict(self, X: Union[List, np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Make predictions."""
        # Convert to DataFrame if necessary
        if isinstance(X, (list, np.ndarray)):
            if isinstance(X, np.ndarray) and len(X.shape) == 2:
                X = pd.DataFrame(X, columns=self.feature_names[:X.shape[1]])
            elif isinstance(X, list) and len(X) > 0:
                X = pd.DataFrame(X, columns=self.feature_names[:len(X[0])])

        # Preprocess
        X_processed = self.preprocess(X)

        # Predict
        predictions = self.model.predict(X_processed)

        return predictions

    def predict_proba(self, X: Union[List, np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class probabilities."""
        # Convert to DataFrame if necessary
        if isinstance(X, (list, np.ndarray)):
            if isinstance(X, np.ndarray) and len(X.shape) == 2:
                X = pd.DataFrame(X, columns=self.feature_names[:X.shape[1]])
            elif isinstance(X, list) and len(X) > 0:
                X = pd.DataFrame(X, columns=self.feature_names[:len(X[0])])

        # Preprocess
        X_processed = self.preprocess(X)

        # Predict probabilities
        probabilities = self.model.predict_proba(X_processed)

        return probabilities
