import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Predict car loan default for test set.")
    parser.add_argument(
        "--test-path",
        type=str,
        default="test.csv",
        help="Path to test CSV file.",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="model_mvp.joblib",
        help="Trained model path.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="submission_mvp.csv",
        help="Prediction output CSV path.",
    )
    args = parser.parse_args()

    test_path = Path(args.test_path)
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_path}")

    model_path = Path(args.model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model_bundle = joblib.load(model_path)
    pipeline = model_bundle["pipeline"]
    feature_cols = model_bundle["feature_cols"]

    test_df = pd.read_csv(test_path)
    missing_cols = [c for c in feature_cols if c not in test_df.columns]
    if missing_cols:
        raise ValueError(f"Test set missing feature columns: {missing_cols}")

    X_test = test_df[feature_cols].copy()
    X_test = X_test.replace([np.inf, -np.inf], np.nan)
    pred_proba = pipeline.predict_proba(X_test)[:, 1]
    pred_label = (pred_proba >= 0.5).astype(int)

    output = pd.DataFrame(
        {
            "customer_id": test_df["customer_id"] if "customer_id" in test_df.columns else range(len(test_df)),
            "loan_default_proba": pred_proba,
            "loan_default_pred": pred_label,
        }
    )
    output.to_csv(args.output_path, index=False)

    print("Prediction completed.")
    print(f"Output saved to: {args.output_path}")
    print(f"Rows: {len(output)}")


if __name__ == "__main__":
    main()
