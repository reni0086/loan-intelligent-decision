import argparse
import json
import random
from datetime import date
from pathlib import Path

from pyspark.ml.fpm import FPGrowth
from pyspark.ml.recommendation import ALS
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# ---------------------------------------------------------------------------
# FP-Growth evaluation: mask values -> run FP-Growth repair -> compare
# ---------------------------------------------------------------------------
def _fp_evaluate(spark, df, target_col, cat_cols, sample_frac=0.2, seed=42):
    """Return (coverage, accuracy) by masking target_col values then repairing."""
    import pyspark.sql.types as T

    # Keep only rows where target is non-null and all antecedent cols are non-null.
    complete = df.filter(F.col(target_col).isNotNull())
    for c in cat_cols:
        if c != target_col:
            complete = complete.filter(F.col(c).isNotNull())

    total = complete.count()
    if total == 0:
        return 0.0, 0.0

    # Sample ~20% and mask their target.
    mask_rows = complete.sample(withReplacement=False, fraction=sample_frac, seed=seed)
    mask_ids = [row["customer_id"] for row in mask_rows.select("customer_id").collect()]
    if not mask_ids:
        return 0.0, 0.0

    # Build ground-truth map: {customer_id -> original_value}
    gt_map = {row["customer_id"]: row[target_col] for row in
              complete.filter(F.col("customer_id").isin(mask_ids)).select("customer_id", target_col).collect()}

    # Replace target with NULL for masked rows.
    masked = df.withColumn(
        target_col,
        F.when(F.col("customer_id").isin(mask_ids), F.lit(None)).otherwise(F.col(target_col)),
    )

    # --- Run FP-Growth repair on the masked data ---
    item_cols = cat_cols
    tokens = [
        F.concat(F.lit(f"{c}="), F.coalesce(F.col(c).cast("string"), F.lit("NULL")))
        for c in item_cols
    ]
    work = masked.select(
        "customer_id",
        F.array(*tokens).alias("items"),
        F.col(target_col).alias("_target"),
        *[F.col(c).alias(f"_ant_{c}") for c in cat_cols if c != target_col],
    ).filter(F.col("_target").isNotNull())

    model = FPGrowth(itemsCol="items", minSupport=0.05, minConfidence=0.6).fit(work)
    rules = model.associationRules
    rules.createOrReplaceTempView("ev_fp_rules")

    # Build rule lookup
    import re as _re
    lookup = {}
    rule_rows = (
        rules.filter(F.col("confidence") >= 0.6)
        .select("antecedent", "consequent", "confidence")
        .collect()
    )
    for row in rule_rows:
        cons_str = row["consequent"]
        conf = float(row["confidence"])
        m = _re.search(rf"{_re.escape(target_col)}=([^,)\]]+)", cons_str)
        if not m:
            continue
        cons_val_str = m.group(1).strip()
        try:
            cons_val = int(cons_val_str) if cons_val_str else None
        except ValueError:
            try:
                cons_val = float(cons_val_str)
            except ValueError:
                cons_val = cons_val_str
        ant_tuple = tuple(row["antecedent"])
        if ant_tuple not in lookup or conf > lookup[ant_tuple][1]:
            lookup[ant_tuple] = (cons_val, conf)

    # Apply UDF
    ant_cols_filtered = [c for c in cat_cols if c != target_col]
    col_indices = {c: i for i, c in enumerate(ant_cols_filtered)}

    def apply_rules_udf(*vals):
        for ant_tuple, (cons_val, conf) in lookup.items():
            match = True
            for col_name, col_val in zip(ant_cols_filtered, vals):
                if col_val is not None and ant_tuple[col_indices[col_name]] != str(col_val):
                    match = False
                    break
            if match:
                return (float(cons_val), round(conf, 4)) if cons_val is not None else (None, 0.0)
        return (None, 0.0)

    from pyspark.ml.functions import array_to_vector
    from pyspark.sql.types import DoubleType, StructType, StructField

    apply_fn = F.udf(apply_rules_udf, StructType([
        StructField("val", DoubleType(), True),
        StructField("conf", DoubleType(), True),
    ]))

    ant_refs = [F.col(f"_ant_{c}") for c in ant_cols_filtered]

    repaired_sample = (
        masked.filter(F.col("customer_id").isin(mask_ids))
        .withColumn("result", apply_fn(*ant_refs))
        .withColumn("repaired_target", F.col("result.val"))
        .withColumn("repaired_conf", F.col("result.conf"))
        .select("customer_id", "repaired_target", "repaired_conf")
    )

    # Compute metrics
    repaired_map = {
        row["customer_id"]: (row["repaired_target"], row["repaired_conf"])
        for row in repaired_sample.collect()
        if row["repaired_target"] is not None
    }

    covered = len(repaired_map)
    coverage = covered / len(mask_ids) if mask_ids else 0.0

    correct = sum(
        1 for cid in repaired_map
        if cid in gt_map and repaired_map[cid][0] == gt_map[cid]
    )
    accuracy = correct / covered if covered > 0 else 0.0

    return float(coverage), float(accuracy)


