# 基于大数据的贷款客户信息修复与智能决策系统 — 运行说明

> 本文档面向**最终用户**，手把手说明如何在 Windows 环境下将本系统完整运行起来。每个步骤均提供命令、预期输出与验收检查点。

---

## 一、系统概述

本系统是一个本地可运行的大数据 + AI 信贷决策平台，基于 **226 万条** LendingClub 真实贷款数据构建，覆盖以下全链路能力：

| 模块 | 说明 |
|------|------|
| **数据采集与存储** | CSV 批量导入 → SQLite 结构化存储 |
| **智能修复** | FP-Growth 关联规则 + ALS 矩阵分解，修复缺失/错误数据 |
| **智能决策** | 违约预测 / 欺诈检测 / 额度预测 / 信用评分卡 |
| **实时处理** | 微批消费、在线推理、结果回写、监控日志 |
| **API 服务** | Flask RESTful 接口集 |
| **可视化看板** | 4 个完整页面（综合看板 / 客户画像 / 风险热力图 / 模型解释） |

**基础数据**：226 万条训练记录（`car_loan_train.csv`）+ 11 万条测试记录（`test.csv`）

---

## 二、环境准备

### 2.1 硬件要求

| 项目 | 最低要求 | 推荐 |
|------|---------|------|
| 内存 | 8 GB RAM | 16 GB RAM（训练更快） |
| 磁盘 | 10 GB 可用 | 20 GB+ |
| Python | 3.9+ | 3.10 / 3.11 |

### 2.2 安装 Python

前往 https://www.python.org/downloads/ 下载 **Python 3.10** 或更新版本。

安装时勾选：
- ✅ Add Python to PATH
- ✅ Install pip

安装完成后在终端验证：

```powershell
python --version
pip --version
```

### 2.3 创建虚拟环境（推荐）

```powershell
cd "C:\Users\Ren\Desktop\O，基于大数据的贷款客户信息修复与智能决策系统(2)\车辆贷款违约预测（讯飞A.I算法赛）"

python -m venv venv

# 激活虚拟环境（PowerShell）
.\venv\Scripts\Activate.ps1

# 激活虚拟环境（CMD）
venv\Scripts\activate.bat
```

### 2.4 安装依赖

```powershell
pip install -r requirements.txt
```

> **注意**：`pyspark` 在 Windows 上可能需要额外配置 JAVA_HOME。若不准备使用 Spark 批处理功能，删除 `requirements.txt` 中的 `pyspark` 及其传递依赖后重新安装即可。

---

## 三、运行步骤

按以下顺序执行 6 个步骤即可完成全链路运行。

### 第 1 步 — 安装依赖（已完成请跳过）

```powershell
pip install -r requirements.txt
```

---

### 第 2 步 — 数据采集与存储

```powershell
python run_ingest_storage.py
```

**预期行为**：
- 将 `car_loan_train.csv` 复制到 `data_lake/raw/`
- 执行 Spark 数据清洗（等效逻辑）→ `data_lake/cleaned/train_cleaned.csv`
- 构造特征快照 → `data_lake/featured/train_featured.csv`
- 初始化 SQLite 数据库 `data_lake/loan_system.db`
- 创建伪实时队列 `data_lake/raw/realtime_queue.jsonl`

**预期产物**：

```
data_lake/
├── raw/
│   ├── train_20260xxx.csv        # 原始数据副本
│   └── realtime_queue.jsonl     # 实时事件队列
├── cleaned/
│   └── train_cleaned.csv        # 清洗后数据
├── featured/
│   └── train_featured.csv      # 特征工程后数据
└── loan_system.db              # SQLite 数据库
artifacts/
└── ingest_storage_report.json  # 入库报告
```

**验收检查**：生成 `artifacts/ingest_storage_report.json`（非空文件）。

---

### 第 3 步 — 智能数据修复

```powershell
python run_repair_pipeline.py
```

