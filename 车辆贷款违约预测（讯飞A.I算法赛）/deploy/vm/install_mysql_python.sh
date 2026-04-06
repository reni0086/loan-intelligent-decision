#!/usr/bin/env bash
set -euo pipefail

MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root123}"
PYTHON_VENV_DIR="${PYTHON_VENV_DIR:-/opt/loan-venv}"

echo "[mysql-python] install mysql server..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server

echo "[mysql-python] configure mysql root password..."
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${MYSQL_ROOT_PASSWORD}'; FLUSH PRIVILEGES;"

echo "[mysql-python] create databases and user..."
sudo mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS loan_ods DEFAULT CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS loan_rt DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'loan_user'@'%' IDENTIFIED BY 'loan_pass_123';
GRANT ALL PRIVILEGES ON loan_ods.* TO 'loan_user'@'%';
GRANT ALL PRIVILEGES ON loan_rt.* TO 'loan_user'@'%';
FLUSH PRIVILEGES;
SQL

echo "[mysql-python] install python and venv..."
sudo apt-get install -y python3 python3-pip python3-venv
sudo python3 -m venv "${PYTHON_VENV_DIR}"
sudo "${PYTHON_VENV_DIR}/bin/pip" install --upgrade pip
sudo "${PYTHON_VENV_DIR}/bin/pip" install flask pandas numpy scikit-learn xgboost pymysql pyhive thrift thrift-sasl sasl pyspark

echo "[mysql-python] done."
