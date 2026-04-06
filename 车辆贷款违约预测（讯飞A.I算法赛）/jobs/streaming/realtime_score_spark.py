import argparse
from pathlib import Path

import joblib
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StructField,
    StructType,
)

from features_v3 import add_features


def _schema() -> StructType:
    return StructType(
        [
            StructField("customer_id", LongType(), True),
            StructField("main_account_loan_no", DoubleType(), True),
            StructField("main_account_active_loan_no", DoubleType(), True),
            StructField("main_account_overdue_no", DoubleType(), True),
            StructField("main_account_outstanding_loan", DoubleType(), True),
            StructField("main_account_sanction_loan", DoubleType(), True),
            StructField("main_account_disbursed_loan", DoubleType(), True),
            StructField("sub_account_loan_no", DoubleType(), True),
            StructField("sub_account_active_loan_no", DoubleType(), True),
            StructField("sub_account_overdue_no", DoubleType(), True),
            StructField("sub_account_outstanding_loan", DoubleType(), True),
            StructField("sub_account_sanction_loan", DoubleType(), True),
            StructField("sub_account_disbursed_loan", DoubleType(), True),
            StructField("disbursed_amount", DoubleType(), True),
            StructField("asset_cost", DoubleType(), True),
            StructField("branch_id", IntegerType(), True),
            StructField("supplier_id", IntegerType(), True),
            StructField("manufacturer_id", IntegerType(), True),
            StructField("area_id", IntegerType(), True),
            StructField("employee_code_id", IntegerType(), True),
            StructField("mobileno_flag", IntegerType(), True),
            StructField("idcard_flag", IntegerType(), True),
            StructField("Driving_flag", IntegerType(), True),
            StructField("passport_flag", IntegerType(), True),
            StructField("credit_score", DoubleType(), True),
            StructField("main_account_monthly_payment", DoubleType(), True),
            StructField("sub_account_monthly_payment", DoubleType(), True),
            StructField("last_six_month_new_loan_no", DoubleType(), True),
            StructField("last_six_month_defaulted_no", DoubleType(), True),
            StructField("average_age", DoubleType(), True),
            StructField("credit_history", DoubleType(), True),
            StructField("enquirie_no", DoubleType(), True),
            StructField("loan_to_asset_ratio", DoubleType(), True),
            StructField("total_account_loan_no", DoubleType(), True),
            StructField("sub_account_inactive_loan_no", DoubleType(), True),
            StructField("total_inactive_loan_no", DoubleType(), True),
            StructField("main_account_inactive_loan_no", DoubleType(), True),
            StructField("total_overdue_no", DoubleType(), True),
            StructField("total_outstanding_loan", DoubleType(), True),
            StructField("total_sanction_loan", DoubleType(), True),
            StructField("total_disbursed_loan", DoubleType(), True),
            StructField("total_monthly_payment", DoubleType(), True),
            StructField("outstanding_disburse_ratio", DoubleType(), True),
            StructField("main_account_tenure", DoubleType(), True),
            StructField("sub_account_tenure", DoubleType(), True),
            StructField("disburse_to_sactioned_ratio", DoubleType(), True),
            StructField("active_to_inactive_act_ratio", DoubleType(), True),
            StructField("year_of_birth", IntegerType(), True),
            StructField("disbursed_date", IntegerType(), True),
            StructField("Credit_level", IntegerType(), True),
            StructField("employment_type", IntegerType(), True),
            StructField("age", IntegerType(), True),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Structured streaming scoring with XGBoost model.")
    parser.add_argument("--input-dir", default="/data_lake/raw/realtime_input")
    parser.add_argument("--checkpoint", default="/data_lake/model/ckpt/realtime_score")
    parser.add_argument("--output-dir", default="/data_lake/featured/realtime_scored")
    parser.add_argument("--model-path", default="artifacts/default_model.joblib")
    args = parser.parse_args()

    bundle = joblib.load(Path(args.model_path))
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    spark = SparkSession.builder.appName("realtime_score_spark").getOrCreate()

    stream_df = (
        spark.readStream.option("header", True).schema(_schema()).csv(args.input_dir)
        .withColumn("event_time", F.current_timestamp())
    )

    def score_batch(batch_df, batch_id: int):
        if batch_df.rdd.isEmpty():
            return
        pdf = batch_df.toPandas()
        raw = pdf.copy()
        feat = add_features(raw).replace([float("inf"), float("-inf")], pd.NA)
        x = feat.reindex(columns=feature_cols).fillna(0)
        prob = model.predict_proba(x)[:, 1]
        pdf["default_probability"] = prob
        pdf["default_pred"] = (prob >= 0.5).astype(int)
        out = spark.createDataFrame(pdf[["customer_id", "default_probability", "default_pred", "event_time"]])
        out.write.mode("append").parquet(args.output_dir)

    query = (
        stream_df.writeStream
        .foreachBatch(score_batch)
        .option("checkpointLocation", args.checkpoint)
        .trigger(processingTime="20 seconds")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