**预期行为**：
- 加载清洗后数据
- FP-Growth 关联规则挖掘，提取高置信度规则
- ALS 矩阵分解，修复数值型缺失特征
- 输出修复后数据 + 评估报告

**预期产���**：

```
data_lake/featured/
└── train_repaired.csv           # 修复后数据（含修复标记字段）
artifacts/
└── repair_evaluation.json     # 修复效果评估报告
```

**验收检查**：`repair_evaluation.json` 中包含 `fp_accuracy`、`als_rmse` 等指标。

---

### 第 4 步 — 训练决策模型

```powershell
python run_decision_suite.py
```

**预期行为**：
- 加载修复后数据
- 分别训练三个模型：
  - **违约预测**（XGBoost 分类）：AUC ≈ 0.87
  - **欺诈检测**（RandomForest 分类）：准确率 > 85%
  - **额度预测**（梯度提升回归）：RMSE ≈ 2600
- 计算 SHAP 特征重要性
- 保存模型到 artifacts 目录

**预期产物**：

```
artifacts/
├── default_model.joblib        # 违约预测模型
├── fraud_model.joblib          # 欺诈检测模型
├── limit_model.joblib          # 额度预测模型
└── model_registry.json         # 模型注册表（含指标）
```

**验收检查**：`artifacts/model_registry.json` 存在且包含 `default`、`fraud`、`limit` 三个模型条目。

---

### 第 5 步 — 启动实时微批处理 Worker（可选）

```powershell
python run_realtime_worker.py
```

**预期行为**：
- 从实时队列（jsonl）消费数据
- 调用已训练的模型进行在线推理
- 将决策结果回写 SQLite 数据库
- 记录监控日志

> 若无实时数据需求（仅看板展示），可跳过此步。

**验收检查**：`monitoring/metrics.log` 有内容写入，或 SQLite 中 `realtime_decisions` 表有新记录。

---

### 第 6 步 — 启动 API 服务与看板

```powershell
python app.py
```

终端输出类似：

```
* Running on http://127.0.0.1:5000
* Press CTRL+C to quit
```

---

## 四、访问系统

### 4.1 看板页面（浏览器打开）

| 页面 | 访问地址 |
|------|---------|
| **综合运营看板** | http://127.0.0.1:5000/dashboard/index.html |
| **客户画像** | http://127.0.0.1:5000/dashboard/customer_profile.html |
| **风险热力图** | http://127.0.0.1:5000/dashboard/risk_heatmap.html |
| **模型解释** | http://127.0.0.1:5000/dashboard/model_explain.html |

### 4.2 API 健康检查

打开浏览器或使用 curl 访问：

```bash
curl http://127.0.0.1:5000/health
```

**预期响应**：

```json
{"status": "ok", "time": "2026-04-05T10:00:00"}
```

### 4.3 API 接口快速验证

**业务概览**：

```bash
curl http://127.0.0.1:5000/stats/overview
```

**违约预测**：

```bash
curl -X POST http://127.0.0.1:5000/predict/default ^
  -H "Content-Type: application/json" ^
  -d "{\"customer_id\":100001,\"credit_score\":720,\"disbursed_amount\":35000}"
```

**完整决策（一次调用返回全部结果）**：

```bash
curl -X POST http://127.0.0.1:5000/predict/full ^
  -H "Content-Type: application/json" ^
  -d "{\"customer_id\":100001,\"credit_score\":720,\"disbursed_amount\":35000}"
```

---

## 五、模块说明

### 5.1 各脚本功能一览

| 脚本 | 功能 |
|------|------|
| `run_ingest_storage.py` | 采集原始数据、清洗、特征工程、SQLite 入库 |
| `run_repair_pipeline.py` | FP-Growth 规则修复 + ALS 矩阵分解修复 |
| `run_decision_suite.py` | 训练违约/欺诈/额度三模型，保存 artifacts |
| `run_realtime_worker.py` | 伪实时微批推理（消费队列→推理→回写） |
| `app.py` | Flask API 服务（含看板静态文件） |

