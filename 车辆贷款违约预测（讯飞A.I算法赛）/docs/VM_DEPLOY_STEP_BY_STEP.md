# 虚拟机部署分步指南（完整生产栈）

## 一、完整一键部署（推荐首次使用）

```bash
# 在 VM 服务器上以 root 身份运行（约 20~40 分钟）
chmod +x deploy/vm/setup_production.sh
sudo ./deploy/vm/setup_production.sh

# 首次启动 Kafka（仅首次需要）：
/opt/kafka/bin/kafka-storage.sh format     -c /opt/kafka/config/kraft/server.properties --ignore-formatted
systemctl start loan-kafka

# 启动 Flume（采集 CSV → HDFS + Kafka）：
/opt/flume/bin/flume-ng agent     -n loan-agent     -c /opt/flume/conf     -f /opt/flume/conf/flume-agent.conf &
```
---

## 二、分步安装（精细控制）

### 步骤 1：系统基础包 + Hadoop + Spark + Hive

```bash
chmod +x deploy/vm/bootstrap.sh
sudo ./deploy/vm/bootstrap.sh

chmod +x deploy/vm/install_hadoop_spark_hive.sh
sudo ./deploy/vm/install_hadoop_spark_hive.sh
```

验证：

```bash
hdfs version   # Hadoop 3.3.6
spark-submit --version  # Spark 3.5.1
hive --version  # Hive 3.1.3
echo $HADOOP_HOME  # /opt/bigdata/hadoop
echo $SPARK_HOME   # /opt/bigdata/spark
```

### 步骤 2：MySQL + Python 环境 + JDBC Driver

```bash
chmod +x deploy/vm/install_mysql_python.sh
sudo ./deploy/vm/install_mysql_python.sh

chmod +x deploy/vm/install_mysql_jdbc.sh
sudo ./deploy/vm/install_mysql_jdbc.sh
```

验证：

```bash
mysql --version
# Active Python venv:
source /opt/bigdata/loan-venv/bin/activate
pip list | grep -E "pandas|scikit-learn|xgboost|flask|kafka"
# MySQL JDBC:
ls /usr/share/java/mysql-connector-j-8.0.33.jar
```

### 步骤 3：Kafka 3.6（KRaft 模式，无需 Zookeeper）

```bash
chmod +x deploy/vm/install_kafka.sh
sudo ./deploy/vm/install_kafka.sh

# 首次启动（仅首次）：
/opt/kafka/bin/kafka-storage.sh format     -c /opt/kafka/config/kraft/server.properties --ignore-formatted

systemctl start loan-kafka
# 或手动启动：
/opt/kafka/bin/kafka-server-start.sh     /opt/kafka/config/kraft/server.properties &
```

验证：

```bash
/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
# 应显示：lending_application, loan_repair_events, model_score_results

/opt/kafka/bin/kafka-topics.sh --describe     --topic lending_application     --bootstrap-server localhost:9092
```

### 步骤 4：Flume 1.11（CSV → HDFS + Kafka）

```bash
chmod +x deploy/vm/install_flume.sh
sudo ./deploy/vm/install_flume.sh

# 配置并启动：
cp deploy/vm/flume_agent.conf /opt/flume/conf/flume-agent.conf
mkdir -p /data/flume/spool /data/flume/checkpoint

/opt/flume/bin/flume-ng agent     -n loan-agent     -c /opt/flume/conf     -f /opt/flume/conf/flume-agent.conf &
```

验证：

```bash
# 查看 Flume 监控指标：
curl http://localhost:41414/metrics

# 查看 HDFS 写入文件：
hdfs dfs -ls /data_lake/raw/
# 应看到 Flume 写入的 Parquet 文件
```

### 步骤 5：Sqoop 1.4.7（MySQL ↔ Hive 双向同步）

```bash
chmod +x deploy/vm/install_sqoop.sh
sudo ./deploy/vm/install_sqoop.sh
```

验证：

```bash
sqoop version
# 应显示 Sqoop 1.4.7

# 测试连接 MySQL：
sqoop list-databases \
    --connect jdbc:mysql://localhost:3306/loan_ods \
    --username loan_user \
    --password 'loan_pass_123'
# 应显示：loan_ods, loan_rt
```

