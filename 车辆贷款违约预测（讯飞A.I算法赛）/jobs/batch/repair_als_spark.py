import argparse
from pathlib import Path

from pyspark.ml.recommendation import ALS
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main() -> None:
    parser = argparse.ArgumentParser(description="ALS style numeric repair with Spark.")
    parser.add_argument("--source-table", default="loan_dwd.loan_repaired_fp")
    parser.add_argument("--output-table", default="loan_dwd.loan_repaired_als")
    parser.add_argument(
        "--features",
        default="credit_score,disbursed_amount,asset_cost,total_outstanding_loan,total_monthly_payment",
        help="Comma-separated numeric feature columns to repair",
    )
    parser.add_argument("--rank", type=int, default=10)
    parser.add_argument("--max-iter", type=int, default=8)
    parser.add_argument("--reg-param", type=float, default=0.1)
    args = parser.parse_args()

    spark = SparkSession.builder.appName("repair_als_spark").enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    df = spark.table(args.source_table)

    features = [f.strip() for f in args.features.split(",")]
    num_features = len(features)

    temp = df.select("customer_id", *[F.col(c).cast("double").alias(c) for c in features])
    for c in features:
        temp = temp.withColumn(c, F.coalesce(F.col(c), F.lit(0.0)))

    # Build user-item-rating interaction matrix.
    melted = []
    for idx, c in enumerate(features):
        melted.append(
            temp.select(
                F.col("customer_id").cast("int").alias("user"),
                F.lit(idx).alias("item"),
                F.col(c).alias("rating"),
            )
        )
    ratings = melted[0]
    for i in range(1, num_features):
        ratings = ratings.unionByName(melted[i])

    als = ALS(
        userCol="user",
        itemCol="item",
        ratingCol="rating",
        rank=args.rank,
        maxIter=args.max_iter,
        regParam=args.reg_param,
        coldStartStrategy="drop",
        nonnegative=False,
    )
    model = als.fit(ratings)

    # Extract latent factors and compute full user-item prediction matrix.
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

    # Collect predictions as a dict {(user, item): value} and broadcast it.
    lookup = {
        (int(row["user"]), int(row["item"])): float(row["rating_pred"])
        for row in predictions.collect()
    }
    broadcast_lookup = spark.sparkContext.broadcast(lookup)

    # Add a permanent int column once.
    df = df.withColumn("_user_int", F.col("customer_id").cast("int"))

    repaired = df
    for idx, c in enumerate(features):
        orig_col = F.col(c)
        feature_idx = idx

        def get_pred(user_int, feature_idx=feature_idx):
            bl = broadcast_lookup.value
            return bl.get((int(user_int), int(feature_idx)), 0.0)

        get_pred_udf = F.udf(get_pred, "double")

        repaired = repaired.withColumn(
            f"als_pred_{idx}",
            get_pred_udf(F.col("_user_int")),
        )

    # Now build the final repaired columns in one pass.
    repair_exprs = []
    for idx, c in enumerate(features):
        orig_col = F.col(c)
        pred_col = F.col(f"als_pred_{idx}")
        repaired = repaired.withColumn(
            "repaired_" + c,
            F.when(orig_col.isNull() | (F.abs(orig_col) < 1e-9), pred_col).otherwise(orig_col),
        ).withColumn(
            "repair_confidence_" + c,
            F.when(orig_col.isNull() | (F.abs(orig_col) < 1e-9), F.lit(0.8)).otherwise(F.lit(1.0)),
        )
        repair_exprs.append(f"repaired_{c}")
        repaired = repaired.drop(f"als_pred_{idx}")

    repaired = repaired.drop("_user_int")

    # Log stats
    total = repaired.count()
    spark.sparkContext.setLogLevel("INFO")
    for c in features:
        missing = repaired.filter(F.col(c).isNull()).count()
        repaired_missing = repaired.filter(F.col("repaired_" + c).isNull()).count()
        print(
            f"[ALS Repair] Feature={c} | Total={total} | "
            f"Original missing={missing} | Remaining missing after repair={repaired_missing}"
        )

    spark.sql(f"DROP TABLE IF EXISTS {args.output_table}")
    repaired.write.mode("overwrite").saveAsTable(args.output_table)

    # Persist model metadata
    meta_path = Path("artifacts/als_model_meta.txt")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        f"rank={args.rank}\nmaxIter={args.max_iter}\nregParam={args.reg_param}\n"
        f"numFeatures={num_features}\nfeatures={','.join(features)}\n",
        encoding="utf-8",
    )

    broadcast_lookup.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
