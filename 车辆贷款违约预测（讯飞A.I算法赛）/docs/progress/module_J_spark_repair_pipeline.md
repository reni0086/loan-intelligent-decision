# 模块 J：Spark 修复流水线

## 模块目标
实现 Spark 预处理、FP-Growth 修复、ALS 修复与修复评估入仓。

## 已完成功能
- `jobs/batch/preprocess_spark.py`
- `jobs/batch/repair_fpgrowth_spark.py`
- `jobs/batch/repair_als_spark.py`
- `jobs/batch/evaluate_repair.py`

## 实现方式
- 使用 Spark SQL + MLlib 执行清洗与修复。
- 评估结果写入 Hive ADS 与 MySQL 报表表。

## 未完成项
- 需在 VM 上提交运行并沉淀真实评估截图。
