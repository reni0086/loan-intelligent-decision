import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET_COL = "loan_default"


def build_model(numeric_features, categorical_features):
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )

    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )

    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def split_feature_types(df):
    feature_cols = [col for col in df.columns if col != TARGET_COL]
    categorical_features = [
        col for col in feature_cols if str(df[col].dtype) in ("object", "string")
    ]
    numeric_features = [col for col in feature_cols if col not in categorical_features]
    return feature_cols, numeric_features, categorical_features


def main():
    parser = argparse.ArgumentParser(description="Train car loan default MVP model.")
    parser.add_argument(
        "--train-path",
        type=str,
        default="car_loan_train.csv",
        help="Path to training CSV file.",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="model_mvp.joblib",
        help="Output model file path.",
    )
    parser.add_argument(
        "--metrics-path",
        type=str,
        default="metrics_mvp.txt",
        help="Output metrics report path.",
    )
    args = parser.parse_args()

    train_path = Path(args.train_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Train file not found: {train_path}")

    df = pd.read_csv(train_path)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    feature_cols, numeric_features, categorical_features = split_feature_types(df)
    X = df[feature_cols].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    y = df[TARGET_COL].astype(int).copy()

    X_train, X_valid, y_train, y_valid = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    pipeline = build_model(numeric_features, categorical_features)
    pipeline.fit(X_train, y_train)

    valid_proba = pipeline.predict_proba(X_valid)[:, 1]
    valid_pred = (valid_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_valid, valid_proba)
    acc = accuracy_score(y_valid, valid_pred)
    report = classification_report(y_valid, valid_pred, digits=4)

    model_bundle = {
        "pipeline": pipeline,
        "feature_cols": feature_cols,
        "target_col": TARGET_COL,
    }
    joblib.dump(model_bundle, args.model_path)

    metrics_text = (
        f"AUC: {auc:.6f}\n"
        f"Accuracy: {acc:.6f}\n\n"
        f"Classification Report:\n{report}\n"
        f"Train rows: {len(X_train)}\n"
        f"Valid rows: {len(X_valid)}\n"
        f"Features: {len(feature_cols)}\n"
    )
    Path(args.metrics_path).write_text(metrics_text, encoding="utf-8")

    print("Training completed.")
    print(f"Model saved to: {args.model_path}")
    print(f"Metrics saved to: {args.metrics_path}")
    print(f"AUC={auc:.6f}, ACC={acc:.6f}")


if __name__ == "__main__":
    main()
