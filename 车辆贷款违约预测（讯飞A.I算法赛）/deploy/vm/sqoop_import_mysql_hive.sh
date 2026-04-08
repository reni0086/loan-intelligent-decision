#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# Sqoop 同步脚本：MySQL → Hive（Sqoop Import）
# 用于将 MySQL ODS 层的数据导入到 Hive 数据仓库
# ============================================================
#
# 用法：
#   bash deploy/vm/sqoop_import_mysql_hive.sh
#
# 依赖：
#   - Sqoop 1.4.7
#   - MySQL Connector/J
#   - Hive 表结构已存在
# ============================================================

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# 配置参数
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DB="${MYSQL_DB:-loan_ods}"
MYSQL_USER="${MYSQL_USER:-loan_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-loan_pass_123}"
HIVE_WAREHOUSE="${HIVE_WAREHOUSE:-/user/hive/warehouse}"
HDFS_TARGET_DIR="${HDFS_TARGET_DIR:-/data_lake/mysql_import}"

# JDBC URL
JDBC_URL="jdbc:mysql://${MYSQL_HOST}:${MYSQL_PORT}/${MYSQL_DB}?useSSL=false&serverTimezone=UTC"

echo ""
echo "=========================================="
echo "  Sqoop Import: MySQL → Hive"
echo "=========================================="
echo ""

# 前置检查
if ! command -v sqoop &>/dev/null; then
    error "Sqoop 未安装或不在 PATH 中"
    error "请先运行: bash deploy/vm/install_sqoop.sh"
    exit 1
fi

if ! command -v hive &>/dev/null; then
    error "Hive 未安装"
    exit 1
fi

info "JDBC URL: ${JDBC_URL}"
info "MySQL User: ${MYSQL_USER}"
info "MySQL Database: ${MYSQL_DB}"
info "HDFS Target: ${HDFS_TARGET_DIR}"
echo ""

# 创建 HDFS 目录
info "创建 HDFS 目录..."
hdfs dfs -mkdir -p "${HDFS_TARGET_DIR}"/{customer_profile,loan_fact,repair_evaluation}
hdfs dfs -chmod -R 777 "${HDFS_TARGET_DIR}"

# ========================================
# 导入表 1: customer_profile
# ========================================
echo ""
info "导入 customer_profile 表..."

sqoop import \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table customer_profile \
    --target-dir "${HDFS_TARGET_DIR}/customer_profile" \
    --delete-target-dir \
    --fields-terminated-by ',' \
    --lines-terminated-by '\n' \
    --null-string '\\N' \
    --null-non-string '\\N' \
    --hive-import \
    --hive-table loan_ods.customer_profile \
    --hive-overwrite \
    --create-hive-table \
    --num-mappers 2 \
    --batch \
    2>&1 | tee /tmp/sqoop_import_cust.log

info "customer_profile 导入完成"

# ========================================
# 导入表 2: loan_fact
# ========================================
echo ""
info "导入 loan_fact 表..."

sqoop import \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table loan_fact \
    --target-dir "${HDFS_TARGET_DIR}/loan_fact" \
    --delete-target-dir \
    --fields-terminated-by ',' \
    --lines-terminated-by '\n' \
    --null-string '\\N' \
    --null-non-string '\\N' \
    --hive-import \
    --hive-table loan_ods.loan_fact \
    --hive-overwrite \
    --create-hive-table \
    --num-mappers 2 \
    --batch \
    2>&1 | tee /tmp/sqoop_import_loan.log

info "loan_fact 导入完成"

# ========================================
# 导入表 3: repair_evaluation
# ========================================
echo ""
info "导入 repair_evaluation 表..."

sqoop import \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table repair_evaluation \
    --target-dir "${HDFS_TARGET_DIR}/repair_evaluation" \
    --delete-target-dir \
    --fields-terminated-by ',' \
    --lines-terminated-by '\n' \
    --hive-import \
    --hive-table loan_ods.repair_evaluation \
    --hive-overwrite \
    --create-hive-table \
    --num-mappers 1 \
    --batch \
    2>&1 | tee /tmp/sqoop_import_repair.log

info "repair_evaluation 导入完成"

# ========================================
# 验证导入结果
# ========================================
echo ""
echo "=========================================="
echo "  验证导入结果"
echo "=========================================="
echo ""

# 检查 HDFS 文件
info "HDFS 文件检查："
hdfs dfs -ls -h "${HDFS_TARGET_DIR}"

# 检查 Hive 表
info "Hive 表检查："
hive -e "SELECT 'customer_profile' AS table_name, COUNT(*) AS cnt FROM loan_ods.customer_profile
UNION ALL SELECT 'loan_fact', COUNT(*) FROM loan_ods.loan_fact
UNION ALL SELECT 'repair_evaluation', COUNT(*) FROM loan_ods.repair_evaluation;" 2>/dev/null || true

echo ""
info "Sqoop Import 全部完成！"
echo ""
echo "导入日志位置："
echo "  - /tmp/sqoop_import_cust.log"
echo "  - /tmp/sqoop_import_loan.log"
echo "  - /tmp/sqoop_import_repair.log"
