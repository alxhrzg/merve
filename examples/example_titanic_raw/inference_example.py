"""
Titanic Survival Classifier - Inference Demo Script

This script demonstrates how to load trained artifacts and perform inference
on the Titanic survival prediction model. This is an example of the kind of
Python file that could be used with `ml_server ainit` to automatically
generate MLServer configuration files.
"""

import joblib
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Load trained artifacts
print("Loading model artifacts...")

# Define paths to artifacts (this would be auto-detected by ainit)
artifacts_path = Path("../example_titanic_manual_setup/artifacts")
model_path = artifacts_path / "catboost_model.pkl"
preprocessor_path = artifacts_path / "preprocessor.pkl"
feature_order_path = artifacts_path / "feature_order.json"

# Load preprocessor using joblib for safer deserialization
preprocessor = joblib.load(preprocessor_path)

# Load CatBoost model using joblib for safer deserialization
model = joblib.load(model_path)

# Load feature order
with open(feature_order_path, "r") as f:
    feature_order = json.load(f)

print("Artifacts loaded successfully!")
print(f"Feature order: {feature_order}")


def engineer_features(df):
    """Apply the same feature engineering as in training."""
    df = df.copy()

    # Derive additional features
    df["alone"] = (df["sibsp"].fillna(0) + df["parch"].fillna(0) == 0)
    df["adult_male"] = (df["sex"].astype(str).str.lower().eq("male")) & (df["age"].fillna(99) >= 16)
    df["who"] = np.where(
        df["age"].fillna(99) < 16, "child",
        np.where(df["sex"].astype(str).str.lower().eq("male"), "man", "woman")
    )

    # Reorder columns to match training feature order
    return df[feature_order]


def predict_survival(passenger_data):
    """Predict survival probability for passenger data."""
    if isinstance(passenger_data, dict):
        passenger_data = pd.DataFrame([passenger_data])

    # Apply feature engineering
    features = engineer_features(passenger_data)

    # Preprocess features
    X_processed = preprocessor.transform(features)

    # Get prediction probabilities
    proba = model.predict_proba(X_processed)[:, 1]

    return proba


# Example passengers for testing
print("\n" + "="*50)
print("Testing inference with example passengers:")

passengers = [
    {
        "pclass": 1,
        "sex": "female",
        "age": 25,
        "sibsp": 0,
        "parch": 0,
        "fare": 80.0,
        "embarked": "S"
    },
    {
        "pclass": 3,
        "sex": "male",
        "age": 30,
        "sibsp": 1,
        "parch": 2,
        "fare": 15.0,
        "embarked": "Q"
    },
    {
        "pclass": 2,
        "sex": "female",
        "age": 5,
        "sibsp": 1,
        "parch": 1,
        "fare": 25.0,
        "embarked": "C"
    }
]

# Create DataFrame
passenger_df = pd.DataFrame(passengers)
print("\nExample passengers:")
print(passenger_df)

# Get predictions
survival_probs = predict_survival(passenger_df)

# Display results
results = passenger_df.copy()
results['survival_probability'] = survival_probs
results['predicted_survival'] = (survival_probs > 0.5).astype(int)

print("\nPrediction results:")
print(results[['pclass', 'sex', 'age', 'survival_probability', 'predicted_survival']])

# Single passenger example
print("\n" + "="*50)
print("Single passenger prediction:")

single_passenger = {
    "pclass": 1,
    "sex": "female",
    "age": 28,
    "sibsp": 1,
    "parch": 0,
    "fare": 120.0,
    "embarked": "S"
}

survival_prob = predict_survival(single_passenger)[0]
print(f"Passenger: {single_passenger}")
print(f"Survival probability: {survival_prob:.3f}")
print(f"Predicted outcome: {'Survived' if survival_prob > 0.5 else 'Did not survive'}")

# Model information
print("\n" + "="*50)
print("Model Information:")
print(f"Model type: {type(model).__name__}")
print(f"Feature count: {model.feature_count_}")
print(f"Tree count: {model.tree_count_}")

print("\nPreprocessor Information:")
print(f"Preprocessor type: {type(preprocessor).__name__}")
print(f"Feature names in: {feature_order}")
print(f"Transformed feature count: {preprocessor.transform(pd.DataFrame([single_passenger])).shape[1]}")


# This is the pattern that ainit would extract for the predictor class
class TitanicPredictor:
    """Example predictor class that ainit would generate."""

    def __init__(self, model_path: str, preprocessor_path: str, feature_order_path: str):
        # Load artifacts
        # Using joblib for safer deserialization
        self.model = joblib.load(model_path)
        self.preprocessor = joblib.load(preprocessor_path)
        with open(feature_order_path, "r") as f:
            self.feature_order = json.load(f)

    def _engineer_features(self, df):
        """Apply feature engineering."""
        df = df.copy()
        df["alone"] = (df["sibsp"].fillna(0) + df["parch"].fillna(0) == 0)
        df["adult_male"] = (df["sex"].astype(str).str.lower().eq("male")) & (df["age"].fillna(99) >= 16)
        df["who"] = np.where(
            df["age"].fillna(99) < 16, "child",
            np.where(df["sex"].astype(str).str.lower().eq("male"), "man", "woman")
        )
        return df[self.feature_order]

    def predict(self, X):
        """Predict survival probability."""
        if isinstance(X, dict):
            X = pd.DataFrame([X])
        elif isinstance(X, list):
            X = pd.DataFrame(X)

        # Feature engineering
        features = self._engineer_features(X)

        # Preprocessing
        X_processed = self.preprocessor.transform(features)

        # Prediction
        proba = self.model.predict_proba(X_processed)[:, 1]
        return proba.tolist()

    def predict_proba(self, X):
        """Return full probability matrix."""
        if isinstance(X, dict):
            X = pd.DataFrame([X])
        elif isinstance(X, list):
            X = pd.DataFrame(X)

        features = self._engineer_features(X)
        X_processed = self.preprocessor.transform(features)
        proba = self.model.predict_proba(X_processed)
        return proba.tolist()


# Demo the predictor class
print("\n" + "="*50)
print("Testing Predictor Class:")

predictor = TitanicPredictor(
    model_path=str(model_path),
    preprocessor_path=str(preprocessor_path),
    feature_order_path=str(feature_order_path)
)

test_result = predictor.predict(single_passenger)
print(f"Predictor class result: {test_result[0]:.3f}")

print("\n🚀 This script demonstrates patterns that ml_server ainit would extract!")
print("Run: ml_server ainit inference_example.py --trace")