
from __future__ import annotations
import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.datasets import fetch_openml
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score
from catboost import CatBoostClassifier


# 1) Load a mixed-type tabular dataset (Titanic) with numerics, categoricals, bools
X, y = fetch_openml("titanic", version=1, as_frame=True, return_X_y=True)

BASE = ["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked"]
X = X[BASE].copy()

# Derive the seaborn-like columns on OpenML data
X["alone"] = (X["sibsp"].fillna(0) + X["parch"].fillna(0) == 0)
X["adult_male"] = (X["sex"].astype(str).str.lower().eq("male")) & (X["age"].fillna(99) >= 16)
X["who"] = np.where(
    X["age"].fillna(99) < 16, "child",
    np.where(X["sex"].astype(str).str.lower().eq("male"), "man", "woman")
)

FEATURES = BASE + ["who", "adult_male", "alone"]
X = X[FEATURES].copy()

# y can be string or numeric depending on OpenML version — coerce to 0/1 int
if y.dtype.kind in {"O", "U", "S"}:  # strings
    y = y.map({"yes": 1, "no": 0, "1": 1, "0": 0, "true": 1, "false": 0, "True": 1, "False": 0})
    if y.isnull().any():
        # Some variants label "survived" as 0/1 already but as string; fillna with numeric cast
        y = y.fillna(y.astype("float").fillna(0)).astype(int)
else:
    y = y.astype(int)

# 2) Preprocessing: impute + scale numerics; impute + one-hot categoricals (dense)
NUMERIC = ["pclass", "age", "sibsp", "parch", "fare"]
CATEG = ["sex", "embarked", "who", "adult_male", "alone"]

try:
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
except TypeError:
    # Backward-compat for <1.2
    ohe = OneHotEncoder(handle_unknown="ignore", sparse=False)

preprocess = ColumnTransformer(
    transformers=[
        (
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]),
            NUMERIC,
        ),
        (
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", ohe),
            ]),
            CATEG,
        ),
    ],
    remainder="drop",
)

# 3) Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() == 2 else None
)

# 4) Fit preprocessor and transform
preprocess.fit(X_train)
Xtr = preprocess.transform(X_train)
Xte = preprocess.transform(X_test)

# 5) Train CatBoost on the transformed numeric array
model = CatBoostClassifier(
    depth=6,
    learning_rate=0.1,
    iterations=300,
    loss_function="Logloss",
    verbose=False,
    random_seed=42,
)
model.fit(Xtr, y_train)

# 6) Evaluate quickly
proba = model.predict_proba(Xte)[:, 1]
auc = roc_auc_score(y_test, proba)
acc = accuracy_score(y_test, (proba > 0.5).astype(int))
print(f"AUC: {auc:.3f}  ACC: {acc:.3f}")

# 7) Persist artifacts
os.makedirs("artifacts", exist_ok=True)
# Using joblib for safer serialization of scikit-learn models
joblib.dump(preprocess, "artifacts/preprocessor.pkl")
joblib.dump(model, "artifacts/catboost_model.pkl")
with open("artifacts/feature_order.json", "w") as f:
    json.dump(FEATURES, f)

print("Artifacts written to ./artifacts")