# ---------------------------------------------------------------------------
# ALS evaluation: mask numeric values -> run ALS repair -> compare
# ---------------------------------------------------------------------------
def _als_evaluate(spark, df, num_features, sample_frac=0.2, seed=42):
    """Return (coverage, rmse, mape) by masking numeric values then repairing."""
    features = num_features  # list of column names

    temp = df.select("customer_id", *[F.col(c).cast("double").alias(c) for c in features])

    # Keep only rows where all features are non-null.
    complete = temp
    for c in features:
        complete = complete.filter(F.col(c).isNotNull())

    total = complete.count()
    if total == 0:
        return 0.0, 0.0, 0.0

    # Sample and mask.
    sample_df = complete.sample(withReplacement=False, fraction=sample_frac, seed=seed)
    mask_ids = [row["customer_id"] for row in sample_df.select("customer_id").collect()]
    if not mask_ids:
        return 0.0, 0.0, 0.0

    # Ground truth
    gt_rows = {
        row["customer_id"]: {c: row[c] for c in features}
        for row in complete.filter(F.col("customer_id").isin(mask_ids)).collect()
    }

    # Replace features with 0 (cold-start) for masked rows.
    masked = temp.withColumn(
        "customer_id_int", F.col("customer_id").cast("int")
    )
    for c in features:
        masked = masked.withColumn(
            c,
            F.when(F.col("customer_id").isin(mask_ids), F.lit(0.0)).otherwise(F.col(c))
        )

    # Build melted interactions for ALS.
    melted = []
    for idx, c in enumerate(features):
        melted.append(
            masked.select(
                F.col("customer_id_int").alias("user"),
                F.lit(idx).alias("item"),
                F.col(c).alias("rating"),
            )
        )
    ratings = melted[0]
    for i in range(1, len(features)):
        ratings = ratings.unionByName(melted[i])

    als = ALS(
        userCol="user", itemCol="item", ratingCol="rating",
        rank=10, maxIter=8, regParam=0.1,
        coldStartStrategy="drop", nonnegative=False,
    )
    model = als.fit(ratings)

    # Compute predictions for masked users and all items.
    from pyspark.ml.functions import vector_to_array

    user_factors = (
        model.userFactors
        .withColumnRenamed("id", "user")
        .withColumn("user_vec_arr", vector_to_array("features"))
    )
    item_factors = (
        model.itemFactors
        .withColumnRenamed("id", "item")
        .withColumn("item_vec_arr", vector_to_array("features"))
        .orderBy("item")
    )

    cross = user_factors.select("user", "user_vec_arr").crossJoin(
        item_factors.select("item", "item_vec_arr")
    )

    def dot_product(u, v):
        return float(sum(x * y for x, y in zip(u, v)))

    dot_udf = F.udf(dot_product, "double")
    predictions = (
        cross.withColumn("rating_pred", dot_udf(F.col("user_vec_arr"), F.col("item_vec_arr")))
        .select("user", "item", "rating_pred")
    )

    # Build lookup (user, item) -> prediction
    pred_lookup = {
        (int(row["user"]), int(row["item"])): float(row["rating_pred"])
        for row in predictions.collect()
    }

    # Evaluate on masked rows.
    repaired_preds = {}
    for cid in mask_ids:
        user_int = cid
        for idx, c in enumerate(features):
            val = pred_lookup.get((user_int, idx))
            if val is not None:
                repaired_preds[(cid, c)] = val

    covered = len(repaired_preds)
    total_masked = len(mask_ids) * len(features)
    coverage = covered / total_masked if total_masked > 0 else 0.0

    se_sum = 0.0
    ape_sum = 0.0
    count = 0
    for (cid, c), pred_val in repaired_preds.items():
        gt_val = gt_rows.get(cid, {}).get(c)
        if gt_val is None:
            continue
        se_sum += (pred_val - gt_val) ** 2
        denom = abs(gt_val) if abs(gt_val) > 1e-6 else 1.0
        ape_sum += abs(pred_val - gt_val) / denom
        count += 1

    rmse = (se_sum / count) ** 0.5 if count > 0 else 0.0
    mape = ape_sum / count if count > 0 else 0.0

    return float(coverage), float(rmse), float(mape)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate FP/ALS repair quality against a controlled ground-truth experiment."
    )
    parser.add_argument("--source-table", default="loan_dwd.loan_cleaned")
    parser.add_argument(
        "--cat-features",
        default="employment_type,area_id,Credit_level,mobileno_flag,idcard_flag",
        help="Comma-separated categorical columns for FP-Growth evaluation",
    )
    parser.add_argument(
        "--num-features",
        default="credit_score,disbursed_amount,asset_cost,total_outstanding_loan,total_monthly_payment",
        help="Comma-separated numeric columns for ALS evaluation",
    )
    parser.add_argument(
        "--sample-frac",
        type=float,
        default=0.2,
        help="Fraction of complete rows to mask and evaluate (default 0.2)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-json", default="artifacts/spark_repair_metrics.json")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("evaluate_repair").enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        df = spark.table(args.source_table)
    except Exception:
        print(f"[evaluate_repair] Table {args.source_table} not found, using empty result.")
        metrics = {
            "metric_date": str(date.today()),
            "fp_coverage": 0.0, "fp_accuracy": 0.0,
            "als_coverage": 0.0, "als_rmse": 0.0, "als_mape": 0.0,
            "note": f"Table {args.source_table} not accessible",
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        spark.stop()
        return

    cat_cols = [c.strip() for c in args.cat_features.split(",")]
    num_cols = [c.strip() for c in args.num_features.split(",")]

    # FP-Growth evaluation
    target_col = "Credit_level"
    if target_col in cat_cols:
        fp_cov, fp_acc = _fp_evaluate(
            spark, df, target_col, cat_cols,
            sample_frac=args.sample_frac, seed=args.seed,
        )
    else:
        fp_cov, fp_acc = 0.0, 0.0

    # ALS evaluation
    als_cov, als_rmse, als_mape = _als_evaluate(
        spark, df, num_cols,
        sample_frac=args.sample_frac, seed=args.seed,
    )

    spark.sparkContext.setLogLevel("INFO")
    print(
        f"[evaluate_repair] FP-Growth: coverage={fp_cov:.4f} accuracy={fp_acc:.4f} | "
        f"ALS: coverage={als_cov:.4f} rmse={als_rmse:.4f} mape={als_mape:.4f}"
    )

    metrics = {
        "metric_date": str(date.today()),
        "fp_coverage": fp_cov,
        "fp_accuracy": fp_acc,
        "als_coverage": als_cov,
        "als_rmse": als_rmse,
        "als_mape": als_mape,
        "sample_frac": args.sample_frac,
        "seed": args.seed,
    }

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    spark.stop()


if __name__ == "__main__":
    main()
