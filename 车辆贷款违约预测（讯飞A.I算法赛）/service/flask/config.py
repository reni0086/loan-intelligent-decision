import os


class Settings:
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "loan_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "loan_pass_123")
    MYSQL_DB_ODS = os.getenv("MYSQL_DB_ODS", "loan_ods")
    MYSQL_DB_RT = os.getenv("MYSQL_DB_RT", "loan_rt")

    HIVE_HOST = os.getenv("HIVE_HOST", "127.0.0.1")
    HIVE_PORT = int(os.getenv("HIVE_PORT", "10000"))
    HIVE_USERNAME = os.getenv("HIVE_USERNAME", "hive")
    HIVE_DATABASE = os.getenv("HIVE_DATABASE", "loan_ads")

    MODEL_DIR = os.getenv("MODEL_DIR", "artifacts")
