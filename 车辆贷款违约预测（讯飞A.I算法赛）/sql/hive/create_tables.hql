-- ============================================================
--  Hive 数仓 DDL — 贷款客户信息修复与智能决策系统
-- ============================================================
-- 包含以下层次：
--   loan_ods  （Operational Data Store）：原始层，从 Flume/HDFS 接入原始数据
--   loan_dwd  （Data Warehouse Detail）：明细层，经清洗、去重、修复后的数据
--   loan_ads  （Application Data Service）：应用层，聚合指标和模型评分
--
-- 与 Flume + Kafka 数据管道的对应关系：
--   Flume HDFS Sink  → /data_lake/raw/  → loan_ods.raw_loan_data (Parquet, 分区)
--   Kafka Topic      → Spark Streaming   → loan_dwd.loan_realtime_scored
--   Spark Repair     → /data_lake/cleaned/ → loan_dwd.loan_cleaned
--   Spark ALS Repair → loan_dwd.loan_repaired_als
--   Spark FP-Growth → loan_dwd.loan_repaired_fp
-- ============================================================

-- ---------- ODS 层（原始层）----------
CREATE DATABASE IF NOT EXISTS loan_ods;
CREATE DATABASE IF NOT EXISTS loan_dwd;
CREATE DATABASE IF NOT EXISTS loan_ads;

