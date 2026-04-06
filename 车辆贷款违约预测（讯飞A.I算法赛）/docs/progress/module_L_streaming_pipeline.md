# 模块 L：Spark Structured Streaming 实时评分

## 模块目标
实现 Spark Structured Streaming 实时评分并写入 MySQL。

## 已完成功能
- 打分流作业：`jobs/streaming/realtime_score_spark.py`
- 入库流作业：`jobs/streaming/realtime_to_mysql.py`
- 启动脚本：`jobs/streaming/run_streaming.sh`

## 实现方式
- 文件流读取实时数据，微批推理，产出实时评分 Parquet。
- 通过第二个流作业将评分结果写入 MySQL 实时表。

## 未完成项
- 若客户要求 Kafka，可将输入源替换为 Kafka Source。
