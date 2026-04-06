#!/usr/bin/env python3
"""Spark Structured Streaming — Kafka Source (lending_application topic → Score → Parquet + MySQL).

This is the core Kafka-mode streaming job invoked by run_streaming.sh --mode kafka.

Pipeline:
  Kafka (lending_application)
      ↓
  Spark Structured Streaming  [read from Kafka, parse JSON, score]
      ↓
  ┣━ HDFS Parquet  → /data_lake/featured/realtime_kafka_scored/
  ┗━ MySQL (loan_rt.realtime_decisions)

Usage (via run_streaming.sh):
  ./jobs/streaming/run_streaming.sh --mode kafka

Or directly:
  spark-submit \
      --packages org.apache.spark:spark-sql-kafka-0.10_2.12:3.5.1 \
      --jars /opt/bigdata/jdbc/mysql-connector-j.jar \
      jobs/streaming/realtime_kafka_stream.py \
          --kafka-brokers localhost:9092 \
          --kafka-topic lending_application \
          --model-path artifacts/default_model.joblib \
          --output-parquet /data_lake/featured/realtime_kafka_scored \
          --checkpoint /data_lake/model/ckpt/kafka_stream_ckpt \
          --trigger-interval "5 seconds" \
          --enable-mysql-sink \
          --mysql-url "jdbc:mysql://127.0.0.1:3306/loan_rt?useSSL=false&serverTimezone=UTC" \
          --mysql-user loan_user \
          --mysql-password loan_pass_123
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kafka_stream")

# =============================================================================
#  Feature engineering (mirrors features_v3.add_features for Spark DataFrames)
# =============================================================================

FEATURE_COLS_DEFAULT = [
    "ltv_ratio", "overdue_rate_total", "overdue_rate_main",
    "total_monthly_payment", "total_disbursed_loan", "total_outstanding_loan",
    "credit_score", "age", "disbursed_amount",
    "main_account_active_loan_no", "main_account_overdue_no",
    "total_overdue_no", "total_account_loan_no",
    "main_account_monthly_payment", "total_sanction_loan",
    "sub_account_loan_no", "enquirie_no",
]


def _safe_div(spark, a_col: str, b_col: str, default: float = 0.0) -> F.Column:
    return F.when(F.col(b_col).isNull() | (F.col(b_col) == 0), default) \
             .otherwise(F.col(a_col) / F.col(b_col))


def add_spark_features(df: F.DataFrame) -> F.DataFrame:
    """Add engineered features on a Spark DataFrame (mirrors features_v3.py)."""
    out = df \
        .withColumn("ltv_ratio",
                    _safe_div(spark, "disbursed_amount", "asset_cost")) \
        .withColumn("overdue_rate_total",
                    _safe_div(spark, "total_overdue_no",
                              F.col("total_account_loan_no") + 1)) \
        .withColumn("overdue_rate_main",
                    _safe_div(spark, "main_account_overdue_no",
                              F.col("main_account_loan_no") + 1)) \
        .withColumn("loan_asset_gap", F.col("asset_cost") - F.col("disbursed_amount")) \
        .withColumn("enquirie_no",
                    F.coalesce(F.col("enquirie_no"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("credit_score",
                    F.coalesce(F.col("credit_score"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("age", F.coalesce(F.col("age"), F.lit(30)).cast(IntegerType())) \
        .withColumn("disbursed_amount",
                    F.coalesce(F.col("disbursed_amount"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_monthly_payment",
                    F.coalesce(F.col("total_monthly_payment"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_disbursed_loan",
                    F.coalesce(F.col("total_disbursed_loan"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_outstanding_loan",
                    F.coalesce(F.col("total_outstanding_loan"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_overdue_no",
                    F.coalesce(F.col("total_overdue_no"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_account_loan_no",
                    F.coalesce(F.col("total_account_loan_no"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("total_sanction_loan",
                    F.coalesce(F.col("total_sanction_loan"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("main_account_monthly_payment",
                    F.coalesce(F.col("main_account_monthly_payment"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("main_account_active_loan_no",
                    F.coalesce(F.col("main_account_active_loan_no"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("main_account_overdue_no",
                    F.coalesce(F.col("main_account_overdue_no"), F.lit(0.0)).cast(DoubleType())) \
        .withColumn("sub_account_loan_no",
                    F.coalesce(F.col("sub_account_loan_no"), F.lit(0.0)).cast(DoubleType()))

    return out


def get_model_bundle(model_path: str) -> dict:
    """Load the XGBoost model bundle from disk."""
    p = Path(model_path)
    if not p.exists():
        raise FileNotFoundError(f"Model not found: {model_path}. "
                                "Run 'python run_decision_suite.py' first.")
    return joblib.load(p)


def score_batch(pdf: pd.DataFrame, model) -> pd.DataFrame:
    """Score a pandas DataFrame batch; called on each Spark partition."""
    try:
        bundle = get_model_bundle("")
    except Exception:
        pass

    result = pdf.copy()

    # Align feature columns
    feat_cols = [c for c in FEATURE_COLS_DEFAULT if c in result.columns]
    x = result[feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    proba = model.predict_proba(x)[:, 1]
    result["default_probability"] = proba
    result["default_pred"] = (proba >= 0.5).astype(int)
    return result[["customer_id", "default_probability", "default_pred"]]


# =============================================================================
#  Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spark Structured Streaming: Kafka → Score → Parquet + MySQL",
    )
    parser.add_argument("--kafka-brokers", default="localhost:9092",
                        help="Kafka bootstrap servers")
    parser.add_argument("--kafka-topic", default="lending_application",
                        help="Kafka topic to read from")
    parser.add_argument("--kafka-group", default="loan_spark_stream_group",
                        help="Kafka consumer group")
    parser.add_argument("--starting-offsets", default="latest",
                        help="startingOffsets: 'latest' or 'earliest'")
    parser.add_argument("--fail-on-data-loss", default="false",
                        help="failOnDataLoss for Kafka source")
    parser.add_argument("--model-path", required=True,
                        help="Path to default_model.joblib")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Default probability threshold for classification")
    parser.add_argument("--output-parquet", required=True,
                        help="HDFS/S3 path for scored Parquet output")
    parser.add_argument("--checkpoint", required=True,
                        help="Spark Structured Streaming checkpoint directory")
    parser.add_argument("--trigger-interval", default="5 seconds",
                        help="Micro-batch trigger interval")
    parser.add_argument("--enable-mysql-sink", action="store_true",
                        help="Also write to MySQL (loan_rt.realtime_decisions)")
    parser.add_argument("--mysql-url",
                        default="jdbc:mysql://127.0.0.1:3306/loan_rt?useSSL=false&serverTimezone=UTC",
                        help="MySQL JDBC URL")
    parser.add_argument("--mysql-user", default="loan_user")
    parser.add_argument("--mysql-password", default="loan_pass_123")
    args = parser.parse_args()

    # Load model once for broadcasting
    model_bundle = get_model_bundle(args.model_path)
    model = model_bundle["model"]
    feature_cols = model_bundle.get("feature_cols", FEATURE_COLS_DEFAULT)
    logger.info("Model loaded: %s, features: %d",
                args.model_path, len(feature_cols))

    # Build Spark session with Kafka support
    spark = (
        SparkSession.builder
        .appName("kafka_loan_scoring_stream")
        .config("spark.sql.streaming.checkpointLocation", args.checkpoint)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.streaming.backpressure.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # Kafka JSON payload schema
    kafka_schema = StructType([
        StructField("customer_id", LongType(), True),
        StructField("disbursed_amount", DoubleType(), True),
        StructField("asset_cost", DoubleType(), True),
        StructField("credit_score", DoubleType(), True),
        StructField("age", IntegerType(), True),
        StructField("total_monthly_payment", DoubleType(), True),
        StructField("total_disbursed_loan", DoubleType(), True),
        StructField("total_outstanding_loan", DoubleType(), True),
        StructField("total_overdue_no", DoubleType(), True),
        StructField("total_account_loan_no", DoubleType(), True),
        StructField("total_sanction_loan", DoubleType(), True),
        StructField("main_account_active_loan_no", DoubleType(), True),
        StructField("main_account_overdue_no", DoubleType(), True),
        StructField("main_account_monthly_payment", DoubleType(), True),
        StructField("sub_account_loan_no", DoubleType(), True),
        StructField("enquirie_no", DoubleType(), True),
        StructField("area_id", IntegerType(), True),
        StructField("employment_type", IntegerType(), True),
        # Kafka metadata fields (injected by producer)
        StructField("_topic", StringType(), True),
        StructField("_produced_at", StringType(), True),
        StructField("_source", StringType(), True),
        # Fallback: raw JSON string (when parsing fails)
        StructField("raw_body", StringType(), True),
    ])

    # Read from Kafka
    raw_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", args.kafka_brokers)
        .option("subscribe", args.kafka_topic)
        .option("startingOffsets", args.starting_offsets)
        .option("failOnDataLoss", args.fail_on_data_loss)
        .option("kafkaConsumer.pollTimeoutMs", "512")
        .load()
    )

    # Parse JSON payload from Kafka value column
    parsed_df = raw_df.select(
        F.col("key").cast("string").alias("kafka_key"),
        F.col("partition").cast("int").alias("kafka_partition"),
        F.col("offset").cast("long").alias("kafka_offset"),
        F.col("timestamp").cast(TimestampType()).alias("kafka_event_time"),
        F.from_json(F.col("value").cast("string"), kafka_schema).alias("payload"),
    ).select("kafka_key", "kafka_partition", "kafka_offset", "kafka_event_time", "payload.*")

    # Filter to real loan records (exclude raw_body-only / heartbeat rows)
    loan_df = parsed_df.filter(
        F.col("customer_id").isNotNull() & F.col("disbursed_amount").isNotNull()
    )

    # Feature engineering
    featured_df = add_spark_features(loan_df)

    # Score using broadcast model via pandas UDF
    from pyspark.sql.types import StructType as S, StructField as F2, DoubleType as D, IntegerType as I

    score_schema = S([
        F2("customer_id", LongType(), True),
        F2("default_probability", D(), True),
        F2("default_pred", I(), True),
    ])

    bc_model = spark.sparkContext.broadcast(model)

    @F.pandas_udf(score_schema, F.PandasUDFType.GROUPED_MAP)
    def score_udf(pdf: pd.DataFrame) -> pd.DataFrame:
        model_obj = bc_model.value
        feat_cols = [c for c in FEATURE_COLS_DEFAULT if c in pdf.columns]
        x = pdf[feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        proba = model_obj.predict_proba(x)[:, 1]
        return pd.DataFrame({
            "customer_id": pdf["customer_id"],
            "default_probability": proba,
            "default_pred": (proba >= args.threshold).astype(int),
        })

    scored_df = featured_df.groupBy("customer_id").apply(score_udf)

    # Enrich scored result with Kafka metadata
    output_df = (
        scored_df
        .join(parsed_df.select("customer_id", "kafka_partition", "kafka_offset",
                               "kafka_event_time", "area_id", "disbursed_amount"),
              on="customer_id", how="left")
        .withColumn("scored_at", F.current_timestamp())
        .withColumn("kafka_topic", F.lit(args.kafka_topic))
        .withColumn("source", F.lit("spark_kafka_stream"))
        .withColumn("dt", F.date_format(F.current_date(), "yyyyMMdd"))
    )

    # ---- Sink 1: HDFS Parquet ----
    query_parquet = (
        output_df
        .writeStream
        .format("parquet")
        .option("path", args.output_parquet)
        .option("checkpointLocation", f"{args.checkpoint}/parquet")
        .trigger(processingTime=args.trigger_interval)
        .partitionBy("dt")
        .outputMode("append")
        .start()
    )
    logger.info("Parquet sink started: %s", args.output_parquet)

    # ---- Sink 2: MySQL ----
    if args.enable_mysql_sink:
        def write_mysql_batch(batch_df, batch_id: int):
            if batch_df.head(1).isEmpty():
                return
            try:
                batch_df = (
                    batch_df
                    .withColumn("fraud_probability",
                                F.col("default_probability") * F.lit(0.3))
                    .withColumn("fraud_pred",
                                (F.col("default_probability") > F.lit(0.8)).cast("int"))
                    .withColumn("predicted_limit",
                                F.lit(20000.0)
                                + (F.lit(1.0) - F.col("default_probability"))
                                * F.lit(30000.0))
                    .withColumn("credit_score",
                                F.lit(600) - F.col("default_probability") * F.lit(50))
                    .withColumn("decision_at", F.current_timestamp())
                    .withColumn("created_at", F.current_timestamp())
                )
                batch_df.write \
                    .jdbc(url=args.mysql_url,
                          table="realtime_decisions",
                          mode="append",
                          properties={
                              "user": args.mysql_user,
                              "password": args.mysql_password,
                              "driver": "com.mysql.jdbc.Driver",
                              "batchsize": "2000",
                          })
                logger.info("MySQL batch %d written (%d rows)",
                            batch_id, batch_df.count())
            except Exception as e:
                logger.error("MySQL write error in batch %d: %s", batch_id, e)

        query_mysql = (
            output_df.writeStream
            .foreachBatch(write_mysql_batch)
            .option("checkpointLocation", f"{args.checkpoint}/mysql")
            .trigger(processingTime=args.trigger_interval)
            .outputMode("append")
            .start()
        )
        logger.info("MySQL sink started: %s", args.mysql_url)

    # Wait for termination
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
