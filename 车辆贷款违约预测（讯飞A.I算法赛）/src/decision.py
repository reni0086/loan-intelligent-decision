import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier, XGBRegressor

from features_v2 import add_features
from src.config import ProjectConfig


def _load_training_data(cfg: ProjectConfig) -> pd.DataFrame:
    repaired = cfg.featured_dir / "train_repaired.csv"
    if repaired.exists():
        return pd.read_csv(repaired)
    fallback = cfg.cleaned_dir / "train_cleaned.csv"
    if fallback.exists():
        return pd.read_csv(fallback)
    raise FileNotFoundError("No cleaned/repaired training data found. Run ingest and repair modules first.")


def train_default_model(cfg: ProjectConfig, df: pd.DataFrame) -> dict:
    work = df.copy()
    y = work["loan_default"].astype(int)
    X = work.drop(columns=["loan_default"])
    X = add_features(X).replace([np.inf, -np.inf], np.nan)

    X_train, X_valid, y_train, y_valid = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    pos = y_train.sum()
    neg = len(y_train) - pos
    model = XGBClassifier(
        n_estimators=700,
        learning_rate=0.04,
        max_depth=6,
        min_child_weight=5,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.1,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=float(neg / max(pos, 1)),
    )
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)
    p = model.predict_proba(X_valid)[:, 1]
    y_pred = (p >= 0.5).astype(int)
    metrics = {
        "auc": float(roc_auc_score(y_valid, p)),
        "accuracy": float(accuracy_score(y_valid, y_pred)),
        "precision": float(precision_score(y_valid, y_pred, zero_division=0)),
        "recall": float(recall_score(y_valid, y_pred, zero_division=0)),
        "f1": float(f1_score(y_valid, y_pred, zero_division=0)),
        "threshold": 0.5,
    }
    artifact = {
        "model": model,
        "feature_cols": X.columns.tolist(),
        "metrics": metrics,
        "type": "default_classifier",
    }
    out = cfg.artifacts_dir / "default_model.joblib"
    joblib.dump(artifact, out)
    return {"artifact": str(out), "metrics": metrics}


def _build_fraud_label(df: pd.DataFrame) -> pd.Series:
    score = (
        (df["enquirie_no"] > df["enquirie_no"].quantile(0.9)).astype(int)
        + (df["last_six_month_new_loan_no"] > df["last_six_month_new_loan_no"].quantile(0.9)).astype(int)
        + (df["total_overdue_no"] > 2).astype(int)
        + ((df["idcard_flag"] == 0) | (df["mobileno_flag"] == 0)).astype(int)
    )
    return (score >= 2).astype(int)


def train_fraud_model(cfg: ProjectConfig, df: pd.DataFrame) -> dict:
    work = df.copy()
    y = _build_fraud_label(work)
    X = work.drop(columns=["loan_default"], errors="ignore")
    X = add_features(X).replace([np.inf, -np.inf], np.nan)

    X_train, X_valid, y_train, y_valid = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    pos = y_train.sum()
    neg = len(y_train) - pos
    model = XGBClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=5,
        min_child_weight=3,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=float(neg / max(pos, 1)),
    )
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)
    p = model.predict_proba(X_valid)[:, 1]
    y_pred = (p >= 0.5).astype(int)
    metrics = {
        "auc": float(roc_auc_score(y_valid, p)),
        "accuracy": float(accuracy_score(y_valid, y_pred)),
        "precision": float(precision_score(y_valid, y_pred, zero_division=0)),
        "recall": float(recall_score(y_valid, y_pred, zero_division=0)),
        "f1": float(f1_score(y_valid, y_pred, zero_division=0)),
    }
    artifact = {
        "model": model,
        "feature_cols": X.columns.tolist(),
        "metrics": metrics,
        "type": "fraud_classifier",
    }
    out = cfg.artifacts_dir / "fraud_model.joblib"
    joblib.dump(artifact, out)
    return {"artifact": str(out), "metrics": metrics}


def train_limit_model(cfg: ProjectConfig, df: pd.DataFrame) -> dict:
    work = df.copy()
    y = work["disbursed_amount"].astype(float)
    X_full = add_features(work.drop(columns=["loan_default"], errors="ignore")).replace([np.inf, -np.inf], np.nan)
    X = X_full.drop(columns=["disbursed_amount"], errors="ignore")
    fill_values = X.median(numeric_only=True).to_dict()
    X = X.fillna(fill_values).fillna(0)

    X_train, X_valid, y_train, y_valid = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "random_forest": RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
        "gbr": GradientBoostingRegressor(random_state=42),
        "xgb_reg": XGBRegressor(
            n_estimators=600,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.5,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
        ),
    }

    results = {}
    best_name = None
    best_rmse = float("inf")
    best_model = None
    for name, m in models.items():
        m.fit(X_train, y_train)
        pred = m.predict(X_valid)
        rmse = float(np.sqrt(mean_squared_error(y_valid, pred)))
        mae = float(mean_absolute_error(y_valid, pred))
        mape = float(np.mean(np.abs((y_valid - pred) / np.clip(np.abs(y_valid), 1e-6, None))))
        results[name] = {"rmse": rmse, "mae": mae, "mape": mape}
        if rmse < best_rmse:
            best_rmse = rmse
            best_name = name
            best_model = m

    artifact = {
        "model": best_model,
        "feature_cols": X.columns.tolist(),
        "best_model_name": best_name,
        "fill_values": fill_values,
        "comparison": results,
        "type": "limit_regressor",
    }
    out = cfg.artifacts_dir / "limit_model.joblib"
    joblib.dump(artifact, out)
    return {"artifact": str(out), "best_model": best_name, "comparison": results}


def score_from_probability(default_prob: np.ndarray) -> np.ndarray:
    p = np.clip(default_prob, 1e-6, 1 - 1e-6)
    odds = p / (1 - p)
    score = 600 - 50 * np.log(odds)
    return np.clip(score, 300, 850)


def run_decision_suite(cfg: ProjectConfig) -> Path:
    cfg.artifacts_dir.mkdir(parents=True, exist_ok=True)
    df = _load_training_data(cfg)
    default_info = train_default_model(cfg, df)
    fraud_info = train_fraud_model(cfg, df)
    limit_info = train_limit_model(cfg, df)

    default_bundle = joblib.load(default_info["artifact"])
    model = default_bundle["model"]
    cols = default_bundle["feature_cols"]
    x = add_features(df.drop(columns=["loan_default"]).copy()).replace([np.inf, -np.inf], np.nan)[cols]
    p = model.predict_proba(x)[:, 1]
    score = score_from_probability(p)
    score_report = {
        "score_min": float(np.min(score)),
        "score_max": float(np.max(score)),
        "score_mean": float(np.mean(score)),
    }

    registry = {
        "default_model": default_info,
        "fraud_model": fraud_info,
        "limit_model": limit_info,
        "credit_score_summary": score_report,
    }
    out = cfg.artifacts_dir / "model_registry.json"
    out.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
