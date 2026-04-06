#!/usr/bin/env bash
set -euo pipefail

CONNECTOR_VERSION="${CONNECTOR_VERSION:-8.0.33}"
INSTALL_DIR="${INSTALL_DIR:-/opt/bigdata}"
JDBC_DIR="${INSTALL_DIR}/jdbc"
SPARK_JARS_DIR="${INSTALL_DIR}/spark/jars"

echo "[jdbc] installing MySQL Connector/J ${CONNECTOR_VERSION}..."

sudo mkdir -p "${JDBC_DIR}"
cd /tmp

echo "[jdbc] download MySQL Connector/J..."
wget -q "https://downloads.mysql.com/archives/get/p/3/file/mysql-connector-j-${CONNECTOR_VERSION}.jar" \
    -O "mysql-connector-j-${CONNECTOR_VERSION}.jar" || \
wget -q "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/${CONNECTOR_VERSION}/mysql-connector-j-${CONNECTOR_VERSION}.jar" \
    -O "mysql-connector-j-${CONNECTOR_VERSION}.jar"

sudo cp "mysql-connector-j-${CONNECTOR_VERSION}.jar" "${JDBC_DIR}/"
sudo ln -sfn "${JDBC_DIR}/mysql-connector-j-${CONNECTOR_VERSION}.jar" "${JDBC_DIR}/mysql-connector-j.jar"

echo "[jdbc] copy to Spark jars..."
sudo cp "mysql-connector-j-${CONNECTOR_VERSION}.jar" "${SPARK_JARS_DIR}/"

echo "[jdbc] copy to Hadoop lib..."
sudo cp "mysql-connector-j-${CONNECTOR_VERSION}.jar" "${INSTALL_DIR}/hadoop/share/hadoop/common/"
sudo cp "mysql-connector-j-${CONNECTOR_VERSION}.jar" "${INSTALL_DIR}/hive/lib/"

echo "[jdbc] copy to common lib..."
sudo cp "mysql-connector-j-${CONNECTOR_VERSION}.jar" /usr/share/java/

echo "[jdbc] verify:"
ls -lh "${JDBC_DIR}/mysql-connector-j.jar"
ls -lh "${SPARK_JARS_DIR}/mysql-connector-j-${CONNECTOR_VERSION}.jar"

cat <<EOF | sudo tee /etc/profile.d/loan-jdbc.sh >/dev/null
export JDBC_JAR="${JDBC_DIR}/mysql-connector-j.jar"
export MYSQL_JDBC_URL="jdbc:mysql://localhost:3306"
EOF

echo "[jdbc] done. Add --jars ${JDBC_DIR}/mysql-connector-j.jar to spark-submit commands."
