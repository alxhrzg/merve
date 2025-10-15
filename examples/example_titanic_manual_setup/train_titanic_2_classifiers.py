#!/usr/bin/env python3
"""Train multiple Titanic survival prediction models for multi-classifier demo."""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from catboost import CatBoostClassifier
import pickle
import json
from pathlib import Path


def prepare_data():
    """Load and prepare Titanic dataset."""
    # Load Titanic dataset
    from sklearn.datasets import fetch_openml
    titanic = fetch_openml("titanic", version=1, as_frame=True, return_X_y=False)
    df = titanic.frame

    # Convert column names to lowercase (OpenML uses lowercase)
    df.columns = [col.lower() for col in df.columns]

    # Handle missing values
    df['age'].fillna(df['age'].median(), inplace=True)
    df['fare'].fillna(df['fare'].median(), inplace=True)
    df['embarked'].fillna(df['embarked'].mode()[0], inplace=True)

    # Feature engineering
    df['FamilySize'] = df['sibsp'] + df['parch'] + 1
    df['IsAlone'] = (df['FamilySize'] == 1).astype(int)

    # Extract title from name
    df['Title'] = df['name'].str.extract(r' ([A-Za-z]+)\.', expand=False)
    df['Title'] = df['Title'].replace(['Lady', 'Countess','Capt', 'Col','Don',
                                       'Dr', 'Major', 'Rev', 'Sir', 'Jonkheer', 'Dona'], 'Rare')
    df['Title'] = df['Title'].replace('Mlle', 'Miss')
    df['Title'] = df['Title'].replace('Ms', 'Miss')
    df['Title'] = df['Title'].replace('Mme', 'Mrs')

    # Select features
    feature_cols = ['pclass', 'sex', 'age', 'sibsp', 'parch',
                   'fare', 'embarked', 'FamilySize', 'IsAlone', 'Title']

    # Encode categorical variables
    label_encoders = {}
    for col in ['sex', 'embarked', 'Title']:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        label_encoders[col] = le

    X = df[feature_cols]
    y = df['survived'].astype(int)

    return X, y, feature_cols, label_encoders


def train_catboost_model(X_train, y_train, X_test, y_test, feature_cols):
    """Train CatBoost model."""
    print("\n=== Training CatBoost Model ===")

    # Create model
    model = CatBoostClassifier(
        iterations=100,
        depth=6,
        learning_rate=0.1,
        random_state=42,
        verbose=False
    )

    # Train
    model.fit(X_train, y_train)

    # Evaluate
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    print(f"CatBoost - Train accuracy: {train_score:.4f}")
    print(f"CatBoost - Test accuracy: {test_score:.4f}")

    # Save model and metadata
    artifacts_dir = Path("artifacts/catboost-survival")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with open(artifacts_dir / "model.pkl", "wb") as f:
        pickle.dump(model, f)

    with open(artifacts_dir / "features.json", "w") as f:
        json.dump(feature_cols, f)

    # Also save in old location for backward compatibility
    with open("artifacts/catboost_model.pkl", "wb") as f:
        pickle.dump(model, f)

    # Create simple preprocessor (just feature names)
    preprocessor = {"feature_order": feature_cols}
    with open("artifacts/preprocessor.pkl", "wb") as f:
        pickle.dump(preprocessor, f)

    return model, test_score


def train_randomforest_model(X_train, y_train, X_test, y_test, feature_cols, label_encoders):
    """Train RandomForest model."""
    print("\n=== Training RandomForest Model ===")

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Create model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )

    # Train
    model.fit(X_train_scaled, y_train)

    # Evaluate
    train_score = model.score(X_train_scaled, y_train)
    test_score = model.score(X_test_scaled, y_test)
    print(f"RandomForest - Train accuracy: {train_score:.4f}")
    print(f"RandomForest - Test accuracy: {test_score:.4f}")

    # Save model and artifacts
    artifacts_dir = Path("artifacts/randomforest-survival")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with open(artifacts_dir / "model.pkl", "wb") as f:
        pickle.dump(model, f)

    with open(artifacts_dir / "features.json", "w") as f:
        json.dump(feature_cols, f)

    with open(artifacts_dir / "label_encoders.pkl", "wb") as f:
        pickle.dump(label_encoders, f)

    with open(artifacts_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    return model, test_score


def create_predictor_randomforest():
    """Create RandomForest predictor class file."""
    predictor_code = '''"""RandomForest predictor for Titanic survival."""
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
            X = pd.DataFrame(X, columns=self.feature_names[:len(X[0])] if X else [])

        # Preprocess
        X_processed = self.preprocess(X)

        # Predict
        predictions = self.model.predict(X_processed)

        return predictions

    def predict_proba(self, X: Union[List, np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class probabilities."""
        # Convert to DataFrame if necessary
        if isinstance(X, (list, np.ndarray)):
            X = pd.DataFrame(X, columns=self.feature_names[:len(X[0])] if X else [])

        # Preprocess
        X_processed = self.preprocess(X)

        # Predict probabilities
        probabilities = self.model.predict_proba(X_processed)

        return probabilities
'''

    with open("predictor_randomforest.py", "w") as f:
        f.write(predictor_code)

    print("Created predictor_randomforest.py")


def main():
    """Main training pipeline."""
    print("Starting multi-classifier training pipeline...")

    # Prepare data
    X, y, feature_cols, label_encoders = prepare_data()

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train CatBoost model
    catboost_model, catboost_score = train_catboost_model(
        X_train, y_train, X_test, y_test, feature_cols
    )

    # Train RandomForest model
    rf_model, rf_score = train_randomforest_model(
        X_train, y_train, X_test, y_test, feature_cols, label_encoders
    )

    # Create RandomForest predictor class
    create_predictor_randomforest()

    # Print summary
    print("\n=== Training Complete ===")
    print(f"CatBoost accuracy: {catboost_score:.4f}")
    print(f"RandomForest accuracy: {rf_score:.4f}")
    print("\nArtifacts saved:")
    print("  - artifacts/catboost-survival/")
    print("  - artifacts/randomforest-survival/")
    print("  - predictor_randomforest.py created")


if __name__ == "__main__":
    main()