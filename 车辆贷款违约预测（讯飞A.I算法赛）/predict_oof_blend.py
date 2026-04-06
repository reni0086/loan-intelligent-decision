import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from features_v2 import add_features


def predict_average(models, x):
    preds = []
    for model in models:
        preds.append(model.predict_proba(x)[:, 1])
    return np.mean(np.vstack(preds), axis=0)


def main():
    parser = argparse.ArgumentParser(description="Predict with OOF blend model.")
    parser.add_argument("--test-path", type=str, default="test.csv")
    parser.add_argument("--model-path", type=str, default="model_oof_blend.joblib")
    parser.add_argument("--output-path", type=str, default="submission_oof_blend.csv")
    parser.add_argument(
        "--strict-output-path",
        type=str,
        default="submission_oof_blend_strict.csv",
        help="Competition-style output with columns: customer_id, loan_default (probability).",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    test_path = Path(args.test_path)
    model_path = Path(args.model_path)
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    bundle = joblib.load(model_path)
    raw_models = bundle["raw_models"]
    eng_models = bundle["eng_models"]
    raw_cols = bundle["raw_cols"]
    eng_cols = bundle["eng_cols"]
    w_raw = float(bundle["blend_weight_raw"])

    test_df = pd.read_csv(test_path)
    customer_id = test_df["customer_id"] if "customer_id" in test_df.columns else pd.Series(range(len(test_df)))

    x_raw = test_df.copy().replace([np.inf, -np.inf], np.nan)
    miss_raw = [c for c in raw_cols if c not in x_raw.columns]
    if miss_raw:
        raise ValueError(f"Test set missing raw feature columns: {miss_raw}")
    p_raw = predict_average(raw_models, x_raw[raw_cols])

    x_eng = add_features(test_df.copy()).replace([np.inf, -np.inf], np.nan)
    miss_eng = [c for c in eng_cols if c not in x_eng.columns]
    if miss_eng:
        raise ValueError(f"Test set missing engineered feature columns: {miss_eng}")
    p_eng = predict_average(eng_models, x_eng[eng_cols])

    p_blend = w_raw * p_raw + (1.0 - w_raw) * p_eng
    y_pred = (p_blend >= args.threshold).astype(int)

    output = pd.DataFrame(
        {
            "customer_id": customer_id,
            "loan_default_proba": p_blend,
            "loan_default_pred": y_pred,
            "proba_raw": p_raw,
            "proba_eng": p_eng,
        }
    )
    output.to_csv(args.output_path, index=False)

    strict_output = pd.DataFrame({"customer_id": customer_id, "loan_default": p_blend})
    strict_output.to_csv(args.strict_output_path, index=False)

    print("Prediction completed.")
    print(f"Blend weight(raw): {w_raw:.4f}")
    print(f"Output saved to: {args.output_path}")
    print(f"Strict output saved to: {args.strict_output_path}")
    print(f"Rows: {len(output)}")


if __name__ == "__main__":
    main()
