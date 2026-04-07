import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.auth import init_default_user
from src.config import ProjectConfig


def ensure_directories(cfg: ProjectConfig) -> None:
    for p in [
        cfg.data_lake_dir,
        cfg.raw_dir,
        cfg.cleaned_dir,
        cfg.featured_dir,
        cfg.model_dir,
        cfg.artifacts_dir,
        cfg.monitoring_dir,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def batch_ingest_files(cfg: ProjectConfig) -> dict:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_train = cfg.raw_dir / f"train_{ts}.csv"
    raw_test = cfg.raw_dir / f"test_{ts}.csv"
    shutil.copy2(cfg.train_csv, raw_train)
    shutil.copy2(cfg.test_csv, raw_test)
    return {"raw_train": str(raw_train), "raw_test": str(raw_test)}


def preprocess_clean_data(cfg: ProjectConfig) -> Path:
    df = pd.read_csv(cfg.train_csv)
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.drop_duplicates(subset=["customer_id"])
    cleaned_path = cfg.cleaned_dir / "train_cleaned.csv"
    df.to_csv(cleaned_path, index=False)
    return cleaned_path


def build_feature_snapshot(cfg: ProjectConfig, cleaned_path: Path) -> Path:
    df = pd.read_csv(cleaned_path)
    if "loan_default" in df.columns:
        target = df["loan_default"]
        df = df.drop(columns=["loan_default"])
    else:
        target = None

    # Lightweight feature snapshot for downstream modules.
    df["loan_asset_gap"] = df["asset_cost"] - df["disbursed_amount"]
    df["repay_pressure"] = df["total_monthly_payment"] / (df["total_disbursed_loan"].replace(0, np.nan) + 1e-6)
    df["overdue_ratio"] = df["total_overdue_no"] / (df["total_account_loan_no"].replace(0, np.nan) + 1e-6)
    if target is not None:
        df["loan_default"] = target

    featured_path = cfg.featured_dir / "train_featured.csv"
    df.to_csv(featured_path, index=False)
    return featured_path


def initialize_sqlite_schema(cfg: ProjectConfig) -> None:
    conn = sqlite3.connect(cfg.sqlite_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS customer_basic_info (
            customer_id INTEGER PRIMARY KEY,
            year_of_birth INTEGER,
            age INTEGER,
            employment_type INTEGER,
            mobileno_flag INTEGER,
            idcard_flag INTEGER,
            driving_flag INTEGER,
            passport_flag INTEGER,
            credit_score REAL,
            credit_level INTEGER
        );

        CREATE TABLE IF NOT EXISTS loan_history (
            customer_id INTEGER,
            disbursed_amount REAL,
            asset_cost REAL,
            branch_id INTEGER,
            supplier_id INTEGER,
            manufacturer_id INTEGER,
            area_id INTEGER,
            disbursed_date INTEGER,
            loan_to_asset_ratio REAL
        );

        CREATE TABLE IF NOT EXISTS account_behavior (
            customer_id INTEGER,
            total_account_loan_no REAL,
            total_inactive_loan_no REAL,
            total_overdue_no REAL,
            total_outstanding_loan REAL,
            total_sanction_loan REAL,
            total_disbursed_loan REAL,
            total_monthly_payment REAL
        );

        CREATE TABLE IF NOT EXISTS repayment_behavior (
            customer_id INTEGER,
            main_account_tenure REAL,
            sub_account_tenure REAL,
            outstanding_disburse_ratio REAL,
            disburse_to_sactioned_ratio REAL,
            active_to_inactive_act_ratio REAL,
            loan_default INTEGER
        );

        CREATE TABLE IF NOT EXISTS credit_bureau (
            customer_id INTEGER,
            credit_history REAL,
            enquirie_no REAL,
            last_six_month_new_loan_no REAL,
            last_six_month_defaulted_no REAL,
            average_age REAL
        );

        CREATE TABLE IF NOT EXISTS realtime_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            payload_json TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    # 初始化默认管理员账号（如果尚无用户）
    init_default_user(cfg)


def load_structured_tables(cfg: ProjectConfig, cleaned_path: Path) -> None:
    df = pd.read_csv(cleaned_path)
    conn = sqlite3.connect(cfg.sqlite_path)

    customer_cols = [
        "customer_id",
        "year_of_birth",
        "age",
        "employment_type",
        "mobileno_flag",
        "idcard_flag",
        "Driving_flag",
        "passport_flag",
        "credit_score",
        "Credit_level",
    ]
    customer_df = df[customer_cols].copy()
    customer_df = customer_df.rename(columns={"Driving_flag": "driving_flag", "Credit_level": "credit_level"})
    customer_df.to_sql("customer_basic_info", conn, if_exists="replace", index=False)

    loan_cols = [
        "customer_id",
        "disbursed_amount",
        "asset_cost",
        "branch_id",
        "supplier_id",
        "manufacturer_id",
        "area_id",
        "disbursed_date",
        "loan_to_asset_ratio",
    ]
    df[loan_cols].to_sql("loan_history", conn, if_exists="replace", index=False)

    account_cols = [
        "customer_id",
        "total_account_loan_no",
        "total_inactive_loan_no",
        "total_overdue_no",
        "total_outstanding_loan",
        "total_sanction_loan",
        "total_disbursed_loan",
        "total_monthly_payment",
    ]
    df[account_cols].to_sql("account_behavior", conn, if_exists="replace", index=False)

    repay_cols = [
        "customer_id",
        "main_account_tenure",
        "sub_account_tenure",
        "outstanding_disburse_ratio",
        "disburse_to_sactioned_ratio",
        "active_to_inactive_act_ratio",
        "loan_default",
    ]
    df[repay_cols].to_sql("repayment_behavior", conn, if_exists="replace", index=False)

    bureau_cols = [
        "customer_id",
        "credit_history",
        "enquirie_no",
        "last_six_month_new_loan_no",
        "last_six_month_defaulted_no",
        "average_age",
    ]
    df[bureau_cols].to_sql("credit_bureau", conn, if_exists="replace", index=False)

    conn.close()


def create_pseudo_realtime_queue(cfg: ProjectConfig, max_events: int = 2000) -> Path:
    df = pd.read_csv(cfg.test_csv, nrows=max_events)
    queue_path = cfg.queue_path
    with queue_path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            payload = row.to_dict()
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return queue_path


def consume_queue_once(cfg: ProjectConfig, batch_size: int = 500) -> int:
    if not cfg.queue_path.exists():
        return 0

    with cfg.queue_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return 0

    consume_lines = lines[:batch_size]
    remain_lines = lines[batch_size:]
    with cfg.queue_path.open("w", encoding="utf-8") as f:
        f.writelines(remain_lines)

    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for ln in consume_lines:
        payload = json.loads(ln)
        rows.append(
            {
                "customer_id": int(payload.get("customer_id", -1)),
                "payload_json": json.dumps(payload, ensure_ascii=False),
                "created_at": now,
            }
        )

    conn = sqlite3.connect(cfg.sqlite_path)
    pd.DataFrame(rows).to_sql("realtime_events", conn, if_exists="append", index=False)
    conn.close()
    return len(rows)


def generate_storage_report(cfg: ProjectConfig, extra: dict | None = None) -> Path:
    conn = sqlite3.connect(cfg.sqlite_path)
    counts = {}
    for table in [
        "customer_basic_info",
        "loan_history",
        "account_behavior",
        "repayment_behavior",
        "credit_bureau",
        "realtime_events",
    ]:
        try:
            c = pd.read_sql_query(f"SELECT COUNT(*) AS c FROM {table}", conn)["c"].iloc[0]
            counts[table] = int(c)
        except Exception:
            counts[table] = 0
    conn.close()

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_lake": {
            "raw_dir": str(cfg.raw_dir),
            "cleaned_dir": str(cfg.cleaned_dir),
            "featured_dir": str(cfg.featured_dir),
            "model_dir": str(cfg.model_dir),
        },
        "sqlite_path": str(cfg.sqlite_path),
        "table_counts": counts,
    }
    if extra:
        report["extra"] = extra

    out_path = cfg.artifacts_dir / "ingest_storage_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path

