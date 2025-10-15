#!/usr/bin/env python3
"""
Train two different classifiers for the Titanic dataset.
This demonstrates a multi-classifier setup from a single repository.

Classifier 1: CatBoost (primary model for survival prediction)
Classifier 2: RandomForest (alternative model for comparison/ensemble)
"""

import os
import pickle
import json
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from catboost import CatBoostClassifier
import warnings
warnings.filterwarnings('ignore')


def load_and_prepare_data():
    """Load and prepare the Titanic dataset."""
    # Load data
    url = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"
    df = pd.read_csv(url)

    # Feature engineering
    df['Age'].fillna(df['Age'].median(), inplace=True)
    df['Embarked'].fillna(df['Embarked'].mode()[0], inplace=True)
    df['Fare'].fillna(df['Fare'].median(), inplace=True)
    df['FamilySize'] = df['SibSp'] + df['Parch'] + 1
    df['IsAlone'] = (df['FamilySize'] == 1).astype(int)
    df['Title'] = df['Name'].str.extract(' ([A-Za-z]+)\.', expand=False)

    # Simplify titles
    df['Title'] = df['Title'].replace(['Lady', 'Countess','Capt', 'Col','Don',
                                      'Dr', 'Major', 'Rev', 'Sir', 'Jonkheer', 'Dona'], 'Rare')
    df['Title'] = df['Title'].replace('Mlle', 'Miss')
    df['Title'] = df['Title'].replace('Ms', 'Miss')
    df['Title'] = df['Title'].replace('Mme', 'Mrs')

    return df


def create_features_catboost(df):
    """Create features for CatBoost classifier."""
    # CatBoost handles categorical features natively
    features = ['Pclass', 'Sex', 'Age', 'SibSp', 'Parch', 'Fare',
                'Embarked', 'FamilySize', 'IsAlone', 'Title']

    X = df[features].copy()
    y = df['Survived']

    # Identify categorical columns
    categorical_features = ['Sex', 'Embarked', 'Title']
    cat_features_indices = [features.index(cat) for cat in categorical_features]

    return X, y, features, cat_features_indices


def create_features_randomforest(df):
    """Create features for RandomForest classifier."""
    # RandomForest needs encoded categorical features
    features = ['Pclass', 'Sex', 'Age', 'SibSp', 'Parch', 'Fare',
                'Embarked', 'FamilySize', 'IsAlone', 'Title']

    X = df[features].copy()
    y = df['Survived']

    # Encode categorical variables
    label_encoders = {}
    categorical_features = ['Sex', 'Embarked', 'Title']

    for cat in categorical_features:
        le = LabelEncoder()
        X[cat] = le.fit_transform(X[cat].astype(str))
        label_encoders[cat] = le

    # Scale numerical features
    scaler = StandardScaler()
    numerical_features = ['Age', 'Fare', 'FamilySize']
    X[numerical_features] = scaler.fit_transform(X[numerical_features])

    return X, y, features, label_encoders, scaler


def train_catboost_classifier(X_train, y_train, X_test, y_test, cat_features_indices):
    """Train CatBoost classifier."""
    print("\n=== Training CatBoost Classifier ===")

    model = CatBoostClassifier(
        iterations=100,
        learning_rate=0.1,
        depth=5,
        cat_features=cat_features_indices,
        verbose=False,
        random_state=42
    )

    model.fit(X_train, y_train, eval_set=(X_test, y_test), verbose=False)

    # Evaluate
    y_pred = model.predict(X_test)
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1_score': f1_score(y_test, y_pred)
    }

    print(f"CatBoost Accuracy: {metrics['accuracy']:.4f}")
    print(f"CatBoost F1 Score: {metrics['f1_score']:.4f}")

    return model, metrics


def train_randomforest_classifier(X_train, y_train, X_test, y_test):
    """Train RandomForest classifier."""
    print("\n=== Training RandomForest Classifier ===")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1_score': f1_score(y_test, y_pred)
    }

    print(f"RandomForest Accuracy: {metrics['accuracy']:.4f}")
    print(f"RandomForest F1 Score: {metrics['f1_score']:.4f}")

    return model, metrics


