#!/usr/bin/env bash
set -euo pipefail

SQOOP_VERSION="${SQOOP_VERSION:-1.4.7}"
SQOOP_INSTALL_DIR="${SQOOP_INSTALL_DIR:-/opt/sqoop}"

echo "[sqoop] installing Apache Sqoop ${SQOOP_VERSION}..."

cd /tmp

echo "[sqoop] download Sqoop..."
# Sqoop 1.4.7 稳定版，使用华为镜像或官方归档
wget -q "https://mirrors.huaweicloud.com/apache/sqoop/${SQOOP_VERSION}/sqoop-${SQOOP_VERSION}-bin.tar.gz" \
    -O "sqoop-${SQOOP_VERSION}-bin.tar.gz" 2>/dev/null || \
wget -q "https://archive.apache.org/dist/sqoop/${SQOOP_VERSION}/sqoop-${SQOOP_VERSION}-bin.tar.gz" \
    -O "sqoop-${SQOOP_VERSION}-bin.tar.gz"

echo "[sqoop] extract to ${SQOOP_INSTALL_DIR}..."
sudo mkdir -p "${SQOOP_INSTALL_DIR}"
sudo tar -xzf "sqoop-${SQOOP_VERSION}-bin.tar.gz" -C "${SQOOP_INSTALL_DIR}"
sudo ln -sfn "${SQOOP_INSTALL_DIR}/sqoop-${SQOOP_VERSION}-bin" "${SQOOP_INSTALL_DIR}/current"

echo "[sqoop] copy MySQL JDBC driver..."
if [[ -f /usr/share/java/mysql-connector-j.jar ]]; then
    sudo cp /usr/share/java/mysql-connector-j.jar "${SQOOP_INSTALL_DIR}/current/lib/"
elif [[ -f /usr/share/java/mysql-connector-java.jar ]]; then
    sudo cp /usr/share/java/mysql-connector-java.jar "${SQOOP_INSTALL_DIR}/current/lib/"
fi

echo "[sqoop] copy PostgreSQL JDBC driver (optional)..."
# PostgreSQL驱动（可选，用于其他数据库同步）
wget -q "https://jdbc.postgresql.org/download/postgresql-42.6.0.jar" \
    -O "postgresql-42.6.0.jar" 2>/dev/null && \
    sudo cp "postgresql-42.6.0.jar" "${SQOOP_INSTALL_DIR}/current/lib/" || true

echo "[sqoop] configure Sqoop environment..."
cat <<'EOF' | sudo tee "${SQOOP_INSTALL_DIR}/current/conf/sqoop-env.sh" >/dev/null
# Sqoop 环境配置文件
export SQOOP_HOME=/opt/sqoop/current
export HADOOP_HOME=/opt/bigdata/hadoop
export HIVE_HOME=/opt/bigdata/hive
export HBASE_HOME=/opt/bigdata/hbase
export ZOOKEEPER_HOME=/opt/bigdata/zookeeper
export HCAT_HOME=/opt/bigdata/hive/hcatalog
export ACCUMULO_HOME=/opt/bigdata/accumulo
export ACCUMULO_TRACE_HOME=/opt/bigdata/accumulo/trace
export PATH=$PATH:$SQOOP_HOME/bin:$HADOOP_HOME/bin:$HIVE_HOME/bin
EOF

echo "[sqoop] configure sqoop-site.xml (disable doc generation for faster startup)..."
cat <<'EOF' | sudo tee "${SQOOP_INSTALL_DIR}/current/conf/sqoop-site.xml" >/dev/null
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <property>
        <name>sqoop.avro.data.skip</name>
        <value>true</value>
    </property>
    <property>
        <name>sqoop.csv.null.postfix</name>
        <value>__NULL__</value>
    </property>
</configuration>
EOF

echo "[sqoop] copy Hadoop & Hive libs to Sqoop..."
if [[ -d /opt/bigdata/hadoop/share/hadoop/common ]]; then
    for jar in /opt/bigdata/hadoop/share/hadoop/common/lib/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${SQOOP_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
    for jar in /opt/bigdata/hadoop/share/hadoop/hdfs/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${SQOOP_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
    for jar in /opt/bigdata/hadoop/share/hadoop/mapreduce/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${SQOOP_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
fi

if [[ -d /opt/bigdata/hive/lib ]]; then
    for jar in /opt/bigdata/hive/lib/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${SQOOP_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
fi

echo "[sqoop] create symbolic link..."
sudo ln -sf "${SQOOP_INSTALL_DIR}/current/bin/sqoop" /usr/local/bin/sqoop

echo "[sqoop] append env vars..."
cat <<EOF' | sudo tee /etc/profile.d/loan-sqoop.sh >/dev/null
export SQOOP_HOME=/opt/sqoop/current
export PATH=\$PATH:\$SQOOP_HOME/bin
EOF

echo "[sqoop] verify:"
sqoop version 2>&1 | head -5

echo "[sqoop] done."
echo "  Version: $(sqoop version 2>&1 | grep 'Sqoop' | head -1)"
echo "  Home: ${SQOOP_INSTALL_DIR}/current"
echo "  Test: sqoop list-databases --connect jdbc:mysql://localhost:3306/loan_ods --username loan_user --password 'loan_pass_123'"
