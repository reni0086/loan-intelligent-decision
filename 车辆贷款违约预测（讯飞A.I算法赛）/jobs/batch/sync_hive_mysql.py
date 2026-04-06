import argparse
from datetime import datetime

from pyspark.sql import SparkSession


def get_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .enableHiveSupport()
        .getOrCreate()
    )


def upsert_hive_to_mysql(
    spark: SparkSession,
    mysql_url: str,
    mysql_user: str,
    mysql_password: str,
    dt: str,
) -> None:
    query = f"""
    SELECT
      customer_id,
      CAST(year_of_birth AS INT) AS year_of_birth,
      CAST(age AS INT) AS age,
      CAST(employment_type AS INT) AS employment_type,
      CAST(credit_score AS DOUBLE) AS credit_score,
      CAST(Credit_level AS INT) AS credit_level,
      CAST(mobileno_flag AS INT) AS mobileno_flag,
      CAST(idcard_flag AS INT) AS idcard_flag,
      CAST(Driving_flag AS INT) AS driving_flag,
      CAST(passport_flag AS INT) AS passport_flag
    FROM loan_ods.raw_loan_data
    WHERE dt = '{dt}'
    """
    profile_df = spark.sql(query)
    profile_df.write \
        .format("jdbc") \
        .option("url", mysql_url) \
        .option("dbtable", "loan_ods.customer_profile") \
        .option("user", mysql_user) \
        .option("password", mysql_password) \
        .option("driver", "com.mysql.cj.jdbc.Driver") \
        .mode("append") \
        .save()

    fact_query = f"""
    SELECT
      customer_id,
      CAST(disbursed_date AS STRING) AS disbursed_date,
      CAST(disbursed_amount AS DOUBLE) AS disbursed_amount,
      CAST(asset_cost AS DOUBLE) AS asset_cost,
      CAST(total_overdue_no AS DOUBLE) AS total_overdue_no,
      CAST(total_disbursed_loan AS DOUBLE) AS total_disbursed_loan,
      CAST(total_monthly_payment AS DOUBLE) AS total_monthly_payment,
      CAST(loan_default AS INT) AS loan_default
    FROM loan_ods.raw_loan_data
    WHERE dt = '{dt}'
    """
    loan_fact_df = spark.sql(fact_query)
    loan_fact_df.write \
        .format("jdbc") \
        .option("url", mysql_url) \
        .option("dbtable", "loan_ods.loan_fact") \
        .option("user", mysql_user) \
        .option("password", mysql_password) \
        .option("driver", "com.mysql.cj.jdbc.Driver") \
        .mode("append") \
        .save()


def sync_mysql_to_hive_ads(spark: SparkSession, mysql_url: str, mysql_user: str, mysql_password: str, dt: str) -> None:
    mysql_df = spark.read.format("jdbc") \
        .option("url", mysql_url) \
        .option("dbtable", "loan_ods.loan_fact") \
        .option("user", mysql_user) \
        .option("password", mysql_password) \
        .option("driver", "com.mysql.cj.jdbc.Driver") \
        .load()

    mysql_df.createOrReplaceTempView("tmp_mysql_loan_fact")
    ads = spark.sql(
        f"""
        SELECT
          '{dt}' AS dt,
          COUNT(1) AS total_customers,
          AVG(disbursed_amount) AS avg_disbursed_amount,
          AVG(CASE WHEN loan_default = 1 THEN 1.0 ELSE 0.0 END) AS default_rate
        FROM tmp_mysql_loan_fact
        """
    )

    credit = spark.sql(
        """
        SELECT AVG(credit_score) AS avg_credit_score
        FROM loan_ods.raw_loan_data
        """
    ).collect()[0]["avg_credit_score"]

    ads = ads.withColumn("avg_credit_score", ads["avg_disbursed_amount"] * 0 + float(credit or 0.0))
    ads.select("dt", "total_customers", "avg_credit_score", "default_rate", "avg_disbursed_amount") \
        .write.mode("append").insertInto("loan_ads.risk_daily_summary")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Hive and MySQL tables.")
    parser.add_argument("--dt", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--mysql-url", default="jdbc:mysql://127.0.0.1:3306?useSSL=false&serverTimezone=UTC")
    parser.add_argument("--mysql-user", default="loan_user")
    parser.add_argument("--mysql-password", default="loan_pass_123")
    args = parser.parse_args()

    spark = get_spark("sync_hive_mysql")
    upsert_hive_to_mysql(spark, args.mysql_url, args.mysql_user, args.mysql_password, args.dt)
    sync_mysql_to_hive_ads(spark, args.mysql_url, args.mysql_user, args.mysql_password, args.dt)
    spark.stop()


if __name__ == "__main__":
    main()
