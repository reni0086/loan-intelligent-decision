#!/usr/bin/env bash
set -euo pipefail

JAVA_PACKAGE="${JAVA_PACKAGE:-openjdk-8-jdk}"
HADOOP_VERSION="${HADOOP_VERSION:-3.3.6}"
SPARK_VERSION="${SPARK_VERSION:-3.5.1}"
HIVE_VERSION="${HIVE_VERSION:-3.1.3}"
INSTALL_DIR="${INSTALL_DIR:-/opt/bigdata}"

# 下载源：默认用国内镜像（华为云 Apache），避免直连 downloads.apache.org 极慢或卡住。
# 可改环境变量，例如：
#   APACHE_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/apache   # 清华
#   APACHE_MIRROR=https://downloads.apache.org                  # 官方（海外）
APACHE_MIRROR="${APACHE_MIRROR:-https://mirrors.huaweicloud.com/apache}"
# Hive 3.1.x 在官方主站已下架时用归档；华为镜像仍保留 hive-3.1.3，与 APACHE_MIRROR 同域即可
HIVE_USE_ARCHIVE="${HIVE_USE_ARCHIVE:-0}"

_hadoop_url() {
  echo "${APACHE_MIRROR}/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"
}
_spark_url() {
  echo "${APACHE_MIRROR}/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz"
}
_hive_url() {
  if [[ "${HIVE_USE_ARCHIVE}" == "1" ]] || [[ "${APACHE_MIRROR}" == *"downloads.apache.org"* ]]; then
    echo "https://archive.apache.org/dist/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz"
  else
    echo "${APACHE_MIRROR}/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz"
  fi
}

echo "[bigdata] Apache 下载镜像: ${APACHE_MIRROR}"

echo "[bigdata] install java..."
sudo apt-get update -y
sudo apt-get install -y "${JAVA_PACKAGE}"

echo "[bigdata] create install dir..."
sudo mkdir -p "${INSTALL_DIR}"
cd /tmp

echo "[bigdata] download hadoop... (~700MB，镜像慢可 Ctrl+C 后换 APACHE_MIRROR 重试)"
wget --continue --timeout=60 --tries=30 --show-progress -O "hadoop-${HADOOP_VERSION}.tar.gz" \
  "$(_hadoop_url)"
sudo tar -xzf "hadoop-${HADOOP_VERSION}.tar.gz" -C "${INSTALL_DIR}"
sudo ln -sfn "${INSTALL_DIR}/hadoop-${HADOOP_VERSION}" "${INSTALL_DIR}/hadoop"

echo "[bigdata] download spark... (~380MB)"
wget --continue --timeout=60 --tries=30 --show-progress -O "spark-${SPARK_VERSION}-bin-hadoop3.tgz" \
  "$(_spark_url)"
sudo tar -xzf "spark-${SPARK_VERSION}-bin-hadoop3.tgz" -C "${INSTALL_DIR}"
sudo ln -sfn "${INSTALL_DIR}/spark-${SPARK_VERSION}-bin-hadoop3" "${INSTALL_DIR}/spark"

echo "[bigdata] download hive... (~310MB)"
wget --continue --timeout=60 --tries=30 --show-progress -O "apache-hive-${HIVE_VERSION}-bin.tar.gz" \
  "$(_hive_url)"
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
