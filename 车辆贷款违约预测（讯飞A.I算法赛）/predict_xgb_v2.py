import argparse
from pathlib import Path

import joblib
import pandas as pd

from features_v2 import add_features


def main():
    parser = argparse.ArgumentParser(description="Predict with XGBoost v2 model.")
    parser.add_argument("--test-path", type=str, default="test.csv")
    parser.add_argument("--model-path", type=str, default="model_xgb_v2.joblib")
    parser.add_argument("--output-path", type=str, default="submission_xgb_v2.csv")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    test_path = Path(args.test_path)
    model_path = Path(args.model_path)
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    bundle = joblib.load(model_path)
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    default_thr = float(bundle.get("best_threshold", 0.5))
    use_thr = float(args.threshold) if args.threshold is not None else default_thr

    test_df = pd.read_csv(test_path)
    X = test_df.copy()
    X = add_features(X)

    missing_cols = [c for c in feature_cols if c not in X.columns]
    if missing_cols:
        raise ValueError(f"Test set missing feature columns: {missing_cols}")
    X = X[feature_cols]

    pred_proba = model.predict_proba(X)[:, 1]
    pred_label = (pred_proba >= use_thr).astype(int)

    output = pd.DataFrame(
        {
            "customer_id": test_df["customer_id"] if "customer_id" in test_df.columns else range(len(test_df)),
            "loan_default_proba": pred_proba,
            "loan_default_pred": pred_label,
        }
    )
    output.to_csv(args.output_path, index=False)

    print("Prediction completed.")
    print(f"Threshold used: {use_thr:.4f}")
    print(f"Output saved to: {args.output_path}")
    print(f"Rows: {len(output)}")


if __name__ == "__main__":
    main()