同步命令：

```bash
# Hive → MySQL 同步（导出）：
bash deploy/vm/sqoop_export_hive_mysql.sh

# MySQL → Hive 同步（导入）：
bash deploy/vm/sqoop_import_mysql_hive.sh
```

### 步骤 6：HDFS 目录 + Hive 表初始化

```bash
chmod +x deploy/vm/init_hdfs_layout.sh
sudo ./deploy/vm/init_hdfs_layout.sh

# Hive 表：
hive -f sql/hive/create_tables.hql

# MySQL 表：
mysql -u root < sql/mysql/create_tables.sql
```

验证：

```bash
hdfs dfs -ls /data_lake/
# raw/  cleaned/  featured/  model/

hive -e "SHOW DATABASES;"
# loan_ods  loan_dwd  loan_ads

mysql -u loan_user -p -e "SHOW DATABASES;"
# loan_ods  loan_rt
```

### 步骤 7：安装 Python 依赖

```bash
source /opt/bigdata/loan-venv/bin/activate
pip install -r requirements.txt
# 验证：
python -c "import pandas, numpy, sklearn, xgboost, flask, pymysql, kafka; print('All OK')"
```

---

## 三、完整流水线运行

### 3.1 批处理（离线）

```bash
# 1. Spark 预处理（去重、过滤）
spark-submit jobs/batch/preprocess_spark.py \
    --input-path /data_lake/raw/ \
    --output-table loan_dwd.loan_cleaned

# 2. FP-Growth 关联规则修复（分类特征）
spark-submit jobs/batch/repair_fpgrowth_spark.py \
    --input-table loan_dwd.loan_cleaned \
    --output-table loan_dwd.loan_repaired_fp

# 3. ALS 矩阵分解修复（数值特征）
spark-submit jobs/batch/repair_als_spark.py \
    --input-table loan_dwd.loan_cleaned \
    --output-table loan_dwd.loan_repaired_als

# 4. 评估修复质量
spark-submit jobs/batch/evaluate_repair.py \
    --output-json artifacts/spark_repair_metrics.json

# 5. Hive → MySQL 同步（Sqoop 导出）：
bash deploy/vm/sqoop_export_hive_mysql.sh

# 6. 训练模型（features_v3 增强特征）
spark-submit jobs/batch/train_from_hive.py \
    --source-table loan_dwd.loan_repaired_als \
    --feature-engineering v3 \
    --artifacts-dir artifacts
```

### 3.2 实时（Kafka）

```bash
# 1. 启动 Kafka Producer（CSV → Kafka topic）
python jobs/streaming/kafka_producer.py \
    --mode batch \
    --csv test.csv \
    --limit 10000 \
    --compression snappy \
    --kafka-brokers localhost:9092

# 或启动 HTTP 推送服务器（外部系统接入）：
python jobs/streaming/kafka_producer.py --mode http --port 8080

# 2. 启动 Spark Kafka Stream
./jobs/streaming/run_streaming.sh --mode kafka

# 验证：查看 MySQL 实时决策表
mysql -u loan_user -p -e "SELECT COUNT(*) FROM loan_rt.realtime_decisions;"
# 应随时间递增
```

### 3.3 启动 Flask API

```bash
source /opt/bigdata/loan-venv/bin/activate
FLASK_APP=service/flask/app.py flask run --host 0.0.0.0 --port 5000 &

# 测试接口：
curl http://localhost:5000/health
curl http://localhost:5000/stats/overview
curl -X POST http://localhost:5000/predict/default \
    -H "Content-Type: application/json" \
    -d '{"credit_score":650,"disbursed_amount":50000,"age":35}'
```

---

## 四、FAQ 故障排查

### Q1: Hive CLI 找不到命令

```bash
export HIVE_HOME=/opt/bigdata/hive
export PATH=$HIVE_HOME/bin:$PATH
# 或：
source /etc/profile.d/loan-bigdata.sh
```

### Q2: Spark 无法连接 MySQL（JdbcSQLException）

