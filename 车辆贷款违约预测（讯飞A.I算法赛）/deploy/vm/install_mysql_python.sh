#!/usr/bin/env bash
set -euo pipefail

# root 最终密码（与建库、后续脚本一致）。例：export MYSQL_ROOT_PASSWORD='123456' sudo -E ./install_mysql_python.sh
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root123}"
# 若 root 当前密码与上面不同，只在这一步填写当前密码；不设则与 MYSQL_ROOT_PASSWORD 相同
MYSQL_ROOT_CURRENT="${MYSQL_ROOT_CURRENT:-${MYSQL_ROOT_PASSWORD}}"
PYTHON_VENV_DIR="${PYTHON_VENV_DIR:-/opt/loan-venv}"

_mysql_connect_test() {
  sudo mysql -e "SELECT 1" &>/dev/null
}

_mysql_with_password_test() {
  mysql -uroot -p"${MYSQL_ROOT_CURRENT}" -e "SELECT 1" &>/dev/null
}

echo "[mysql-python] install mysql server..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server

echo "[mysql-python] configure mysql root password..."
if _mysql_connect_test; then
  # sudo mysql 可用（可能是 auth_socket 认证），通过 unix_socket 方式改密
  sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH auth_socket; FLUSH PRIVILEGES;"
  sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}'; FLUSH PRIVILEGES;"
elif _mysql_with_password_test; then
  mysql -uroot -p"${MYSQL_ROOT_CURRENT}" -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}'; FLUSH PRIVILEGES;"
else
  echo "[mysql-python] ERROR: 无法连接 MySQL（sudo mysql 与 mysql -uroot -p 均失败）。" >&2
  echo "[mysql-python] 请设置当前 root 密码后重试，例如：" >&2
  echo "  export MYSQL_ROOT_PASSWORD='123456'" >&2
  echo "  export MYSQL_ROOT_CURRENT='你当前的root密码'   # 若与上一行不同" >&2
  echo "  sudo -E ./install_mysql_python.sh" >&2
  exit 1
fi

echo "[mysql-python] create databases and user..."
mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
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
