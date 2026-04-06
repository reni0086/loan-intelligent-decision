# 模块 D：智能决策模块

## 模块目标
补齐违约预测、欺诈检测、额度预测、信用评分四个决策子模块，并形成模型注册信息。

## 已完成功能
- 违约预测：XGBoost 二分类模型（含 AUC/Precision/Recall/F1）。
- 欺诈检测：构造启发式欺诈标签并训练二分类模型。
- 额度预测：随机森林、GBR、XGBoost 回归对比并自动选优。
- 信用评分：将违约概率映射至 300-850 分区间。
- 模型注册：
  - 输出 `artifacts/model_registry.json`。
  - 输出 `default_model.joblib`、`fraud_model.joblib`、`limit_model.joblib`。

## 实现方式
- 代码路径：
  - `src/decision.py`
  - `run_decision_suite.py`
- 数据流：
  - `featured/train_repaired.csv -> 训练/评估 -> artifacts/*.joblib + model_registry.json`

## 验证结果
- `run_decision_suite.py` 执行成功并输出模型注册文件。

## 未完成项
- SHAP 细粒度解释图（当前仅具备模型级指标和评分结果）。

## 风险与下一步
- 风险：欺诈标签为弱监督构造，后续建议替换为真实标注。
- 下一步：进入模块 E，接入实时微批与 API 服务。
