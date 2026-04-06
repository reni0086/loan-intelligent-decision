# 项目交付说明（甲方版）

## 1. 项目概述
- 项目名称：基于大数据的贷款客户信息修复与智能决策系统
- 交付形态：本地可运行全链路版本（可迁移到分布式生产环境）
- 交付目标：完成“采集-存储-修复-决策-实时-可视化”闭环能力验证

## 2. 交付功能矩阵

| 功能模块 | 交付状态 | 实现方式 | 关键产物 |
|---|---|---|---|
| 数据采集 | 已完成 | 批量导入 + 伪实时队列 | `run_ingest_storage.py` |
| 数据存储 | 已完成 | `raw/cleaned/featured/model` 分层 + SQLite 结构化表 | `data_lake/`、`loan_system.db` |
| 智能修复 | 已完成 | FP-growth 风格规则修复 + ALS 风格矩阵分解修复 | `run_repair_pipeline.py` |
| 智能决策 | 已完成 | 违约预测、欺诈检测、额度预测、信用评分 | `run_decision_suite.py` |
| 实时处理 | 已完成 | 微批消费、在线推理、结果回写、监控日志 | `run_realtime_worker.py` |
| API 服务 | 已完成 | Flask 接口集（预测、评分、修复、统计） | `app.py` |
| 可视化看板 | 已完成 | 前端看板 + API 联动 | `dashboard/` |
| 文档体系 | 已完成 | 总进度文档 + 模块进度文档 + 交付清单 | `PROJECT_STATUS.md`、`docs/progress/` |

## 3. 运行与验收

### 3.1 运行步骤
1. `python -m pip install -r requirements.txt`
2. `python run_ingest_storage.py`
3. `python run_repair_pipeline.py`
4. `python run_decision_suite.py`
5. `python run_realtime_worker.py`
6. `python app.py`
7. 浏览器打开 `http://127.0.0.1:5000/`

### 3.2 验收标准
- 产物存在并可读取：
  - `artifacts/ingest_storage_report.json`
  - `artifacts/repair_evaluation.json`
  - `artifacts/model_registry.json`
  - `monitoring/metrics.log`
- 接口可用：
  - `GET /health` 返回 200
  - `GET /stats/overview` 返回 200
  - `POST /predict/default` 返回合法预测结果
- 数据流验证：
  - `realtime_events`、`realtime_decisions` 表均有新增记录

## 4. 当前边界与风险说明
- 当前版本为本地可运行实现，适合 PoC/验收演示与业务流程验证。
- 尚未接入生产集群组件（Flume/Kafka/Spark/Hive/MySQL）的真实部署。
- 欺诈检测当前使用弱监督标签构造，建议生产阶段替换为真实标注样本。

## 5. 迁移到生产环境建议
- 存储：SQLite -> MySQL + Hive/Parquet
- 消息：jsonl 队列 -> Kafka topic
- 流式：本地微批 -> Spark Streaming/Flink
- 服务：单机 Flask -> 容器化 + API 网关 + 监控告警

## 6. 交付清单（文件级）
- 代码入口：`run_ingest_storage.py`、`run_repair_pipeline.py`、`run_decision_suite.py`、`run_realtime_worker.py`、`app.py`
- 核心代码：`src/`
- 页面资源：`dashboard/`
- 文档：`PROJECT_STATUS.md`、`docs/progress/`、`DELIVERY_NOTES.md`、`DELIVERY_CLIENT.md`
- 依赖：`requirements.txt`

## 7. 后续维护约定
- 每新增或完成一个模块，必须同步更新：
  - `PROJECT_STATUS.md`（总览）
  - `docs/progress/module_*.md`（模块级说明）
- 版本交付前，需更新验收步骤与风险边界，确保文档与代码一致。
