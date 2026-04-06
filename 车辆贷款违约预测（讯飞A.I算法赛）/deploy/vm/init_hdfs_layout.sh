#!/usr/bin/env bash
set -euo pipefail

BASE="/data_lake"

echo "[hdfs-init] create HDFS directories..."
hdfs dfs -mkdir -p "${BASE}/raw" "${BASE}/cleaned" "${BASE}/featured" "${BASE}/model"
hdfs dfs -chmod -R 775 "${BASE}"

echo "[hdfs-init] verify:"
hdfs dfs -ls "${BASE}"
