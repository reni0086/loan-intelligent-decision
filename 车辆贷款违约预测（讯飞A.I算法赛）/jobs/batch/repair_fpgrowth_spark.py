import argparse
from typing import Dict, List, Tuple

from pyspark.ml.fpm import FPGrowth
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType


def _build_rule_lookup(
    rules_df,
    antecedent_cols: List[str],
    consequent_col: str,
) -> Dict[Tuple, Tuple]:
    """
    Build a lookup dict: (antecedent_value_tuple) -> (best_consequent_value, confidence).
    For each unique antecedent combination, keep the rule with the highest confidence.
    """
    from pyspark.sql.types import StructType, StructField, StringType, DoubleType

    rows = (
        rules_df.withColumn("ant_str", F.concat_ws("||", *[F.col(c) for c in antecedent_cols]))
        .filter(F.col("consequent").contains(consequent_col))
        .filter(F.col("confidence") >= 0.6)
        .select("ant_str", "consequent", "confidence")
        .distinct()
        .collect()
    )

    lookup = {}
    for row in rows:
        ant_str = row["ant_str"]
        consequent_str = row["consequent"]
        confidence = float(row["confidence"])

        import re
        match = re.search(rf"{re.escape(consequent_col)}=([^,)\]]+)", consequent_str)
        if not match:
            continue
        cons_val = match.group(1).strip()

        try:
            if "." in cons_val:
                cons_val_out = float(cons_val)
            else:
                cons_val_out = int(cons_val)
        except ValueError:
            cons_val_out = cons_val

        ant_tuple = tuple(ant_str.split("||")) if ant_str else ()
        if ant_tuple not in lookup or confidence > lookup[ant_tuple][1]:
            lookup[ant_tuple] = (cons_val_out, confidence)

    return lookup


def _apply_rules_udf(antecedent_cols: List[str], rule_lookup: Dict, default_val, default_conf):
    """
    Build a PySpark UDF that, for a given row's known antecedent values,
    looks up the best matching rule and returns (repaired_value, confidence).
    Falls back to (default_val, default_conf) when no rule matches.
    """
    col_indices = {c: i for i, c in enumerate(antecedent_cols)}

    def apply_rules(*values):
        for ant_tuple, (cons_val, conf) in rule_lookup.items():
            match = True
            for col_name, col_val in zip(antecedent_cols, values):
                idx = col_indices[col_name]
                if col_val is not None and ant_tuple[idx] != str(col_val):
                    match = False
                    break
            if match:
                return (cons_val, round(conf, 4))
        return (default_val, default_conf)

    return F.udf(apply_rules, DoubleType())


def main() -> None:
    parser = argparse.ArgumentParser(description="FP-Growth style categorical repair with Spark.")
    parser.add_argument("--source-table", default="loan_dwd.loan_cleaned")
    parser.add_argument("--output-table", default="loan_dwd.loan_repaired_fp")
    parser.add_argument(
        "--target-col",
        default="Credit_level",
        help="Categorical column to repair (must appear in item_cols)",
    )
    args = parser.parse_args()

    spark = SparkSession.builder.appName("repair_fpgrowth_spark").enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    df = spark.table(args.source_table)

    item_cols = ["employment_type", "area_id", "Credit_level", "mobileno_flag", "idcard_flag"]
    target_col = args.target_col

    assert target_col in item_cols, f"{target_col} must be in item_cols: {item_cols}"
    ant_cols = [c for c in item_cols if c != target_col]

    tokens = [F.concat(F.lit(f"{c}="), F.coalesce(F.col(c).cast("string"), F.lit("NULL"))) for c in item_cols]
    work = df.select(
        "customer_id",
        F.array(*tokens).alias("items"),
        F.col(target_col).alias("_target"),
        *[F.col(c).alias(f"_ant_{c}") for c in ant_cols],
    ).filter(F.col("_target").isNotNull())

    model = FPGrowth(itemsCol="items", minSupport=0.05, minConfidence=0.6).fit(work)
    rules = model.associationRules
    rules.createOrReplaceTempView("tmp_fp_rules")

    rule_lookup = _build_rule_lookup(
        rules,
        antecedent_cols=item_cols,
        consequent_col=target_col,
    )

    # Determine default from mode of target column
    mode_row = work.groupBy("_target").count().orderBy(F.desc("count")).first()
    default_val = mode_row["_target"] if mode_row else 2
    default_conf = 0.5

    apply_fn = _apply_rules_udf(ant_cols, rule_lookup, float(default_val), default_conf)

    ant_col_refs = [F.col(f"_ant_{c}") for c in ant_cols]
    repair_udf = apply_fn(*ant_col_refs)

    df_with_missing = df.withColumn("_is_null_target", F.col(target_col).isNull())
    null_count = df_with_missing.filter("_is_null_target").count()
    total_count = df_with_missing.count()
    spark.sparkContext.setLogLevel("INFO")

    if null_count > 0 and rule_lookup:
        repaired = df_with_missing.withColumn(
            "repaired_value",
            F.when(
                F.col("_is_null_target"),
                repair_udf,
            ).otherwise(F.struct(F.col(target_col).cast(DoubleType()), F.lit(1.0))),
        ).withColumn(
            "repaired_" + target_col,
            F.col("repaired_value").getField("0"),
        ).withColumn(
            "repair_confidence_" + target_col,
            F.col("repaired_value").getField("1"),
        ).drop("repaired_value", "_is_null_target")
    else:
        repaired = df_with_missing.withColumn(
            "repaired_" + target_col,
            F.col(target_col).cast(DoubleType()),
        ).withColumn(
            "repair_confidence_" + target_col,
            F.lit(1.0),
        ).drop("_is_null_target")

    covered = repaired.filter(
        F.col("repaired_" + target_col).isNotNull()
    ).count()
    print(
        f"[FP-Growth Repair] Target={target_col} | Total={total_count} | "
        f"Missing={null_count} | Rules found={len(rule_lookup)} | "
        f"Repaired={covered} | Coverage={null_count/total_count*100:.1f}%"
        if total_count > 0 else "No data"
    )

    spark.sql(f"DROP TABLE IF EXISTS {args.output_table}")
    repaired.write.mode("overwrite").saveAsTable(args.output_table)
    rules.write.mode("overwrite").saveAsTable("loan_ads.fp_growth_rules")

    spark.stop()
