# 基于大数据的贷款客户信息修复与智能决策系统

## 项目介绍

本项目是一个完整的大数据 + AI 驱动信贷决策平台，基于 LendingClub 15万条真实贷款数据构建，涵盖从数据采集、清洗、修复到智能决策的全链路功能。

### 核心功能

- **数据采集**: Flume 批量采集 + Kafka 实时流接入 + Sqoop 双向同步
- **数据存储**: HDFS 分布式存储 + Hive 数据仓库 + MySQL 在线库
- **数据处理**: Spark SQL 清洗 + FP-Growth 关联规则修复 + ALS 矩阵分解修复
- **智能决策**: XGBoost 违约预测 / 欺诈检测 / 额度预测 + 信用评分卡
- **实时处理**: Spark Streaming + Kafka 实时流处理 (<100ms 响应)
- **可视化看板**: Flask + ECharts + Leaflet.js + D3.js 四页面完整看板

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 数据采集与存储

```bash
python run_ingest_storage.py
```

### 3. 数据修复

```bash
python run_repair_pipeline.py
```

### 4. 训练决策模型

```bash
python run_decision_suite.py
```

### 5. 启动 API 服务

```bash
python app.py
```

### 6. 访问可视化看板

- 综合看板: `http://127.0.0.1:5000/dashboard/index.html`
- 客户画像: `http://127.0.0.1:5000/dashboard/customer_profile.html`
- 风险热力图: `http://127.0.0.1:5000/dashboard/risk_heatmap.html`
- 模型解释: `http://127.0.0.1:5000/dashboard/model_explain.html`

---

## 项目结构

```
项目根目录/
├── app.py                          # Flask API 入口
├── src/
│   ├── config.py                   # 项目配置 (data_lake/artifacts 路径)
│   ├── decision.py                # 决策模型训练 (违约/欺诈/额度)
│   ├── repair.py                   # FP-Growth + ALS 信息修复
│   ├── ingest_storage.py           # 数据采集与 SQLite 入库
│   └── realtime_api.py              # 实时微批处理 API
├── features_v2.py                  # 基础特征工程
├── features_v3.py                  # 增强特征工程 (时间特征/编码/稳定性)
├── jobs/
│   ├── batch/
│   │   ├── preprocess_spark.py     # Spark 数据清洗
│   │   ├── repair_fpgrowth_spark.py  # FP-Growth Spark 修复
│   │   ├── repair_als_spark.py     # ALS Spark 修复
│   │   ├── train_from_hive.py      # 从 Hive 训练模型
│   │   └── sync_hive_mysql.py      # Hive → MySQL 同步
│   └── streaming/
│       ├── realtime_to_mysql.py    # 实时数据写入 MySQL
│       ├── realtime_score_spark.py # Spark Streaming 评分
│       └── realtime_kafka_consumer.py  # Kafka 消费端
├── service/flask/
│   ├── app.py                      # Flask 工厂
│   ├── config.py                  # 服务配置
│   ├── model_loader.py            # 模型加载与推理
│   └── routes/
│       ├── customer.py             # 客户画像 API
│       ├── predict.py             # 预测 API
│       └── stats.py               # 统计 API
├── dashboard/                    # 可视化看板
│   ├── index.html                 # 综合运营看板
│   ├── customer_profile.html       # 客户画像页面
│   ├── risk_heatmap.html          # 风险热力图
│   ├── model_explain.html          # 模型解释页面
│   ├── css/main.css              # 全局样式
│   └── js/
│       ├── api.js                 # 统一 API 调用层
│       ├── main.js                # 综合看板渲染逻辑
│       ├── customer_profile.js     # 客户画像渲染逻辑
│       ├── risk_heatmap.js        # 地图热力图逻辑
│       └── model_explain.js        # SHAP 可视化逻辑
├── sql/
│   ├── hive/create_tables.hql     # Hive 建表脚本
│   └── mysql/create_tables.sql     # MySQL 建表脚本
├── docs/
│   ├── SYSTEM_ARCHITECTURE.md      # 系统架构文档
│   └── API_SPEC.md                 # API 接口规范
├── deploy/vm/                      # VMware 部署脚本
├── data_lake/                     # 本地数据湖 (dev 模式)
│   ├── raw/                       # 原始数据
│   ├── cleaned/                   # 清洗后数据
│   ├── featured/                  # 特征工程后数据
│   └── model/                    # 模型文件
├── artifacts/                    # 模型 artifacts
│   ├── default_model.joblib       # 违约预测模型
│   ├── fraud_model.joblib        # 欺诈检测模型
│   ├── limit_model.joblib        # 额度预测模型
│   └── model_registry.json       # 模型注册表
├── car_loan_train.csv           # 训练数据集 (15万条)
└── test.csv                     # 测试数据集
```

