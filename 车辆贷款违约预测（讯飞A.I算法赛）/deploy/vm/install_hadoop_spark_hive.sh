#!/usr/bin/env bash
set -euo pipefail

JAVA_PACKAGE="${JAVA_PACKAGE:-openjdk-8-jdk}"
HADOOP_VERSION="${HADOOP_VERSION:-3.3.6}"
SPARK_VERSION="${SPARK_VERSION:-3.5.1}"
HIVE_VERSION="${HIVE_VERSION:-3.1.3}"
INSTALL_DIR="${INSTALL_DIR:-/opt/bigdata}"

echo "[bigdata] install java..."
sudo apt-get update -y
sudo apt-get install -y "${JAVA_PACKAGE}"

echo "[bigdata] create install dir..."
sudo mkdir -p "${INSTALL_DIR}"
cd /tmp

echo "[bigdata] download hadoop..."
wget -q "https://downloads.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"
sudo tar -xzf "hadoop-${HADOOP_VERSION}.tar.gz" -C "${INSTALL_DIR}"
sudo ln -sfn "${INSTALL_DIR}/hadoop-${HADOOP_VERSION}" "${INSTALL_DIR}/hadoop"

echo "[bigdata] download spark..."
wget -q "https://downloads.apache.org/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz"
sudo tar -xzf "spark-${SPARK_VERSION}-bin-hadoop3.tgz" -C "${INSTALL_DIR}"
sudo ln -sfn "${INSTALL_DIR}/spark-${SPARK_VERSION}-bin-hadoop3" "${INSTALL_DIR}/spark"

echo "[bigdata] download hive..."
wget -q "https://downloads.apache.org/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz"
sudo tar -xzf "apache-hive-${HIVE_VERSION}-bin.tar.gz" -C "${INSTALL_DIR}"
sudo ln -sfn "${INSTALL_DIR}/apache-hive-${HIVE_VERSION}-bin" "${INSTALL_DIR}/hive"

echo "[bigdata] append env vars..."
cat <<'EOF' | sudo tee /etc/profile.d/loan-bigdata.sh >/dev/null
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
export HADOOP_HOME=/opt/bigdata/hadoop
export SPARK_HOME=/opt/bigdata/spark
export HIVE_HOME=/opt/bigdata/hive
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$SPARK_HOME/bin:$HIVE_HOME/bin
EOF

echo "[bigdata] done. restart shell or source /etc/profile.d/loan-bigdata.sh"
