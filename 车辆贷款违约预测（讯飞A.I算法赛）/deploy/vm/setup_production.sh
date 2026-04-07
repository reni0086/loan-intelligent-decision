#!/usr/bin/env bash
set -euo pipefail
# ============================================================
#  一键生产部署脚本 — 贷款客户信息修复与智能决策系统
# ============================================================
# 支持 Ubuntu 22.04（其他 Debian 系亦可）
# 耗时约 30~60 分钟（取决于网络）
#
# 用法（以 root 身份在 VM 上运行）：
#   chmod +x deploy/vm/setup_production.sh
#   sudo ./deploy/vm/setup_production.sh
#
# 或分步执行各脚本（精细控制）：
#   sudo ./deploy/vm/bootstrap.sh
#   sudo ./deploy/vm/install_hadoop_spark_hive.sh
#   sudo ./deploy/vm/install_mysql_python.sh
#   sudo ./deploy/vm/install_mysql_jdbc.sh
#   sudo ./deploy/vm/install_kafka.sh
#   sudo ./deploy/vm/install_flume.sh
#   sudo ./deploy/vm/init_hdfs_layout.sh
# ============================================================

set -e

# ---------- 颜色 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${SCRIPT_DIR}"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------- 前置检查 ----------
if [[ $(id -u) -ne 0 ]]; then
    error "必须以 root 身份运行此脚本。"
    error "正确用法：sudo $0"
    exit 1
fi

if [[ ! -d /opt/bigdata ]] || [[ ! -f /etc/systemd/system/loan-kafka.service ]] 2>/dev/null; then
    ALREADY_INSTALLED=false
else
    ALREADY_INSTALLED=true
fi

echo ""
echo -e "${CYAN}=================================================="
echo -e "  贷款客户信息修复与智能决策系统 — 生产部署"
echo -e "  Version: 1.0.0  |  Date: $(date +%Y-%m-%d)"
echo -e "==================================================${NC}"
echo ""
info "检测到项目根目录: ${PROJECT_ROOT}"
info "部署脚本目录: ${DEPLOY_DIR}"
echo ""

# ---------- Step 1: 系统基础 ----------
section "Step 1/7 — 系统基础包 + 创建用户"
if [[ -f "${DEPLOY_DIR}/bootstrap.sh" ]]; then
    bash "${DEPLOY_DIR}/bootstrap.sh"
else
    warn "bootstrap.sh 未找到，跳过。"
fi

# ---------- Step 2: Hadoop / Spark / Hive ----------
section "Step 2/7 — Hadoop 3.3.6 + Spark 3.5.1 + Hive 3.1.3"
if [[ -f "${DEPLOY_DIR}/install_hadoop_spark_hive.sh" ]]; then
    bash "${DEPLOY_DIR}/install_hadoop_spark_hive.sh"
else
    warn "install_hadoop_spark_hive.sh 未找到，跳过。"
fi
source /etc/profile.d/loan-bigdata.sh 2>/dev/null || true

# ---------- Step 3: MySQL + Python ----------
section "Step 3/7 — MySQL 8 + Python 3 虚拟环境"
if [[ -f "${DEPLOY_DIR}/install_mysql_python.sh" ]]; then
    bash "${DEPLOY_DIR}/install_mysql_python.sh"
else
    warn "install_mysql_python.sh 未找到，跳过。"
fi

# ---------- Step 4: MySQL JDBC ----------
section "Step 4/7 — MySQL Connector/J 8.0.33"
if [[ -f "${DEPLOY_DIR}/install_mysql_jdbc.sh" ]]; then
    bash "${DEPLOY_DIR}/install_mysql_jdbc.sh"
else
    warn "install_mysql_jdbc.sh 未找到，跳过。"
fi

# ---------- Step 5: Kafka ----------
section "Step 5/7 — Kafka 3.6（KRaft 模式）"
if [[ -f "${DEPLOY_DIR}/install_kafka.sh" ]]; then
    bash "${DEPLOY_DIR}/install_kafka.sh"
else
    warn "install_kafka.sh 未找到，跳过。"
fi

# ---------- Step 6: Flume ----------
section "Step 6/7 — Flume 1.11"
if [[ -f "${DEPLOY_DIR}/install_flume.sh" ]]; then
    bash "${DEPLOY_DIR}/install_flume.sh"
else
    warn "install_flume.sh 未找到，跳过。"
fi

