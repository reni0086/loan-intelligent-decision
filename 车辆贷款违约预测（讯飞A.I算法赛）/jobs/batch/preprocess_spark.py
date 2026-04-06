import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main() -> None:
    parser = argparse.ArgumentParser(description="Spark preprocess for loan data.")
    parser.add_argument("--input-path", required=True, help="HDFS path to raw CSV")
    parser.add_argument("--output-table", default="loan_dwd.loan_cleaned")
    parser.add_argument("--output-path", default="/data_lake/cleaned")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("preprocess_spark").enableHiveSupport().getOrCreate()

    df = spark.read.option("header", True).option("inferSchema", True).csv(args.input_path)
    df = df.dropDuplicates(["customer_id", "disbursed_date"])
    df = df.withColumn("missing_count", sum(F.when(F.col(c).isNull(), 1).otherwise(0) for c in df.columns))
    df = df.filter((F.col("age").isNull()) | ((F.col("age") >= 18) & (F.col("age") <= 100)))
    df = df.filter((F.col("disbursed_amount").isNull()) | (F.col("disbursed_amount") > 0))

    df.write.mode("overwrite").parquet(args.output_path)
    spark.sql(f"DROP TABLE IF EXISTS {args.output_table}")
    spark.sql(
        f"""
        CREATE TABLE {args.output_table}
        STORED AS PARQUET
        LOCATION '{args.output_path}'
        AS SELECT * FROM parquet.`{args.output_path}`
        """
    )
    spark.stop()


if __name__ == "__main__":
    main()
