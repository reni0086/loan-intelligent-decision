import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from features_v3 import add_features  # 使用 features_v3（增强版特征工程）


def main() -> None:
    parser = argparse.ArgumentParser(description="Train default model from Hive table (features_v3).")
    parser.add_argument("--source-table", default="loan_dwd.loan_repaired_als")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument(
        "--feature-engineering",
        choices=["v2", "v3"],
        default="v3",
        help="选择特征工程版本：v2=基础特征，v3=增强特征（含时序/稳定性/复合风险）",
    )
    args = parser.parse_args()

    spark = SparkSession.builder.appName("train_from_hive").enableHiveSupport().getOrCreate()
    sdf = spark.table(args.source_table)
    pdf = sdf.toPandas()
    spark.stop()

    # 选择特征工程函数
    if args.feature_engineering == "v3":
        from features_v3 import add_features as _add_features
        version_tag = "_v3"
    else:
        from features_v2 import add_features as _add_features
        version_tag = "_v2"

    y = pdf["loan_default"].astype(int)
    X = _add_features(pdf.drop(columns=["loan_default"])).replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median(numeric_only=True)).fillna(0)

    feature_cols = X.columns.tolist()
    print(f"[train_from_hive] Feature engineering: {args.feature_engineering}, features: {len(feature_cols)}")

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
    auc = float(roc_auc_score(y_valid, p))

    out_dir = Path(args.artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = f"default_model_hive{version_tag}.joblib"
    bundle = {
        "model": model,
        "feature_cols": feature_cols,
        "feature_engineering_version": args.feature_engineering,
        "metrics": {"auc": auc},
    }
    joblib.dump(bundle, out_dir / model_name)
    (out_dir / f"default_model_hive_metrics{version_tag}.json").write_text(
        json.dumps({"auc": auc, "features": len(feature_cols), "version": args.feature_engineering}, indent=2),
        encoding="utf-8",
    )

    print(f"[train_from_hive] Training complete. AUC={auc:.6f}")
    print(f"[train_from_hive] Model: {out_dir / model_name}")


if __name__ == "__main__":
    main()