# 复制 Flume 配置文件
if [[ -f "${DEPLOY_DIR}/flume_agent.conf" ]]; then
    info "复制 Flume Agent 配置文件..."
    mkdir -p /opt/flume/conf
    cp "${DEPLOY_DIR}/flume_agent.conf" /opt/flume/conf/flume-agent.conf
fi

# ---------- Step 7: HDFS 目录初始化 ----------
section "Step 7/7 — HDFS 目录 + Hive 表 + MySQL 表"
if [[ -f "${DEPLOY_DIR}/init_hdfs_layout.sh" ]]; then
    bash "${DEPLOY_DIR}/init_hdfs_layout.sh"
else
    warn "init_hdfs_layout.sh 未找到，跳过。"
fi

# Hive 表
if command -v hive &>/dev/null && [[ -f "${PROJECT_ROOT}/sql/hive/create_tables.hql" ]]; then
    info "初始化 Hive 表..."
    hive -f "${PROJECT_ROOT}/sql/hive/create_tables.hql" 2>/dev/null || warn "Hive 表初始化失败，请手动执行：hive -f sql/hive/create_tables.hql"
fi

# MySQL 表
if command -v mysql &>/dev/null && [[ -f "${PROJECT_ROOT}/sql/mysql/create_tables.sql" ]]; then
    info "初始化 MySQL 表..."
    mysql -u root < "${PROJECT_ROOT}/sql/mysql/create_tables.sql" 2>/dev/null || warn "MySQL 表初始化失败，请手动执行：mysql -u root -p < sql/mysql/create_tables.sql"
fi

# Supervisor（可选）
if command -v supervisorctl &>/dev/null && [[ -f "${DEPLOY_DIR}/supervisor_flume.conf" ]]; then
    info "部署 Supervisor 配置..."
    cp "${DEPLOY_DIR}/supervisor_flume.conf" /etc/supervisor/conf.d/loan.conf
    systemctl restart supervisor
fi

# ---------- 验收 ----------
section "部署验收"
source /etc/profile.d/loan-bigdata.sh 2>/dev/null || true
source /etc/profile.d/loan-kafka.sh 2>/dev/null || true

echo ""
echo -e "${GREEN}所有脚本执行完毕${NC}"
echo ""
echo "========== 版本验收 =========="
command -v java &>/dev/null && java -version 2>&1 | head -1 || echo "Java: 未找到"
command -v hdfs &>/dev/null && echo "Hadoop: $(hdfs version 2>/dev/null | head -1)" || echo "Hadoop: 未找到"
command -v spark-submit &>/dev/null && spark-submit --version 2>&1 | head -3 || echo "Spark: 未找到"
command -v hive &>/dev/null && echo "Hive: $(hive --version 2>/dev/null | head -1)" || echo "Hive: 未找到"
command -v mysql &>/dev/null && echo "MySQL: $(mysql --version 2>/dev/null | head -1)" || echo "MySQL: 未找到"
command -v flume-ng &>/dev/null && echo "Flume: $(flume-ng version 2>/dev/null | head -1)" || echo "Flume: 未找到"
echo "Kafka: ${KAFKA_HOME:-未找到}"
echo "Python venv: /opt/bigdata/loan-venv"
echo "JDBC JAR: ${JDBC_JAR:-未设置}"
echo ""

echo "========== 启动命令参考 =========="
echo ""
echo "  # 启动 Hadoop（HDFS + YARN）:"
echo "  sudo systemctl start hadoop-hdfs-namenode"
echo "  sudo systemctl start hadoop-hdfs-datanode"
echo "  sudo systemctl start hadoop-yarn-resourcemanager"
echo ""
echo "  # 启动 Kafka（首次需先格式化）:"
echo "  sudo systemctl start loan-kafka"
echo ""
echo "  # 启动 Flume 采集:"
echo "  /opt/flume/current/bin/flume-ng agent \\"
echo "      -n loan-agent \\"
echo "      -c /opt/flume/conf \\"
echo "      -f /opt/flume/conf/flume-agent.conf &"
echo ""
echo "  # 启动 Spark 流处理（Kafka 模式）:"
echo "  ./jobs/streaming/run_streaming.sh --mode kafka"
echo ""
echo "  # 启动 Flask API:"
echo "  source /opt/bigdata/loan-venv/bin/activate"
echo "  FLASK_APP=service/flask/app.py flask run --host 0.0.0.0 --port 5000"
echo ""
echo "  # 查看 Kafka topics:"
echo "  /opt/kafka/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092"
echo ""
echo -e "${GREEN}部署完成！请参考上方启动命令启动各服务。${NC}"
