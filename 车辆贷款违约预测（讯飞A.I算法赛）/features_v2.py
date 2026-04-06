import numpy as np
import pandas as pd


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / (b.replace(0, np.nan) + 1e-6)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.replace([np.inf, -np.inf], np.nan)

    # Ratios and risk behavior features
    out["ltv_ratio"] = _safe_div(out["disbursed_amount"], out["asset_cost"])
    out["loan_asset_gap"] = out["asset_cost"] - out["disbursed_amount"]
    out["overdue_rate_total"] = _safe_div(out["total_overdue_no"], out["total_account_loan_no"] + 1)
    out["overdue_rate_main"] = _safe_div(
        out["main_account_overdue_no"], out["main_account_loan_no"] + 1
    )
    out["overdue_rate_sub"] = _safe_div(
        out["sub_account_overdue_no"], out["sub_account_loan_no"] + 1
    )
    out["recent_default_rate"] = _safe_div(
        out["last_six_month_defaulted_no"], out["last_six_month_new_loan_no"] + 1
    )
    out["active_ratio"] = _safe_div(
        out["main_account_active_loan_no"] + out["sub_account_active_loan_no"],
        out["total_account_loan_no"] + 1,
    )
    out["inactive_ratio"] = _safe_div(
        out["total_inactive_loan_no"], out["total_account_loan_no"] + 1
    )
    out["monthly_payment_ratio"] = _safe_div(
        out["total_monthly_payment"], out["total_disbursed_loan"] + 1
    )
    out["credit_per_age"] = _safe_div(out["credit_history"], out["age"] + 1)
    out["enquiry_per_age"] = _safe_div(out["enquirie_no"], out["age"] + 1)
    out["sanction_disburse_gap"] = out["total_sanction_loan"] - out["total_disbursed_loan"]

    # Stabilize heavy-tail numeric variables
    log_cols = [
        "disbursed_amount",
        "asset_cost",
        "total_outstanding_loan",
        "total_disbursed_loan",
        "total_sanction_loan",
        "main_account_outstanding_loan",
        "sub_account_outstanding_loan",
    ]
    for col in log_cols:
        out[f"log1p_{col}"] = np.log1p(np.clip(out[col], a_min=0, a_max=None))

    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def cast_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cat_cols = [
        "branch_id",
        "supplier_id",
        "manufacturer_id",
        "area_id",
        "employee_code_id",
        "mobileno_flag",
        "idcard_flag",
        "Driving_flag",
        "passport_flag",
        "Credit_level",
        "employment_type",
    ]
    for col in cat_cols:
        if col in out.columns:
            out[col] = out[col].astype("Int64").astype("category")
    return out