def save_artifacts(base_path: Path, classifier_name: str, artifacts: dict):
    """Save artifacts for a classifier."""
    classifier_path = base_path / classifier_name
    classifier_path.mkdir(parents=True, exist_ok=True)

    for name, artifact in artifacts.items():
        file_path = classifier_path / name

        if name.endswith('.json'):
            with open(file_path, 'w') as f:
                json.dump(artifact, f, indent=2)
        elif name.endswith('.pkl'):
            with open(file_path, 'wb') as f:
                pickle.dump(artifact, f)

    print(f"Saved artifacts for {classifier_name} to {classifier_path}")


def main():
    """Main training pipeline for both classifiers."""
    print("Loading Titanic dataset...")
    df = load_and_prepare_data()

    # Create base artifacts directory
    base_path = Path(__file__).parent / "artifacts"
    base_path.mkdir(exist_ok=True)

    # ========================================
    # Classifier 1: CatBoost
    # ========================================
    print("\n" + "="*50)
    print("CLASSIFIER 1: CATBOOST")
    print("="*50)

    X_cb, y_cb, features_cb, cat_indices = create_features_catboost(df)
    X_train_cb, X_test_cb, y_train_cb, y_test_cb = train_test_split(
        X_cb, y_cb, test_size=0.2, random_state=42, stratify=y_cb
    )

    catboost_model, catboost_metrics = train_catboost_classifier(
        X_train_cb, y_train_cb, X_test_cb, y_test_cb, cat_indices
    )

    # Save CatBoost artifacts
    save_artifacts(
        base_path,
        "catboost-survival",
        {
            "model.pkl": catboost_model,
            "features.json": features_cb,
            "metrics.json": catboost_metrics,
            "categorical_indices.json": cat_indices
        }
    )

    # ========================================
    # Classifier 2: RandomForest
    # ========================================
    print("\n" + "="*50)
    print("CLASSIFIER 2: RANDOMFOREST")
    print("="*50)

    X_rf, y_rf, features_rf, encoders_rf, scaler_rf = create_features_randomforest(df)
    X_train_rf, X_test_rf, y_train_rf, y_test_rf = train_test_split(
        X_rf, y_rf, test_size=0.2, random_state=42, stratify=y_rf
    )

    rf_model, rf_metrics = train_randomforest_classifier(
        X_train_rf, y_train_rf, X_test_rf, y_test_rf
    )

    # Save RandomForest artifacts
    save_artifacts(
        base_path,
        "randomforest-survival",
        {
            "model.pkl": rf_model,
            "features.json": features_rf,
            "metrics.json": rf_metrics,
            "label_encoders.pkl": encoders_rf,
            "scaler.pkl": scaler_rf
        }
    )

    # ========================================
    # Summary
    # ========================================
    print("\n" + "="*50)
    print("TRAINING SUMMARY")
    print("="*50)

    print("\nCatBoost Classifier:")
    print(f"  - Accuracy: {catboost_metrics['accuracy']:.4f}")
    print(f"  - F1 Score: {catboost_metrics['f1_score']:.4f}")
    print(f"  - Artifacts: {base_path}/catboost-survival/")

    print("\nRandomForest Classifier:")
    print(f"  - Accuracy: {rf_metrics['accuracy']:.4f}")
    print(f"  - F1 Score: {rf_metrics['f1_score']:.4f}")
    print(f"  - Artifacts: {base_path}/randomforest-survival/")

    print("\n✅ Successfully trained 2 classifiers!")
    print("\nNext steps:")
    print("1. Create predictor classes for each model")
    print("2. Configure mlserver_dual_classifier.yaml")
    print("3. Deploy with: ml_server serve --classifier catboost-survival")
    print("   or: ml_server serve --classifier randomforest-survival")


if __name__ == "__main__":
    main()