### 5.2 源码模块说明

| 模块 | 功能 |
|------|------|
| `src/config.py` | 项目路径配置（数据湖、artifacts、SQLite 等） |
| `src/ingest_storage.py` | 采集、清洗、特征工程、SQLite 操作 |
| `src/repair.py` | FP-Growth 关联规则修复 + ALS 矩阵分解修复 |
| `src/decision.py` | XGBoost 违约/欺诈/额度模型训练与评估 |
| `src/realtime_api.py` | Flask 应用工厂 + 所有 API 路由 |

### 5.3 数据库表结构（SQLite）

| 表名 | 说明 |
|------|------|
| `customer_profile` | 客户基本信息 |
| `loan_fact` | 贷款事实表 |
| `repair_metrics` | 修复效果指标 |
| `model_registry` | 模型注册表 |
| `realtime_events` | 实时事件队列表 |
| `realtime_decisions` | 实时决策结果表 |

---

## 六、验收清单

完成全部 6 步后，对照以下清单逐项检查：

| # | 检查项 | 预期结果 |
|---|--------|---------|
| 1 | `python run_ingest_storage.py` 执行成功 | 终端输出 `completed`，无报错 |
| 2 | `artifacts/ingest_storage_report.json` 存在 | 文件非空，含 `total_records` 等字段 |
| 3 | `python run_repair_pipeline.py` 执行成功 | 终端输出 `completed`，无报错 |
| 4 | `artifacts/repair_evaluation.json` 存在 | 文件非空，含修复指标 |
| 5 | `python run_decision_suite.py` 执行成功 | 终端输出 `completed`，无报错 |
| 6 | `artifacts/model_registry.json` 存在 | 含 `default`、`fraud`、`limit` 三模型 |
| 7 | `python app.py` 启动成功 | 监听 http://127.0.0.1:5000 |
| 8 | `GET /health` 返回 200 | JSON 包含 `status: ok` |
| 9 | `GET /stats/overview` 返回 200 | 含 `total_customers`、金额等字段 |
| 10 | 看板页面可访问 | http://127.0.0.1:5000/dashboard/index.html 正常加载 |

---

## 七、常见问题

### Q1: `ModuleNotFoundError: No module named 'xgboost'`

**解决**：确保虚拟环境已激活，然后重新安装依赖。

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Q2: `pyarrow` 或 `pyspark` 在 Windows 上报错

**解决**：如不使用 Spark 批处理，可删除 `requirements.txt` 中的 `pyspark` 相关行后重新安装。核心功能（本地 Python 模式）不依赖 PySpark。

### Q3: `python app.py` 启动后浏览器无法访问

**解决**：
1. 检查端口 5000 是否被占用：`netstat -ano | findstr 5000`
2. 如被占用，修改 `app.py` 中 `port=5000` 为其他端口（如 5001）

### Q4: 看板页面图表空白

**解决**：确保第 2–4 步已执行完毕，相关数据文件和 artifacts 已生成。

### Q5: 内存不足（Out of Memory）

**解决**：修改 `src/decision.py` 中的训练参数，减少 `max_samples` 或 `n_estimators`。

---

## 八、扩展阅读

| 文档 | 内容 |
|------|------|
| `PROJECT_STATUS.md` | 项目整体进度总览 |
| `DELIVERY_CLIENT.md` | 甲方交付说明 |
| `DELIVERY_NOTES.md` | 最终验收清单 |
| `docs/SYSTEM_ARCHITECTURE.md` | 系统架构详解（含大数据架构图） |
| `docs/API_SPEC.md` | 所有 API 接口详细规范 |
| `README_MVP.md` | MVP 快速验证版本说明 |

---

*本文档版本：2026-04-05*
