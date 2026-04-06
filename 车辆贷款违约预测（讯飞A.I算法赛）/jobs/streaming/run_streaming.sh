#!/usr/bin/env bash
# =============================================================================
# run_streaming.sh — Launch Spark Structured Streaming Pipeline
# =============================================================================
# 支持两种模式：
#
#   FILE 模式（默认）：监控 CSV 文件目录 → 评分 → 写入 MySQL
#   KAFKA 模式：       从 Kafka topic 消费 → 评分 → 写入 MySQL + HDFS Parquet
#
# Usage:
#   ./run_streaming.sh                  # 文件模式（默认）
#   ./run_streaming.sh --mode kafka    # Kafka 模式（生产推荐）
#   ./run_streaming.sh --mode both      # 同时启动两个流作业
#   MODE=kafka ./run_streaming.sh       # 环境变量方式指定模式
#
# Environment variables:
#   MODEL_PATH        XGBoost 模型路径（默认：artifacts/default_model.joblib）
#   INPUT_DIR         CSV 输入目录（文件模式，默认：/data_lake/raw/realtime_input）
#   SCORED_DIR        评分结果输出目录（默认：/data_lake/featured/realtime_scored）
#   KAFKA_BROKERS     Kafka brokers（Kafka 模式，默认：namenode:9092）
#   KAFKA_TOPIC       Kafka topic（Kafka 模式，默认：lending_application）
#   KAFKA_GROUP       Kafka consumer group（默认：loan_spark_stream_group）
#   MYSQL_URL         MySQL JDBC URL（默认：jdbc:mysql://127.0.0.1:3306/loan_rt）
#   MYSQL_USER        MySQL 用户（默认：loan_user）
#   MYSQL_PASSWORD    MySQL 密码（默认：loan_pass_123）
#   SPARK_MASTER      Spark Master（默认：yarn，测试用：local[*]）
# =============================================================================

set -euo pipefail

MODE="${MODE:-${1:-file}}"
if [[ "$1" == "--mode" && -n "${2:-}" ]]; then
    MODE="$2"
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Defaults
MODEL_PATH="${MODEL_PATH:-artifacts/default_model.joblib}"
INPUT_DIR="${INPUT_DIR:-/data_lake/raw/realtime_input}"
SCORED_DIR="${SCORED_DIR:-/data_lake/featured/realtime_scored}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-/data_lake/model/ckpt}"
KAFKA_BROKERS="${KAFKA_BROKERS:-namenode:9092}"
KAFKA_TOPIC="${KAFKA_TOPIC:-lending_application}"
KAFKA_GROUP="${KAFKA_GROUP:-loan_spark_stream_group}"
MYSQL_URL="${MYSQL_URL:-jdbc:mysql://127.0.0.1:3306/loan_rt?useSSL=false&serverTimezone=UTC}"
MYSQL_USER="${MYSQL_USER:-loan_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-loan_pass_123}"
SPARK_MASTER="${SPARK_MASTER:-yarn}"
SPARK_DEPLOY="${SPARK_DEPLOY:-cluster}"

# Kafka Structured Streaming JAR（必须随 spark-submit 传入）
KAFKA_PKG="org.apache.spark:spark-sql-kafka-0.10_2.12:3.5.1"
JDBC_JAR="${JDBC_JAR:-/opt/bigdata/mysql-connector-j-8.0.33.jar}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()    { echo -e "\${GREEN}[INFO]\${NC}  $*"; }
warn()    { echo -e "\${YELLOW}[WARN]\${NC}  $*" >&2; }
error()   { echo -e "\${RED}[ERROR]\${NC} $*" >&2; }

info "=========================================="
info "  Spark Structured Streaming Launcher"
info "  Mode:     ${MODE}"
info "  Spark:    ${SPARK_MASTER} (${SPARK_DEPLOY})"
info "  Model:    ${MODEL_PATH}"
info "=========================================="

# Verify model file exists
if [[ ! -f "${MODEL_PATH}" ]]; then
    error "Model file not found: ${MODEL_PATH}"
    error "Run 'python run_decision_suite.py' first to train the model."
    exit 1
fi

# Common spark-submit flags
COMMON_FLAGS=(
    --master "${SPARK_MASTER}"
    --deploy-mode "${SPARK_DEPLOY}"
    --driver-memory 2g
    --executor-memory 2g
    --executor-cores 2
    --conf "spark.sql.adaptive.enabled=true"
    --conf "spark.sql.adaptive.coalescePartitions.enabled=true"
    --conf "spark.streaming.backpressure.enabled=true"
)

