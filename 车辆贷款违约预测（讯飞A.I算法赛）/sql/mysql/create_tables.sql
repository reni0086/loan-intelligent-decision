-- ============================================================
--  MySQL 在线业务库 DDL — 贷款客户信息修复与智能决策系统
-- ============================================================
-- 包含以下库：
--   loan_ods  （在线操作数据）：业务系统实时数据，Sqoop 从 Hive 同步
--   loan_rt   （实时流数据）：Kafka 消费者写入的实时事件和决策
--
-- Sqoop 双向同步链路：
--   Hive (loan_dwd) → MySQL (loan_ods)  via Spark JDBC Write
--   MySQL (loan_ods) → Hive (loan_ads)  via Spark JDBC Read + ADS 计算
-- ============================================================

CREATE DATABASE IF NOT EXISTS loan_ods DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS loan_rt  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ---------- loan_ods: 在线业务数据 ----------
USE loan_ods;

-- ODS: 客户基本信息（Sqoop 从 Hive loan_dwd.loan_cleaned 同步）
CREATE TABLE IF NOT EXISTS customer_profile (
  customer_id             BIGINT PRIMARY KEY,
  year_of_birth           INT,
  age                     INT,
  employment_type          TINYINT COMMENT '0=未知, 1=长期, 2=短期, 3=合同工',
  credit_score            DOUBLE,
  credit_level            TINYINT COMMENT '1-5, -1=缺失',
  mobileno_flag           TINYINT COMMENT '0=无手机, 1=已认证',
  idcard_flag             TINYINT COMMENT '0=无身份证, 1=已认证',
  driving_flag            TINYINT COMMENT '0=无驾照, 1=已认证',
  passport_flag            TINYINT COMMENT '0=无护照, 1=已认证',
  id_verification_count   TINYINT AS (mobileno_flag + idcard_flag + driving_flag + passport_flag),
  area_id                 INT,
  credit_depth_normalized  DOUBLE,
  loan_default            TINYINT,
  updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_credit_level (credit_level),
  INDEX idx_area_id (area_id),
  INDEX idx_employment (employment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ODS: 贷款发放事实表（Sqoop 从 Hive 同步）
CREATE TABLE IF NOT EXISTS loan_fact (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id             BIGINT NOT NULL,
  disbursed_date          VARCHAR(32),
  disbursed_amount         DOUBLE,
  asset_cost               DOUBLE,
  branch_id               INT,
  supplier_id             INT,
  manufacturer_id         INT,
  area_id                 INT,
  employment_type          TINYINT,
  credit_score            DOUBLE,
  ltv_ratio               DOUBLE,
  total_disbursed_loan    DOUBLE,
  total_monthly_payment   DOUBLE,
  total_overdue_no       DOUBLE,
  total_outstanding_loan  DOUBLE,
  loan_default            TINYINT,
  year_of_birth           INT,
  age                     INT,
  -- 关联规则修复字段
  repaired_credit_level   TINYINT,
  repair_confidence_fp    DOUBLE,
  -- ALS 修复字段
  repaired_credit_score   DOUBLE,
  repaired_disbursed_amount DOUBLE,
  repaired_asset_cost     DOUBLE,
  repaired_total_outstanding_loan DOUBLE,
  repaired_total_monthly_payment DOUBLE,
  als_repair_method       VARCHAR(32),
  updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_customer_date (customer_id, disbursed_date),
  INDEX idx_customer_id (customer_id),
  INDEX idx_disbursed_date (disbursed_date),
  INDEX idx_area_id (area_id),
  INDEX idx_loan_default (loan_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ODS: 修复评估指标（Sqoop 从 Hive loan_ads 同步）
CREATE TABLE IF NOT EXISTS repair_metrics (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  metric_date             DATE,
  -- FP-Growth 指标
  fp_growth_coverage      DOUBLE COMMENT '关联规则覆盖率（0~1）',
  fp_growth_accuracy      DOUBLE COMMENT '关联规则准确率（0~1）',
  fp_growth_avg_confidence DOUBLE COMMENT '平均置信度',
  fp_growth_rules_count   INT COMMENT '生成的关联规则数量',
  -- ALS 指标
  als_rmse                DOUBLE COMMENT 'ALS 矩阵分解 RMSE',
  als_mape                DOUBLE COMMENT 'ALS 矩阵分解 MAPE',
  als_coverage            DOUBLE COMMENT 'ALS 修复覆盖率',
  als_method_used         VARCHAR(64) COMMENT '使用的修复策略（mean/median）',
  -- 通用指标
  rows_repaired           BIGINT,
  rows_total              BIGINT,
  computed_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_metric_date (metric_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ODS: 模型注册表（记录所有训练好的模型版本）
CREATE TABLE IF NOT EXISTS model_registry (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  model_name              VARCHAR(64) NOT NULL COMMENT 'default_classifier / fraud_classifier / limit_regressor',
  model_version           VARCHAR(64) NOT NULL COMMENT '例如 v1.0, v2.3, hive_v3',
  feature_version         VARCHAR(16) COMMENT '特征工程版本：v2 / v3',
  feature_count           INT COMMENT '使用的特征数量',
  artifact_path           VARCHAR(512) COMMENT '模型制品在 HDFS 的路径',
  -- 性能指标
  auc                     DOUBLE COMMENT 'AUC（分类模型）',
  accuracy                DOUBLE,
  precision               DOUBLE,
  recall                  DOUBLE,
  f1                      DOUBLE,
  rmse                    DOUBLE COMMENT 'RMSE（回归模型）',
  mae                     DOUBLE,
  best_threshold          DOUBLE,
  -- 元信息
  trained_on_dataset      VARCHAR(128) COMMENT '训练数据来源',
  train_rows              BIGINT,
  eval_rows               BIGINT,
  train_duration_sec      INT,
  train_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active               TINYINT DEFAULT 1 COMMENT '1=当前活跃版本',
  metadata_json           JSON COMMENT '额外元数据',
  INDEX idx_model_name (model_name),
  INDEX idx_is_active (is_active),
  INDEX idx_train_at (train_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- loan_rt: 实时流数据 ----------
USE loan_rt;

-- RT: 实时事件表（Kafka Consumer 消费 lending_application topic 写入）
CREATE TABLE IF NOT EXISTS realtime_events (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id             BIGINT,
  event_type              VARCHAR(32) COMMENT 'lending_application / repair_event / score_event',
  kafka_topic             VARCHAR(64) DEFAULT 'lending_application',
  kafka_partition         INT,
  kafka_offset            BIGINT,
  kafka_timestamp         TIMESTAMP,
  payload_json            JSON COMMENT '原始事件 JSON payload',
  produced_at             TIMESTAMP COMMENT 'Flume 注入的 timestamp',
  ingested_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_customer_id (customer_id),
  INDEX idx_event_type (event_type),
  INDEX idx_kafka_offset (kafka_topic, kafka_offset)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RT: 实时决策表（Kafka Consumer + Spark Streaming 共同写入）
-- 两个数据源都会写这个表，consumer 写来自 Kafka 的原始决策，streaming 写评分结果
CREATE TABLE IF NOT EXISTS realtime_decisions (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id             BIGINT,
  source                  VARCHAR(32) COMMENT 'kafka_consumer / spark_streaming',
  -- 违约预测
  default_probability     DOUBLE COMMENT 'XGBoost 违约概率（0~1）',
  default_pred            TINYINT COMMENT '违约预测标签（0/1）',
  default_threshold       DOUBLE DEFAULT 0.5,
  -- 欺诈检测
  fraud_probability       DOUBLE COMMENT '欺诈概率（0~1）',
  fraud_pred              TINYINT COMMENT '欺诈预测标签（0/1）',
  -- 额度预测
  predicted_limit         DOUBLE COMMENT '推荐贷款额度（元）',
  -- 信用评分
  credit_score            DOUBLE COMMENT '转换后的信用分（300~850）',
  -- Kafka 元信息
  kafka_topic             VARCHAR(64),
  kafka_partition         INT,
  kafka_offset            BIGINT,
  -- 业务信息
  disbursed_amount         DOUBLE,
  area_id                 INT,
  -- 决策时间
  decision_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_customer_id (customer_id),
  INDEX idx_decision_at (decision_at),
  INDEX idx_default_prob (default_probability),
  INDEX idx_area_id (area_id),
  INDEX idx_source (source),
  INDEX idx_kafka_offset (kafka_topic, kafka_partition, kafka_offset)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RT: Kafka 消费者偏移量追踪表（支持断点续传）
CREATE TABLE IF NOT EXISTS kafka_consumer_offsets (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  consumer_group          VARCHAR(128) NOT NULL,
  kafka_topic             VARCHAR(64) NOT NULL,
  partition_id            INT NOT NULL,
  current_offset          BIGINT NOT NULL,
  last_updated            TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_group_topic_partition (consumer_group, kafka_topic, partition_id),
  INDEX idx_consumer_group (consumer_group)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RT: 实时风险告警表
CREATE TABLE IF NOT EXISTS realtime_alerts (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id             BIGINT,
  alert_type              VARCHAR(32) COMMENT 'high_default / high_fraud / suspicious_pattern',
  alert_level             VARCHAR(16) COMMENT 'LOW / MEDIUM / HIGH / CRITICAL',
  default_probability     DOUBLE,
  fraud_probability       DOUBLE,
  area_id                 INT,
  triggered_by            VARCHAR(32) COMMENT 'kafka_consumer / spark_streaming',
  kafka_offset            BIGINT,
  resolved                TINYINT DEFAULT 0,
  resolved_at             TIMESTAMP,
  created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_customer_id (customer_id),
  INDEX idx_alert_type (alert_type),
  INDEX idx_alert_level (alert_level),
  INDEX idx_resolved (resolved),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
