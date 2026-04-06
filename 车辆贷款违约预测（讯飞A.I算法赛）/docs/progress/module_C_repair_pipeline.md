# 模块 C：数据处理与智能修复

## 模块目标
实现预处理与缺失信息智能修复，覆盖类别与数值特征两类场景，并给出对照评估结果。

## 已完成功能
- 规则修复（FP-growth 风格）：
  - 通过离散化 + 关联规则提取进行类别特征修复。
  - 输出置信度并统计覆盖率、准确率。
- 协同过滤修复（ALS 风格）：
  - 基于矩阵分解对数值缺失进行填补。
  - 评估 RMSE 和 MAPE。
- 修复结果落地：
  - 生成 `data_lake/featured/train_repaired.csv`。
  - 生成 `artifacts/repair_evaluation.json` 与 `artifacts/repair_report.txt`。

## 实现方式
- 代码路径：
  - `src/repair.py`
  - `run_repair_pipeline.py`
- 数据流：
  - `cleaned/train_cleaned.csv -> repair -> featured/train_repaired.csv`
  - 同步生成评估指标 JSON/TXT。

## 验证结果
- `run_repair_pipeline.py` 执行成功。
- 修复与评估报告文件已生成。

## 未完成项
- 分布式 Spark MLlib 版本 FP-Growth/ALS（当前为本地实现）。

## 风险与下一步
- 风险：本地矩阵分解复杂度对超大数据规模敏感。
- 下一步：进入模块 D，完成决策子模块全套实现。