info "Starting streaming pipeline in '${MODE}' mode..."

# ============================
# FILE MODE
# ============================
run_file_mode() {
    info "[FILE MODE] Step 1: Score CSV files from ${INPUT_DIR}"
    spark-submit \
        "${COMMON_FLAGS[@]}" \
        jobs/streaming/realtime_score_spark.py \
        --input-dir "${INPUT_DIR}" \
        --output-dir "${SCORED_DIR}" \
        --checkpoint "${CHECKPOINT_DIR}/realtime_score" \
        --model-path "${MODEL_PATH}" \
        &> "logs/streaming_score.log" &

    local score_pid=$!
    info "[FILE MODE] Scoring stream started (PID: ${score_pid})"

    sleep 3

    info "[FILE MODE] Step 2: Write scored results to MySQL ${MYSQL_URL}"
    spark-submit \
        "${COMMON_FLAGS[@]}" \
        --jars "${JDBC_JAR}" \
        jobs/streaming/realtime_to_mysql.py \
        --input-dir "${SCORED_DIR}" \
        --checkpoint "${CHECKPOINT_DIR}/realtime_mysql" \
        --mysql-url "${MYSQL_URL}" \
        --mysql-user "${MYSQL_USER}" \
        --mysql-password "${MYSQL_PASSWORD}" \
        &> "logs/streaming_mysql.log" &

    local mysql_pid=$!
    info "[FILE MODE] MySQL sink stream started (PID: ${mysql_pid})"

    info "File mode streaming running. PIDs: ${score_pid}, ${mysql_pid}"
    wait ${score_pid} ${mysql_pid}
}

# ============================
# KAFKA MODE
# ============================
run_kafka_mode() {
    info "[KAFKA MODE] Connecting to Kafka: ${KAFKA_BROKERS} / topic: ${KAFKA_TOPIC}"
    info "[KAFKA MODE] Group: ${KAFKA_GROUP}"

    info "[KAFKA MODE] Starting Spark Kafka Stream: Kafka → Score → HDFS Parquet"
    spark-submit \
        "${COMMON_FLAGS[@]}" \
        --packages "${KAFKA_PKG}" \
        --jars "${JDBC_JAR}" \
        jobs/streaming/realtime_kafka_stream.py \
        --kafka-brokers "${KAFKA_BROKERS}" \
        --kafka-topic "${KAFKA_TOPIC}" \
        --kafka-group "${KAFKA_GROUP}" \
        --starting-offsets latest \
        --fail-on-data-loss false \
        --model-path "${MODEL_PATH}" \
        --threshold 0.5 \
        --output-parquet "/data_lake/featured/realtime_kafka_scored" \
        --checkpoint "${CHECKPOINT_DIR}/kafka_stream_ckpt" \
        --trigger-interval "5 seconds" \
        --enable-mysql-sink \
        --mysql-url "${MYSQL_URL}" \
        --mysql-user "${MYSQL_USER}" \
        --mysql-password "${MYSQL_PASSWORD}" \
        &> "logs/streaming_kafka.log" &

    local kafka_pid=$!
    info "[KAFKA MODE] Kafka stream started (PID: ${kafka_pid})"

    info "Kafka mode streaming running. PID: ${kafka_pid}"
    wait ${kafka_pid}
}

# ============================
# BOTH MODES
# ============================
run_both_mode() {
    info "[BOTH MODE] Starting both file-mode and kafka-mode streams in parallel..."

    run_file_mode &
    local file_pid=$!

    run_kafka_mode &
    local kafka_pid=$!

    info "Both modes running. File PID: ${file_pid}, Kafka PID: ${kafka_pid}"
    wait ${file_pid} ${kafka_pid}
}

# Create required directories
mkdir -p "${INPUT_DIR}" "${SCORED_DIR}" "${CHECKPOINT_DIR}" logs

# Dispatch by mode
case "${MODE}" in
    file|kafka|both)
        mkdir -p logs
        "run_${MODE}_mode"
        ;;
    *)
        error "Unknown mode: ${MODE}"
        error "Supported modes: file, kafka, both"
        echo ""
        echo "Usage:"
        echo "  ./run_streaming.sh --mode file   # CSV file directory mode"
        echo "  ./run_streaming.sh --mode kafka  # Kafka topic mode (production)"
        echo "  ./run_streaming.sh --mode both   # Both streams in parallel"
        exit 1
        ;;
esac