```bash
# 确保 JDBC JAR 在 Spark classpath 中：
cp /usr/share/java/mysql-connector-j-8.0.33.jar $SPARK_HOME/jars/

# spark-submit 时指定：
spark-submit --jars /usr/share/java/mysql-connector-j-8.0.33.jar ...
```

### Q3: Flume HDFS Sink 报错 "URI null"

```bash
# 在 flume_agent.conf 中确保设置了正确 HDFS URI：
loan-agent.sinks.hdfs-sink.hdfs.uri = hdfs://namenode:9000
# 若本机运行 namenode，使用：
loan-agent.sinks.hdfs-sink.hdfs.uri = hdfs://localhost:9000
```

### Q4: HiveServer2 无法连接

```bash
# 启动 HiveServer2：
hive --service hiveserver2 &

# Beeline 连接：
beeline -u "jdbc:hive2://localhost:10000" -n loan
```

### Q5: Spark Structured Streaming 从 Kafka 读取失败

```bash
# 检查 Kafka 是否运行：
systemctl status loan-kafka
# 或：ps aux | grep kafka

# 检查 Kafka topic：
/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# 检查 Spark 日志：
cat logs/streaming_kafka.log | grep ERROR
```

### Q6: Spark Kafka Stream 作业无数据输出

```bash
# 1. 检查 Kafka Producer 是否运行：
/opt/kafka/bin/kafka-console-consumer.sh \
    --topic lending_application --from-beginning --bootstrap-server localhost:9092

# 2. 检查 Consumer Group：
/opt/kafka/bin/kafka-consumer-groups.sh \
    --group loan_spark_stream_group \
    --describe \
    --bootstrap-server localhost:9092

# 3. 确认 Kafka JAR 在 classpath：
spark-submit --packages org.apache.spark:spark-sql-kafka-0.10_2.12:3.5.1 ...
```

---

## 五、完整文件清单

```
deploy/vm/
  bootstrap.sh                    ← 系统基础包
  install_hadoop_spark_hive.sh   ← Hadoop + Spark + Hive
  install_mysql_python.sh        ← MySQL + Python 虚拟环境
  install_mysql_jdbc.sh          ← MySQL JDBC Driver
  install_kafka.sh               ← Kafka 3.6（KRaft）
  install_flume.sh               ← Flume 1.11
  flume_agent.conf               ← Flume Agent 配置
  supervisor_flume.conf          ← Supervisor 管理配置
  init_hdfs_layout.sh            ← HDFS 目录初始化
  setup_production.sh             ← 一键完整部署（本文件）

sql/
  hive/create_tables.hql          ← Hive 三层数仓 DDL
  mysql/create_tables.sql         ← MySQL ODS/RT DDL

jobs/
  batch/
    preprocess_spark.py           ← Spark 预处理 ETL
    repair_fpgrowth_spark.py      ← FP-Growth 关联规则修复
    repair_als_spark.py           ← ALS 矩阵分解修复
    evaluate_repair.py            ← 修复质量评估
    sync_hive_mysql.py            ← Hive ↔ MySQL 双向同步
    train_from_hive.py            ← Spark Hive 模型训练（features_v3）
  streaming/
    kafka_producer.py              ← CSV → Kafka Topic 生产者（新增）
    realtime_kafka_stream.py       ← Spark Kafka Source 流评分（新增）
    realtime_kafka_consumer.py    ← Kafka Consumer Python 服务
    realtime_score_spark.py       ← Spark 文件流评分
    realtime_to_mysql.py          ← Spark → MySQL 实时写入
    run_streaming.sh              ← 流作业启动器（已支持 Kafka 模式）
```

---

## 六、性能调优参数参考

```bash
# Spark Executor 资源配置（按服务器资源调整）
--executor-memory 4g
--executor-cores 4
--conf spark.sql.shuffle.partitions=200
--conf spark.streaming.backpressure.enabled=true
--conf spark.streaming.kafka.maxRatePerPartition=200

# Kafka Producer（高吞吐配置）
batch.size=65536
linger.ms=20
compression.type=snappy

# HDFS 副本因子（测试=1，生产=3）
hdfs dfs -setrep -w 3 /data_lake/
```
