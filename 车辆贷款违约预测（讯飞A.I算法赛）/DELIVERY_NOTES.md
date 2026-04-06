# 交付说明文档

## 一、交付范围

### 1.1 技术架构（完整生产栈）

| 层次 | 组件 | 状态 |
|------|------|------|
| **数据采集** | Flume Agent（Spooling Dir Source → HDFS + Kafka） | ✅ 已交付 |
| **数据采集** | Apache Kafka 3.6（KRaft 无 ZK） | ✅ 已交付 |
| **数据采集** | Kafka Producer（CSV → Kafka Topic） | ✅ 已交付 |
| **存储** | HDFS 分层目录（/data_lake/raw/cleaned/featured/model） | ✅ 已交付 |
| **存储** | Hive 3.1 数仓（ODS / DWD / ADS 三层） | ✅ 已交付 |
| **存储** | MySQL 8.0 在线库（loan_ods + loan_rt） | ✅ 已交付 |
| **处理** | Spark 3.5.1 Batch ETL + MLlib 修复 | ✅ 已交付 |
| **处理** | Spark Structured Streaming（Kafka Source） | ✅ 已交付 |
| **数据同步** | Spark JDBC 双向同步（Hive ↔ MySQL） | ✅ 已交付 |
| **服务** | Flask REST API + MySQL/Hive Repository | ✅ 已交付 |
| **部署** | VM 一键部署脚本（setup_production.sh） | ✅ 已交付 |
| **文档** | 完整部署文档 + 验收清单 | ✅ 已交付 |

### 1.2 新增文件清单

```
deploy/vm/
  setup_production.sh              # 一键式完整部署（新增）
  install_flume.sh                  # Flume 安装脚本（新增）
  flume_agent.conf                 # Flume Agent 配置（新增）
  supervisor_flume.conf            # Supervisor 管理配置（新增）
  install_kafka.sh                 # Kafka 3.6 安装脚本（新增）
  install_mysql_jdbc.sh            # MySQL JDBC Driver 部署（新增）

jobs/streaming/
  kafka_producer.py                 # CSV → Kafka Topic 生产者（新增）
  realtime_kafka_stream.py         # Spark Kafka Source 评分流（新增）

jobs/batch/
  train_from_hive.py               # 使用 features_v3 增强特征工程（已更新）

sql/hive/
  create_tables.hql                # 完整三层数仓 DDL（已更新）

sql/mysql/
  create_tables.sql                # ODS/RT 完整 DDL，含实时表（已更新）

requirements.txt                   # 含 kafka-python（已更新）
run_decision_suite.py             # 支持 features_v3 和 spark 模式（已更新）
```

---

## 二、快速启动（生产模式）

### 2.1 一键部署（首次运行）

```bash
# 在 VM 服务器上以 root 运行（20~40 分钟）
chmod +x deploy/vm/setup_production.sh
sudo ./deploy/vm/setup_production.sh
```

### 2.2 分步部署（可选精细控制）

```bash
# 1. Hadoop + Spark + Hive
chmod +x deploy/vm/install_hadoop_spark_hive.sh
sudo ./deploy/vm/install_hadoop_spark_hive.sh

# 2. MySQL（含初始化脚本）
chmod +x deploy/vm/install_mysql_python.sh
sudo ./deploy/vm/install_mysql_python.sh

# 3. MySQL JDBC Driver（Spark/Sqoop 必须）
chmod +x deploy/vm/install_mysql_jdbc.sh
sudo ./deploy/vm/install_mysql_jdbc.sh

# 4. Kafka 3.6（KRaft，无需 Zookeeper）
chmod +x deploy/vm/install_kafka.sh
sudo ./deploy/vm/install_kafka.sh
# 首次格式化：
kafka-storage.sh format -c /opt/kafka/config/kraft/server.properties --ignore-formatted
systemctl start loan-kafka

# 5. Flume
chmod +x deploy/vm/install_flume.sh
sudo ./deploy/vm/install_flume.sh
# 复制配置并启动：
cp deploy/vm/flume_agent.conf /opt/flume/conf/flume-agent.conf
flume-ng agent -n loan-agent -c /opt/flume/conf -f /opt/flume/conf/flume-agent.conf &

# 6. HDFS 目录初始化
chmod +x deploy/vm/init_hdfs_layout.sh
sudo ./deploy/vm/init_hdfs_layout.sh

# 7. Hive 表初始化
hive -f sql/hive/create_tables.hql

# 8. MySQL 表初始化
mysql -u root < sql/mysql/create_tables.sql
```

### 2.3 批处理流水线（Spark）

```bash
# 1. 数据摄入（Flume → HDFS，已自动进行）
# 2. Spark 预处理 → Hive
spark-submit jobs/batch/preprocess_spark.py \
    --input-path /data_lake/raw/ \
    --output-table loan_dwd.loan_cleaned

# 3. FP-Growth 关联规则修复
spark-submit jobs/batch/repair_fpgrowth_spark.py \
    --input-table loan_dwd.loan_cleaned \
    --output-table loan_dwd.loan_repaired_fp

# 4. ALS 矩阵分解修复
spark-submit jobs/batch/repair_als_spark.py \
    --input-table loan_dwd.loan_cleaned \
    --output-table loan_dwd.loan_repaired_als

# 5. 评估修复质量
spark-submit jobs/batch/evaluate_repair.py \
    --output-json artifacts/spark_repair_metrics.json

# 6. Hive → MySQL 同步
spark-submit jobs/batch/sync_hive_mysql.py

# 7. 从 Hive 训练模型（含 features_v3 增强特征）
spark-submit jobs/batch/train_from_hive.py \
    --source-table loan_dwd.loan_repaired_als \
    --feature-engineering v3 \
    --artifacts-dir artifacts
```

