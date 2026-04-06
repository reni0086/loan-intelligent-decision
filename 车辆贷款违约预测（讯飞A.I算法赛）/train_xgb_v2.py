import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from features_v2 import add_features


TARGET_COL = "loan_default"


def find_best_threshold(y_true, y_proba):
    best_thr = 0.5
    best_f1 = -1.0
    for thr in np.linspace(0.2, 0.8, 121):
        y_pred = (y_proba >= thr).astype(int)
        f1 = f1_score(y_true, y_pred)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return best_thr, best_f1


def build_candidates(scale_pos_weight):
    common = dict(
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=scale_pos_weight,
    )
    return [
        dict(common, n_estimators=700, learning_rate=0.04, max_depth=6, min_child_weight=5, subsample=0.85, colsample_bytree=0.85, reg_alpha=0.1, reg_lambda=2.0),
        dict(common, n_estimators=900, learning_rate=0.03, max_depth=7, min_child_weight=8, subsample=0.80, colsample_bytree=0.80, reg_alpha=0.3, reg_lambda=2.5),
        dict(common, n_estimators=600, learning_rate=0.05, max_depth=5, min_child_weight=4, subsample=0.90, colsample_bytree=0.90, reg_alpha=0.0, reg_lambda=1.8),
    ]


def main():
    parser = argparse.ArgumentParser(description="Train XGBoost v2 with feature engineering.")
    parser.add_argument("--train-path", type=str, default="car_loan_train.csv")
    parser.add_argument("--model-path", type=str, default="model_xgb_v2.joblib")
    parser.add_argument("--metrics-path", type=str, default="metrics_xgb_v2.txt")
    args = parser.parse_args()

    train_path = Path(args.train_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Train file not found: {train_path}")

    df = pd.read_csv(train_path)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    y = df[TARGET_COL].astype(int).copy()
    X = df.drop(columns=[TARGET_COL]).copy()
    X = add_features(X)
    feature_cols = X.columns.tolist()

    X_train, X_valid, y_train, y_valid = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos_weight = float(neg / max(pos, 1))

    best_auc = -1.0
    best_model = None
    best_params = None

    for params in build_candidates(scale_pos_weight):
        model = XGBClassifier(**params)
        model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)
        proba = model.predict_proba(X_valid)[:, 1]
        auc = roc_auc_score(y_valid, proba)
        if auc > best_auc:
            best_auc = auc
            best_model = model
            best_params = params

    valid_proba = best_model.predict_proba(X_valid)[:, 1]
    best_thr, best_f1 = find_best_threshold(y_valid.values, valid_proba)
    valid_pred = (valid_proba >= best_thr).astype(int)
    acc = accuracy_score(y_valid, valid_pred)
    report = classification_report(y_valid, valid_pred, digits=4)

    bundle = {
        "model": best_model,
        "feature_cols": feature_cols,
        "target_col": TARGET_COL,
        "best_threshold": best_thr,
        "best_params": best_params,
        "version": "xgb_v2_feature_engineering",
    }
    joblib.dump(bundle, args.model_path)

    metrics_text = (
        f"AUC: {best_auc:.6f}\n"
        f"Accuracy@best_thr: {acc:.6f}\n"
        f"Best threshold (F1): {best_thr:.4f}\n"
        f"Best F1: {best_f1:.6f}\n"
        f"Feature count: {len(feature_cols)}\n"
        f"scale_pos_weight: {scale_pos_weight:.4f}\n"
        f"Best params: {best_params}\n\n"
        f"Classification Report @ best threshold:\n{report}\n"
    )
    Path(args.metrics_path).write_text(metrics_text, encoding="utf-8")

    print("XGBoost v2 training completed.")
    print(f"Model saved to: {args.model_path}")
    print(f"Metrics saved to: {args.metrics_path}")
    print(f"AUC={best_auc:.6f}, ACC={acc:.6f}, BEST_THR={best_thr:.4f}, BEST_F1={best_f1:.6f}")


if __name__ == "__main__":
    main()
