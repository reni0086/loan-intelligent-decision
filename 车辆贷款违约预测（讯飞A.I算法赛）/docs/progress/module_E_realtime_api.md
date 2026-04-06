# 模块 E：实时处理与 API

## 模块目标
实现本地实时微批处理服务、统一 Flask API 与监控指标输出。

## 已完成功能
- Flask API 已实现：
  - `/health`
  - `/predict/default`
  - `/predict/fraud`
  - `/predict/limit`
  - `/score/credit`
  - `/repair/record`
  - `/stats/overview`
- 微批处理：
  - 从 `realtime_queue.jsonl` 消费入库。
  - 调用三类模型推理并写入 `realtime_decisions`。
- 监控：
  - 输出 `monitoring/metrics.log`（批次耗时、吞吐等）。

## 实现方式
- 代码路径：
  - `src/realtime_api.py`
  - `run_realtime_worker.py`
  - `app.py`
- 数据流：
  - `queue -> realtime_events -> 预测 -> realtime_decisions -> metrics.log`

## 验证结果
- `run_realtime_worker.py` 执行成功，处理 1000 条记录。
- Flask 测试客户端调用 `/health` 和 `/stats/overview` 均返回 200。

## 未完成项
- WebSocket 推送与生产级告警系统（当前为日志监控）。

## 风险与下一步
- 风险：本地 SQLite 并发能力有限。
- 下一步：进入模块 F，实现可视化看板联动。