### 2.4 实时流水线（Kafka + Spark Streaming）

```bash
# 1. 启动 Kafka Producer（将 CSV 数据推送到 Kafka topic）
python jobs/streaming/kafka_producer.py \
    --mode batch \
    --csv test.csv \
    --limit 10000 \
    --compression snappy

# 或者启动 HTTP 推送服务器：
python jobs/streaming/kafka_producer.py --mode http --port 8080

# 2. 启动 Spark Kafka Stream（Kafka → 评分 → HDFS + MySQL）
./jobs/streaming/run_streaming.sh --mode kafka

# 或者使用 spark-submit 直接启动：
spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0.10_2.12:3.5.1 \
    --jars /opt/bigdata/mysql-connector-j-8.0.33.jar \
    jobs/streaming/realtime_kafka_stream.py \
    --kafka-brokers namenode:9092 \
    --kafka-topic lending_application \
    --model-path artifacts/default_model.joblib \
    --output-parquet /data_lake/featured/realtime_kafka_scored \
    --enable-mysql-sink
```

### 2.5 Flask API 服务

```bash
source /opt/bigdata/loan-venv/bin/activate
FLASK_APP=service/flask/app.py flask run --host 0.0.0.0 --port 5000
```

---

## 三、验收标准

### 3.1 环境验收

```bash
# Java
java -version     # >= Java 8（Hadoop/Spark）, >= Java 11（Kafka 3.6）

# Hadoop
hdfs dfs -ls /data_lake/   # raw, cleaned, featured, model 目录存在

# Hive
hive -e "SHOW DATABASES;"   # loan_ods, loan_dwd, loan_ads 存在

# MySQL
mysql -u loan_user -p -e "SHOW DATABASES;"  # loan_ods, loan_rt 存在

# Kafka
kafka-topics.sh --list --bootstrap-server localhost:9092
# lending_application, loan_repair_events, model_score_results

# Flume
flume-ng version

# Spark
spark-submit --version
```

### 3.2 流水线验收

```bash
# 1. Spark 批处理
spark-submit jobs/batch/evaluate_repair.py --output-json /tmp/metrics.json
# 验收：FP-Growth coverage > 0，ALS rmse < 1e6（数值合理性）

# 2. Spark Streaming from Kafka
./jobs/streaming/run_streaming.sh --mode kafka &
# 验收：Kafka topic 有数据消费，realtime_decisions 表有记录写入

# 3. Flask API
curl http://localhost:5000/health
curl http://localhost:5000/stats/overview
# 验收：返回 HTTP 200，JSON 格式正常
```

### 3.3 制品清单

| 制品 | 路径 | 说明 |
|------|------|------|
| 修复评估报告 | `artifacts/repair_evaluation.json` | FP-Growth + ALS 覆盖率/准确率 |
| 模型注册表 | `artifacts/model_registry.json` | 3 个模型的路径和指标 |
| 实时决策表 | MySQL `loan_rt.realtime_decisions` | Kafka Consumer + Streaming 共同写入 |
| Hive ADS 汇总 | Hive `loan_ads.risk_daily_summary` | 每日风险指标汇总 |
| 模型制品 | `artifacts/default_model.joblib` 等 | joblib 模型包（含特征列） |

---

## 四、技术亮点

1. **无 ZK 的 Kafka**：使用 KRaft 模式简化部署，3.6 版本特性，无需额外部署 ZooKeeper。
2. **双路实时流**：Kafka Consumer（Python/kafka-python）和 Spark Kafka Source（Structured Streaming）双路并行写入 `realtime_decisions` 表。
3. **三层数仓**：ODS（Flume 原始数据）→ DWD（清洗 + 修复后）→ ADS（聚合指标）完整分层。
4. **关联规则 + 矩阵分解**：FP-Growth 修复分类特征，ALS 矩阵分解修复数值特征，两者互补。
5. **增强特征工程**：features_v3 提供时序特征、稳定性特征、复合风险评分等 30+ 衍生特征。
6. **一站式部署**：`setup_production.sh` 覆盖全部 10 个组件，无需逐个手动安装。

---

## 五、迁移说明（从 MVP 本地模式升级）

| 组件 | 本地模式 | 生产模式 | 操作 |
|------|---------|---------|------|
| 数据存储 | SQLite | MySQL + Hive | 运行 SQL DDL 脚本 |
| 消息队列 | JSONL 文件 | Kafka | 启动 Kafka + Producer |
| 实时流 | JSONL 微批 | Spark Streaming | 启动 run_streaming.sh --mode kafka |
| 模型存储 | 本地 .joblib | HDFS + MySQL | spark-submit train_from_hive.py |
| API 数据源 | SQLite | MySQL + Hive Repository | 无需改代码，已自动切换 |
