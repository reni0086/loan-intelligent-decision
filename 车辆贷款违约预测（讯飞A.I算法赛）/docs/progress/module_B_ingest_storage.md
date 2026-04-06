# 模块 B：数据采集与存储

## 模块目标
实现本地可运行的数据采集链路、分层数据湖存储和结构化数据库落地，形成可迁移到大数据组件的基础框架。

## 已完成功能
- 批量采集：将训练集与测试集复制到 `data_lake/raw/`。
- 分层存储：创建 `raw/cleaned/featured/model` 四层目录。
- 清洗落地：生成 `data_lake/cleaned/train_cleaned.csv`。
- 特征快照：生成 `data_lake/featured/train_featured.csv`。
- 结构化存储：使用 SQLite 创建五类业务表和实时事件表。
- 伪实时队列：生成 `data_lake/raw/realtime_queue.jsonl` 并支持批量消费入库。
- 统计报告：生成 `artifacts/ingest_storage_report.json`。

## 实现方式
- 代码路径：
  - `src/config.py`
  - `src/ingest_storage.py`
  - `run_ingest_storage.py`
- 数据流：
  - `CSV -> raw -> cleaned -> featured -> SQLite`
  - `test.csv -> realtime_queue.jsonl -> realtime_events`

## 验证结果
- `run_ingest_storage.py` 执行成功。
- 报告文件存在：`artifacts/ingest_storage_report.json`。

## 未完成项
- 生产环境 Flume/Kafka/Sqoop/HDFS/Hive 对接（当前为本地模拟）。

## 风险与下一步
- 风险：本地模拟无法覆盖分布式容错特性。
- 下一步：进入模块 C，完成智能修复算法与对照评估。
