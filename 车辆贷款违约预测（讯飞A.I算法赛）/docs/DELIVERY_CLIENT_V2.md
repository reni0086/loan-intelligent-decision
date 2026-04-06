# 客户交付说明 V2（完整生产栈增强版）

## 1. 技术栈清单

| 层次 | 组件 | 版本 | 交付状态 |
|------|------|------|---------|
| **数据采集** | Apache Flume | 1.11 | ✅ 已交付 |
| **数据采集** | Apache Kafka | 3.6.1 | ✅ 已交付 |
| **数据采集** | Kafka Producer（CSV → Topic） | — | ✅ 已交付 |
| **存储** | HDFS（Hadoop Distributed FS） | 3.3.6 | ✅ 已交付 |
| **存储** | Apache Hive | 3.1.3 | ✅ 已交付 |
| **存储** | MySQL | 8.0 | ✅ 已交付 |
| **处理** | Apache Spark | 3.5.1 | ✅ 已交付 |
| **服务** | Flask REST API | 2.x | ✅ 已交付 |
| **部署** | VM Shell Scripts | — | ✅ 已交付 |

## 2. 交付目录

```
deploy/vm/          ← VM 安装脚本（含 Flume/Kafka/Hadoop/Hive/MySQL）
sql/hive/           ← Hive DDL（ODS/DWD/ADS 三层数仓）
sql/mysql/          ← MySQL DDL（loan_ods + loan_rt）
jobs/batch/         ← Spark 批处理作业（含 FP-Growth/ALS 修复）
jobs/streaming/     ← Spark Streaming + Kafka Consumer
service/flask/      ← Flask REST API
dashboard/          ← 可视化仪表板
scripts/acceptance/  ← 验收脚本
docs/               ← 部署文档 + 验收清单 + 证据
```

## 3. 执行顺序

1. **环境初始化**：运行 `deploy/vm/setup_production.sh`（一键）或分步执行各安装脚本
2. **数据库初始化**：执行 `sql/hive/create_tables.hql` 和 `sql/mysql/create_tables.sql`
3. **离线批处理**：`jobs/batch/preprocess_spark.py` → 修复 → 评估 → 同步 → 训练
4. **实时流处理**：`jobs/streaming/run_streaming.sh --mode kafka`（或 `--mode file`）
5. **API 启动**：`FLASK_APP=service/flask/app.py flask run --host 0.0.0.0 --port 5000`

## 4. 验收证据

- 环境版本记录：`docs/evidence/env_versions.md`
- 验收清单：`docs/ACCEPTANCE_CHECKLIST.md`
- 接口验收：`/health` → `200`, `/predict/*` → `200` + JSON
- 实时验收：MySQL `loan_rt.realtime_decisions` 表有持续写入记录

## 5. 关键特性

- **无 ZK 的 Kafka**：KRaft 模式，简化运维
- **三层数仓**：ODS（Flume 原始）→ DWD（清洗修复）→ ADS（聚合指标）
- **双路实时流**：Kafka Consumer（Python）和 Spark Kafka Source 并行写入
- **关联规则 + 矩阵分解**：FP-Growth 修复分类，ALS 修复数值特征
- **增强特征工程**：features_v3 含时序/稳定性/复合风险 30+ 特征

## 6. 状态

- 代码已完成 ✅，客户端可在目标 VM 上执行部署脚本完成验收
- 部分功能（如 Flume 监控、Kafka 多节点）需根据实际集群规模调整参数
