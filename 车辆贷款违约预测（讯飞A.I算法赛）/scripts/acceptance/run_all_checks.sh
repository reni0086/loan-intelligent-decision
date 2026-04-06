#!/usr/bin/env bash
set -euo pipefail

echo "[acceptance] check java/python/mysql/hadoop/spark/hive versions..."
java -version || true
python3 --version || true
mysql --version || true
hadoop version || true
spark-submit --version || true
hive --version || true

echo "[acceptance] check hdfs layout..."
hdfs dfs -ls /data_lake || true

echo "[acceptance] check mysql tables..."
mysql -uloan_user -ploan_pass_123 -e "USE loan_ods; SHOW TABLES;" || true
mysql -uloan_user -ploan_pass_123 -e "USE loan_rt; SHOW TABLES;" || true

echo "[acceptance] check flask api endpoints..."
curl -s "http://127.0.0.1:5000/health" || true
curl -s "http://127.0.0.1:5000/stats/overview" || true
curl -s "http://127.0.0.1:5000/stats/risk_daily" || true

echo "[acceptance] done."
