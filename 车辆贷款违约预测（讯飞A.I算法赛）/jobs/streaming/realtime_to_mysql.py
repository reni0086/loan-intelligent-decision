import argparse

from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream scored parquet to MySQL realtime table.")
    parser.add_argument("--input-dir", default="/data_lake/featured/realtime_scored")
    parser.add_argument("--checkpoint", default="/data_lake/model/ckpt/realtime_mysql")
    parser.add_argument("--mysql-url", default="jdbc:mysql://127.0.0.1:3306/loan_rt?useSSL=false&serverTimezone=UTC")
    parser.add_argument("--mysql-user", default="loan_user")
    parser.add_argument("--mysql-password", default="loan_pass_123")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("realtime_to_mysql").getOrCreate()

    schema = "customer_id long, default_probability double, default_pred int, event_time timestamp"
    stream_df = spark.readStream.schema(schema).parquet(args.input_dir)

    def write_mysql(batch_df, batch_id: int):
        if batch_df.rdd.isEmpty():
            return
        out = (
            batch_df
            .withColumnRenamed("event_time", "created_at")
            .withColumn("fraud_probability", batch_df.default_probability * 0.3)
            .withColumn("fraud_pred", (batch_df.default_probability > 0.8).cast("int"))
            .withColumn("predicted_limit", 20000.0 + (1 - batch_df.default_probability) * 30000.0)
            .withColumn("credit_score", 600 - 50 * batch_df.default_probability)
        )
        out.select(
            "customer_id",
            "default_probability",
            "default_pred",
            "fraud_probability",
            "fraud_pred",
            "predicted_limit",
            "credit_score",
            "created_at",
        ).write.format("jdbc")             .option("url", args.mysql_url)             .option("dbtable", "realtime_decisions")             .option("user", args.mysql_user)             .option("password", args.mysql_password)             .option("driver", "com.mysql.cj.jdbc.Driver")             .mode("append")             .save()

    query = (
        stream_df.writeStream
        .foreachBatch(write_mysql)
        .option("checkpointLocation", args.checkpoint)
        .trigger(processingTime="20 seconds")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
