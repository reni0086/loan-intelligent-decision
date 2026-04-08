#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# Sqoop 同步脚本：Hive → MySQL（Sqoop Export）
# 用于将 Hive 数据仓库中的清洗后数据导出到 MySQL ODS 层
# ============================================================
#
# 用法：
#   bash deploy/vm/sqoop_export_hive_mysql.sh
#
# 依赖：
#   - Sqoop 1.4.7
#   - MySQL Connector/J
#   - Hive 表已存在
#   - MySQL 表已存在
# ============================================================

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# 配置参数（可根据环境修改）
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DB="${MYSQL_DB:-loan_ods}"
MYSQL_USER="${MYSQL_USER:-loan_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-loan_pass_123}"
HIVE_WAREHOUSE="${HIVE_WAREHOUSE:-/user/hive/warehouse}"
SQOOP_EXPORT_DIR="${SQOOP_EXPORT_DIR:-/tmp/sqoop_export}"

# JDBC URL
JDBC_URL="jdbc:mysql://${MYSQL_HOST}:${MYSQL_PORT}/${MYSQL_DB}?useSSL=false&serverTimezone=UTC"

echo ""
echo "=========================================="
echo "  Sqoop Export: Hive → MySQL"
echo "=========================================="
echo ""

# 前置检查
if ! command -v sqoop &>/dev/null; then
    error "Sqoop 未安装或不在 PATH 中"
    error "请先运行: bash deploy/vm/install_sqoop.sh"
    exit 1
fi

if ! command -v hive &>/dev/null; then
    error "Hive 未安装或不在 PATH 中"
    exit 1
fi

info "JDBC URL: ${JDBC_URL}"
info "MySQL User: ${MYSQL_USER}"
info "MySQL Database: ${MYSQL_DB}"
echo ""

# 创建临时导出目录
mkdir -p "${SQOOP_EXPORT_DIR}"
sudo chmod -R 777 "${SQOOP_EXPORT_DIR}" 2>/dev/null || true

# ========================================
# 导出表 1: customer_profile（客户基本信息）
# ========================================
echo ""
info "导出 customer_profile 表..."

# 先从 Hive 导出到 HDFS
hive -e "
SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
EXPORT TABLE loan_dwd.loan_cleaned 
TO '/tmp/sqoop_export/customer_profile';
" 2>/dev/null || warn "Hive export 失败，尝试直接导出..."

# 使用 Sqoop export（update-mode：只更新已有记录）
sqoop export \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table customer_profile \
    --export-dir "${HIVE_WAREHOUSE}/loan_dwd.db/loan_cleaned" \
    --input-fields-terminated-by ',' \
    --input-lines-terminated-by '\n' \
    --input-null-string '\\N' \
    --input-null-non-string '\\N' \
    --update-mode allowinsert \
    --update-key customer_id \
    --batch \
    --direct \
    2>&1 | tee /tmp/sqoop_export_cust.log

info "customer_profile 导出完成 (日志: /tmp/sqoop_export_cust.log)"

# ========================================
# 导出表 2: loan_fact（贷款发放事实表）
# ========================================
echo ""
info "导出 loan_fact 表..."

sqoop export \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table loan_fact \
    --export-dir "${HIVE_WAREHOUSE}/loan_dwd.db/loan_cleaned" \
    --input-fields-terminated-by ',' \
    --input-lines-terminated-by '\n' \
    --input-null-string '\\N' \
    --input-null-non-string '\\N' \
    --update-mode allowinsert \
    --update-key customer_id \
    --batch \
    2>&1 | tee /tmp/sqoop_export_loan.log

info "loan_fact 导出完成 (日志: /tmp/sqoop_export_loan.log)"

# ========================================
# 导出表 3: repair_evaluation（修复评估指标）
# ========================================
echo ""
info "导出 repair_evaluation 表..."

sqoop export \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table repair_evaluation \
    --export-dir "${HIVE_WAREHOUSE}/loan_ads.db/risk_daily_summary" \
    --input-fields-terminated-by ',' \
    --input-lines-terminated-by '\n' \
    --update-mode allowinsert \
    --update-key dt \
    --batch \
    2>&1 | tee /tmp/sqoop_export_repair.log

info "repair_evaluation 导出完成 (日志: /tmp/sqoop_export_repair.log)"

# ========================================
# 导出表 4: model_artifacts（模型制品）
# ========================================
echo ""
info "导出 model_artifacts 表..."

sqoop export \
    --connect "${JDBC_URL}" \
    --username "${MYSQL_USER}" \
    --password "${MYSQL_PASSWORD}" \
    --table model_artifacts \
    --export-dir "${HIVE_WAREHOUSE}/loan_ads.db/model_performance" \
    --input-fields-terminated-by ',' \
    --input-lines-terminated-by '\n' \
    --update-mode allowinsert \
    --update-key model_id \
    --batch \
    2>&1 | tee /tmp/sqoop_export_model.log

info "model_artifacts 导出完成 (日志: /tmp/sqoop_export_model.log)"

# ========================================
# 验证导出结果
# ========================================
echo ""
echo "=========================================="
echo "  验证导出结果"
echo "=========================================="
echo ""

mysql -h"${MYSQL_HOST}" -P"${MYSQL_PORT}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" "${MYSQL_DB}" <<SQL
SELECT 'customer_profile' AS table_name, COUNT(*) AS record_count FROM customer_profile
UNION ALL
SELECT 'loan_fact', COUNT(*) FROM loan_fact
UNION ALL
SELECT 'repair_evaluation', COUNT(*) FROM repair_evaluation
UNION ALL
SELECT 'model_artifacts', COUNT(*) FROM model_artifacts;
SQL

echo ""
info "Sqoop Export 全部完成！"
echo ""
echo "导出日志位置："
echo "  - /tmp/sqoop_export_cust.log"
echo "  - /tmp/sqoop_export_loan.log"
echo "  - /tmp/sqoop_export_repair.log"
echo "  - /tmp/sqoop_export_model.log"
