import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from features_v2 import add_features


TARGET_COL = "loan_default"


def build_xgb_params(scale_pos_weight, mode):
    common = dict(
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
        scale_pos_weight=scale_pos_weight,
    )
    if mode == "raw":
        return dict(
            common,
            n_estimators=650,
            learning_rate=0.04,
            max_depth=6,
            min_child_weight=5,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.1,
            reg_lambda=2.0,
        )
    return dict(
        common,
        n_estimators=600,
        learning_rate=0.05,
        max_depth=5,
        min_child_weight=4,
        subsample=0.90,
        colsample_bytree=0.90,
        reg_alpha=0.0,
        reg_lambda=1.8,
    )


def to_features_raw(df):
    x = df.copy()
    x = x.replace([np.inf, -np.inf], np.nan)
    return x


def to_features_eng(df):
    x = add_features(df.copy())
    x = x.replace([np.inf, -np.inf], np.nan)
    return x


def run_oof(x, y, params, n_splits=5):
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof = np.zeros(len(y), dtype=float)
    models = []

    for fold, (tr_idx, va_idx) in enumerate(skf.split(x, y), start=1):
        x_tr = x.iloc[tr_idx]
        y_tr = y.iloc[tr_idx]
        x_va = x.iloc[va_idx]
        y_va = y.iloc[va_idx]

        model = XGBClassifier(**params)
        model.fit(x_tr, y_tr, eval_set=[(x_va, y_va)], verbose=False)
        oof[va_idx] = model.predict_proba(x_va)[:, 1]
        models.append(model)
        fold_auc = roc_auc_score(y_va, oof[va_idx])
        print(f"Fold {fold} AUC: {fold_auc:.6f}")

    auc = roc_auc_score(y, oof)
    return oof, auc, models


def find_best_weight(y, p_raw, p_eng):
    best_w = 0.5
    best_auc = -1.0
    for w in np.linspace(0.0, 1.0, 41):
        p = w * p_raw + (1.0 - w) * p_eng
        auc = roc_auc_score(y, p)
        if auc > best_auc:
            best_auc = auc
            best_w = float(w)
    return best_w, best_auc


def main():
    parser = argparse.ArgumentParser(description="Train OOF blend model for leaderboard boost.")
    parser.add_argument("--train-path", type=str, default="car_loan_train.csv")
    parser.add_argument("--model-path", type=str, default="model_oof_blend.joblib")
    parser.add_argument("--metrics-path", type=str, default="metrics_oof_blend.txt")
    parser.add_argument("--oof-path", type=str, default="oof_blend.csv")
    args = parser.parse_args()

    train_path = Path(args.train_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Train file not found: {train_path}")

    df = pd.read_csv(train_path)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    y = df[TARGET_COL].astype(int).copy()
    x_base = df.drop(columns=[TARGET_COL]).copy()
    customer_id = x_base["customer_id"].copy() if "customer_id" in x_base.columns else pd.Series(np.arange(len(x_base)))

    pos = y.sum()
    neg = len(y) - pos
    scale_pos_weight = float(neg / max(pos, 1))

    x_raw = to_features_raw(x_base)
    raw_cols = x_raw.columns.tolist()
    raw_params = build_xgb_params(scale_pos_weight, mode="raw")
    oof_raw, auc_raw, raw_models = run_oof(x_raw, y, raw_params, n_splits=5)
    print(f"OOF AUC raw: {auc_raw:.6f}")

    x_eng = to_features_eng(x_base)
    eng_cols = x_eng.columns.tolist()
    eng_params = build_xgb_params(scale_pos_weight, mode="eng")
    oof_eng, auc_eng, eng_models = run_oof(x_eng, y, eng_params, n_splits=5)
    print(f"OOF AUC engineered: {auc_eng:.6f}")

    best_w, best_auc = find_best_weight(y, oof_raw, oof_eng)
    oof_blend = best_w * oof_raw + (1.0 - best_w) * oof_eng
    print(f"Best blend weight(raw): {best_w:.3f}, OOF AUC blend: {best_auc:.6f}")

    oof_df = pd.DataFrame(
        {
            "customer_id": customer_id,
            "y_true": y,
            "oof_raw": oof_raw,
            "oof_eng": oof_eng,
            "oof_blend": oof_blend,
        }
    )
    oof_df.to_csv(args.oof_path, index=False)

    model_bundle = {
        "raw_models": raw_models,
        "eng_models": eng_models,
        "raw_cols": raw_cols,
        "eng_cols": eng_cols,
        "blend_weight_raw": best_w,
        "target_col": TARGET_COL,
        "version": "oof_blend_v1",
    }
    joblib.dump(model_bundle, args.model_path)

    metrics_text = (
        f"OOF AUC raw: {auc_raw:.6f}\n"
        f"OOF AUC engineered: {auc_eng:.6f}\n"
        f"OOF AUC blend: {best_auc:.6f}\n"
        f"Best blend weight(raw): {best_w:.4f}\n"
        f"scale_pos_weight: {scale_pos_weight:.4f}\n"
        f"Train rows: {len(y)}\n"
        f"Raw feature count: {len(raw_cols)}\n"
        f"Engineered feature count: {len(eng_cols)}\n"
    )
    Path(args.metrics_path).write_text(metrics_text, encoding="utf-8")

    print("OOF blend training completed.")
    print(f"Model saved to: {args.model_path}")
    print(f"Metrics saved to: {args.metrics_path}")
    print(f"OOF saved to: {args.oof_path}")


if __name__ == "__main__":
    main()
