# 车辆贷款违约预测 MVP

这是一个可直接运行的最小可用版本（MVP），包含：

- 模型训练：`train_mvp.py`
- 测试集预测：`predict_mvp.py`
- 依赖列表：`requirements.txt`

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 训练模型

```bash
python train_mvp.py --train-path car_loan_train.csv --model-path model_mvp.joblib --metrics-path metrics_mvp.txt
```

训练完成后会生成：

- `model_mvp.joblib`：训练好的模型
- `metrics_mvp.txt`：验证集评估指标

## 3. 生成预测结果

```bash
python predict_mvp.py --test-path test.csv --model-path model_mvp.joblib --output-path submission_mvp.csv
```

预测完成后会生成：

- `submission_mvp.csv`
  - `customer_id`
  - `loan_default_proba`（违约概率）
  - `loan_default_pred`（二分类结果，阈值 0.5）

## 4. 说明

- 当前版本用于快速跑通“训练 -> 预测 -> 结果导出”主链路。
- 后续可升级为更高性能模型（XGBoost/LightGBM）、更完善特征工程、模型解释（SHAP）、API 服务与可视化看板。

## 5. 升级版 XGBoost（推荐）

### 训练

```bash
python train_xgb.py --train-path car_loan_train.csv --model-path model_xgb.joblib --metrics-path metrics_xgb.txt
```

### 预测

```bash
python predict_xgb.py --test-path test.csv --model-path model_xgb.joblib --output-path submission_xgb.csv
```

说明：

- 训练时会自动根据验证集搜索最优 F1 阈值，并保存在模型文件中。
- 预测默认使用该阈值，也可以通过 `--threshold` 手动覆盖。

## 6. 强化版 XGBoost v2（特征工程 + 参数候选）

### 训练

```bash
python train_xgb_v2.py --train-path car_loan_train.csv --model-path model_xgb_v2.joblib --metrics-path metrics_xgb_v2.txt
```

### 预测

```bash
python predict_xgb_v2.py --test-path test.csv --model-path model_xgb_v2.joblib --output-path submission_xgb_v2.csv
```

说明：

- 自动构造风险比率、行为强度、对数稳定化等衍生特征。
- 使用稳健的数值化训练方案，兼容当前本地 Python/XGBoost 环境。
- 自动在 3 组参数中挑选验证集 AUC 最优的模型。

## 7. 冲分版 OOF 融合（5 折）

### 训练（生成 OOF + 融合权重）

```bash
python train_oof_blend.py --train-path car_loan_train.csv --model-path model_oof_blend.joblib --metrics-path metrics_oof_blend.txt --oof-path oof_blend.csv
```

### 预测（生成详细版 + 比赛提交版）

```bash
python predict_oof_blend.py --test-path test.csv --model-path model_oof_blend.joblib --output-path submission_oof_blend.csv --strict-output-path submission_oof_blend_strict.csv
```

输出说明：

- `submission_oof_blend.csv`：调试分析用（含概率与标签）
- `submission_oof_blend_strict.csv`：比赛提交用（`customer_id, loan_default`）

## 8. 全链路本地系统（新增）

### 执行顺序

```bash
python run_ingest_storage.py
python run_repair_pipeline.py
python run_decision_suite.py
python run_realtime_worker.py
python app.py
```

### 访问

- 看板首页：`http://127.0.0.1:5000/`
- 健康检查：`GET /health`
- 统计接口：`GET /stats/overview`
- 核心预测：`POST /predict/default`、`POST /predict/fraud`、`POST /predict/limit`

## 9. 技术栈强约束版（VM + Spark + Hive + MySQL + Python + Flask）

- VM 部署脚本：`deploy/vm/`
- Hive 建表：`sql/hive/create_tables.hql`
- MySQL 建表：`sql/mysql/create_tables.sql`
- 批处理作业：`jobs/batch/`
- 流处理作业：`jobs/streaming/`
- Flask 服务（双仓）：`service/flask/app.py`
- 验收脚本：`scripts/acceptance/run_all_checks.sh`