-- ODS: 原始贷款数据（Flume HDFS Sink 写入的 Parquet 文件）
-- 分区字段 dt=数据日期，由 Flume 拦截器注入 timestamp
CREATE EXTERNAL TABLE IF NOT EXISTS loan_ods.raw_loan_data (
  customer_id                     BIGINT,
  main_account_loan_no            DOUBLE,
  main_account_active_loan_no     DOUBLE,
  main_account_overdue_no         DOUBLE,
  main_account_outstanding_loan   DOUBLE,
  main_account_sanction_loan      DOUBLE,
  main_account_disbursed_loan     DOUBLE,
  sub_account_loan_no             DOUBLE,
  sub_account_active_loan_no      DOUBLE,
  sub_account_overdue_no          DOUBLE,
  sub_account_outstanding_loan    DOUBLE,
  sub_account_sanction_loan       DOUBLE,
  sub_account_disbursed_loan     DOUBLE,
  disbursed_amount                DOUBLE,
  asset_cost                      DOUBLE,
  branch_id                       INT,
  supplier_id                     INT,
  manufacturer_id                 INT,
  area_id                         INT,
  employee_code_id                INT,
  mobileno_flag                   INT,
  idcard_flag                     INT,
  Driving_flag                    INT,
  passport_flag                   INT,
  credit_score                    DOUBLE,
  main_account_monthly_payment   DOUBLE,
  sub_account_monthly_payment     DOUBLE,
  last_six_month_new_loan_no      DOUBLE,
  last_six_month_defaulted_no     DOUBLE,
  average_age                     DOUBLE,
  credit_history                  DOUBLE,
  enquirie_no                     DOUBLE,
  loan_to_asset_ratio             DOUBLE,
  total_account_loan_no           DOUBLE,
  sub_account_inactive_loan_no    DOUBLE,
  total_inactive_loan_no         DOUBLE,
  main_account_inactive_loan_no  DOUBLE,
  total_overdue_no               DOUBLE,
  total_outstanding_loan          DOUBLE,
  total_sanction_loan             DOUBLE,
  total_disbursed_loan           DOUBLE,
  total_monthly_payment          DOUBLE,
  outstanding_disburse_ratio      DOUBLE,
  main_account_tenure            DOUBLE,
  sub_account_tenure             DOUBLE,
  disburse_to_sactioned_ratio    DOUBLE,
  active_to_inactive_act_ratio    DOUBLE,
  year_of_birth                   INT,
  disbursed_date                  STRING,
  Credit_level                    INT,
  employment_type                 INT,
  age                             INT,
  loan_default                    INT,
  -- Flume 注入的元字段
  flume_host                      STRING,
  flume_ts                        TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
LOCATION '/data_lake/raw'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ODS: 实时评分结果（Spark Structured Streaming from Kafka → Parquet）
CREATE EXTERNAL TABLE IF NOT EXISTS loan_ods.kafka_realtime_scored (
  customer_id              BIGINT,
  default_probability     DOUBLE,
  default_pred            INT,
  kafka_topic             STRING,
  kafka_partition         INT,
  kafka_offset            BIGINT,
  kafka_event_time        TIMESTAMP,
  scored_at               TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
LOCATION '/data_lake/featured/realtime_kafka_scored'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ODS: 贷款申请事件（Kafka Consumer 写入 MySQL 的事件流）
CREATE EXTERNAL TABLE IF NOT EXISTS loan_ods.loan_events_raw (
  event_id                BIGINT,
  customer_id             BIGINT,
  event_type              STRING,
  disbursed_amount        DOUBLE,
  credit_score            DOUBLE,
  area_id                 INT,
  event_time              TIMESTAMP,
  kafka_offset            BIGINT
)
STORED AS PARQUET
LOCATION '/data_lake/raw/events'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ---------- DWD 层（明细层）----------
-- DWD: 清洗后的数据（去重 + 基本过滤）
CREATE TABLE IF NOT EXISTS loan_dwd.loan_cleaned (
  customer_id                     BIGINT,
  main_account_loan_no            DOUBLE,
  main_account_active_loan_no     DOUBLE,
  main_account_overdue_no         DOUBLE,
  main_account_outstanding_loan   DOUBLE,
  main_account_sanction_loan      DOUBLE,
  main_account_disbursed_loan     DOUBLE,
  sub_account_loan_no             DOUBLE,
  sub_account_active_loan_no      DOUBLE,
  sub_account_overdue_no          DOUBLE,
  sub_account_outstanding_loan    DOUBLE,
  sub_account_sanction_loan       DOUBLE,
  sub_account_disbursed_loan     DOUBLE,
  disbursed_amount                DOUBLE,
  asset_cost                      DOUBLE,
  branch_id                       INT,
  supplier_id                     INT,
  manufacturer_id                 INT,
  area_id                         INT,
  employee_code_id                INT,
  mobileno_flag                   INT,
  idcard_flag                     INT,
  Driving_flag                    INT,
  passport_flag                    INT,
  credit_score                    DOUBLE,
  main_account_monthly_payment    DOUBLE,
  sub_account_monthly_payment     DOUBLE,
  last_six_month_new_loan_no      DOUBLE,
  last_six_month_defaulted_no      DOUBLE,
  average_age                     DOUBLE,
  credit_history                  DOUBLE,
  enquirie_no                     DOUBLE,
  loan_to_asset_ratio             DOUBLE,
  total_account_loan_no           DOUBLE,
  sub_account_inactive_loan_no   DOUBLE,
  total_inactive_loan_no         DOUBLE,
  main_account_inactive_loan_no  DOUBLE,
  total_overdue_no               DOUBLE,
  total_outstanding_loan          DOUBLE,
  total_sanction_loan             DOUBLE,
  total_disbursed_loan           DOUBLE,
  total_monthly_payment          DOUBLE,
  outstanding_disburse_ratio      DOUBLE,
  main_account_tenure            DOUBLE,
  sub_account_tenure             DOUBLE,
  disburse_to_sactioned_ratio    DOUBLE,
  active_to_inactive_act_ratio    DOUBLE,
  year_of_birth                   INT,
  disbursed_date                  STRING,
  Credit_level                    INT,
  employment_type                 INT,
  age                             INT,
  loan_default                    INT
)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY')
AS
SELECT *
FROM loan_ods.raw_loan_data
WHERE customer_id IS NOT NULL;

-- DWD: FP-Growth 关联规则修复后的数据（信用等级被修复）
CREATE TABLE IF NOT EXISTS loan_dwd.loan_repaired_fp (
  customer_id                     BIGINT,
  -- 原始字段
  disbursed_amount                DOUBLE,
  credit_score                    DOUBLE,
  Credit_level                    INT,
  employment_type                 INT,
  area_id                         INT,
  age                             INT,
  -- 修复后的字段
  repaired_credit_level           INT,
  repair_confidence_credit_level  DOUBLE,
  -- 特征标签
  overdue_flag                    INT,
  high_inquiry_flag               INT,
  ltv_ratio                       DOUBLE
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- DWD: ALS 矩阵分解修复后的数据（数值特征被修复）
CREATE TABLE IF NOT EXISTS loan_dwd.loan_repaired_als (
  customer_id                    BIGINT,
  main_account_loan_no           DOUBLE,
  main_account_active_loan_no    DOUBLE,
  main_account_overdue_no        DOUBLE,
  main_account_outstanding_loan  DOUBLE,
  main_account_sanction_loan     DOUBLE,
  main_account_disbursed_loan    DOUBLE,
  sub_account_loan_no            DOUBLE,
  sub_account_active_loan_no     DOUBLE,
  sub_account_overdue_no         DOUBLE,
  sub_account_outstanding_loan   DOUBLE,
  sub_account_sanction_loan      DOUBLE,
  sub_account_disbursed_loan    DOUBLE,
  disbursed_amount               DOUBLE,
  asset_cost                     DOUBLE,
  credit_score                  DOUBLE,
  total_outstanding_loan         DOUBLE,
  total_monthly_payment          DOUBLE,
  total_account_loan_no          DOUBLE,
  total_overdue_no               DOUBLE,
  total_disbursed_loan          DOUBLE,
  total_sanction_loan           DOUBLE,
  loan_default                   INT,
  -- ALS 修复后的数值特征
  repaired_credit_score          DOUBLE,
  repaired_disbursed_amount      DOUBLE,
  repaired_asset_cost            DOUBLE,
  repaired_total_outstanding_loan DOUBLE,
  repaired_total_monthly_payment DOUBLE,
  -- 修复元数据
  als_repair_method              STRING,
  repair_timestamp               TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- DWD: 关联规则表（存储 FP-Growth 挖掘出的规则）
CREATE TABLE IF NOT EXISTS loan_dwd.fp_growth_rules (
  rule_id            BIGINT,
  antecedent         STRING,
  consequent         STRING,
  support            DOUBLE,
  confidence         DOUBLE,
  lift               DOUBLE,
  created_at         TIMESTAMP
)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- DWD: 评分结果表（模型推理结果）
CREATE TABLE IF NOT EXISTS loan_dwd.model_scores (
  customer_id            BIGINT,
  default_probability    DOUBLE,
  default_pred          INT,
  fraud_probability     DOUBLE,
  fraud_pred            INT,
  predicted_limit       DOUBLE,
  credit_score          DOUBLE,
  model_version         STRING,
  scored_at             TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ---------- ADS 层（应用层）----------
-- ADS: 每日风险汇总（MySQL 同步 Hive 后由 Spark ADS 计算）
CREATE TABLE IF NOT EXISTS loan_ads.risk_daily_summary (
  dt                          STRING,
  total_customers             BIGINT,
  total_disbursed_amount      DOUBLE,
  avg_disbursed_amount        DOUBLE,
  total_defaulted             BIGINT,
  default_rate                DOUBLE,
  avg_credit_score            DOUBLE,
  avg_default_probability     DOUBLE,
  top_risk_area               STRING,
  fraud_high_risk_count       BIGINT,
  fraud_rate                  DOUBLE,
  avg_predicted_limit         DOUBLE,
  als_rmse                   DOUBLE,
  als_mape                    DOUBLE,
  fp_growth_coverage          DOUBLE,
  fp_growth_accuracy          DOUBLE,
  computed_at                 TIMESTAMP
)
PARTITIONED BY (year STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ADS: 客户画像（实时决策 + 脱敏字段，供仪表板使用）
CREATE TABLE IF NOT EXISTS loan_ads.customer_profile_ads (
  customer_id             BIGINT,
  credit_score            DOUBLE,
  default_probability     DOUBLE,
  fraud_probability       DOUBLE,
  credit_score_v2         INT,
  ltv_ratio               DOUBLE,
  overdue_rate            DOUBLE,
  risk_level              STRING,
  area_id                 INT,
  employment_type          INT,
  age_band                STRING,
  tenure_band             STRING,
  computed_at             TIMESTAMP
)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ADS: 模型性能追踪表
CREATE TABLE IF NOT EXISTS loan_ads.model_performance (
  model_name              STRING,
  model_version           STRING,
  metric_name             STRING,
  metric_value            DOUBLE,
  eval_dataset            STRING,
  eval_date               STRING,
  computed_at             TIMESTAMP
)
PARTITIONED BY (year STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');