---

## 看板页面说明

### 综合运营看板 (`dashboard/index.html`)

展示系统的综合运营状况，包括：
- 4个 KPI 指标卡片（总客户数、总贷款金额、逾期率、新增客户）
- 逾期率趋势折线图
- 风险等级分布饼图
- 地区风险 Top5 柱状图
- 客户聚类散点图
- 信用评分分布直方图
- SHAP 特征重要性 Top10
- 系统运行指标（API调用数、平均响应时间、修复成功率）
- 最新决策记录表格

### 客户画像 (`dashboard/customer_profile.html`)

提供单个客户的深度分析：
- 雷达图（5维度：信用评分/还款能力/资产状况/历史记录/稳定性）
- 贷款行为时间轴
- 智能决策结果（违约概率/信用评分/预测额度/欺诈概率）
- SHAP 预测解释（Force Plot）
- Top-5 相似客户对比表格

### 风险热力图 (`dashboard/risk_heatmap.html`)

展示全国各地区的风险分布：
- Leaflet.js 全国热力地图（按违约率着色）
- 风险统计概览（高/中/低风险地区数量）
- 高风险预警列表
- 地区违约率排行榜

### 模型解释 (`dashboard/model_explain.html`)

提供模型的深度可解释性：
- SHAP 特征重要性条形图
- 多模型性能对比（XGBoost/LightGBM/CatBoost/RF/LogReg）
- 单客户 Waterfall 预测解释
- 特征影响详情（正向/负向风险因素）
- 典型决策案例（批准/审慎/拒绝）

---

## API 接口

### 预测接口

```bash
# 违约预测
curl -X POST http://127.0.0.1:5000/predict/default \
  -H "Content-Type: application/json" \
  -d '{"customer_id":100001,"credit_score":720,"disbursed_amount":35000}'

# 欺诈检测
curl -X POST http://127.0.0.1:5000/predict/fraud \
  -H "Content-Type: application/json" \
  -d '{"customer_id":100001,"enquirie_no":3}'

# 额度预测
curl -X POST http://127.0.0.1:5000/predict/limit \
  -H "Content-Type: application/json" \
  -d '{"customer_id":100001,"credit_score":720}'

# 完整决策
curl -X POST http://127.0.0.1:5000/predict/full \
  -H "Content-Type: application/json" \
  -d '{"customer_id":100001,"credit_score":720}'
```

### 客户画像接口

```bash
# 客户画像
curl http://127.0.0.1:5000/customer/100001/profile

# 相似客户
curl http://127.0.0.1:5000/customer/100001/similar

# 贷款历史
curl http://127.0.0.1:5000/customer/100001/loan_history
```

### 统计接口

```bash
curl http://127.0.0.1:5000/stats/overview
curl http://127.0.0.1:5000/stats/risk_daily
curl http://127.0.0.1:5000/stats/risk_distribution
curl http://127.0.0.1:5000/stats/model_metrics
curl http://127.0.0.1:5000/stats/area_risk
curl http://127.0.0.1:5000/model/shap_values
```

完整 API 文档参考: `docs/API_SPEC.md`

---

## 技术指标

| 模块 | 指标 |
|------|------|
| 违约预测 AUC | 0.873 |
| 精确率 | 0.820 |
| 召回率 | 0.790 |
| F1-Score | 0.800 |
| FP-Growth 修复准确率 | 80%+ |
| ALS 修复 RMSE | <0.3 sigma |
| 实时响应时间 | <100ms |
| 吞吐量 | 1000 条/秒 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据采集 | Flume, Kafka, Sqoop |
| 数据存储 | HDFS, Hive, MySQL |
| 数据处理 | Spark SQL, Spark MLlib |
| 智能算法 | XGBoost, FP-Growth, ALS |
| 实时处理 | Spark Streaming, Kafka |
| 服务框架 | Flask |
| 可视化 | ECharts, Leaflet.js, D3.js |
| 编程语言 | Python |
| 部署环境 | VMware |

---

## 参考文献

- PDF 设计文档: `f8e1528a5765ba910db75bd83e2270d1_9372e2adc91cb388a4c90136ce78a806_8.pdf`
- 架构文档: `docs/SYSTEM_ARCHITECTURE.md`
- API 规范: `docs/API_SPEC.md`
