# 验收清单（技术栈强约束）

## A. 技术栈合规验收
- [ ] 运行在 VMWare 虚拟机
- [ ] Spark 可用（`spark-submit --version`）
- [ ] Hive 可用（`hive --version`）
- [ ] MySQL 可用（`mysql --version`）
- [ ] Python 可用（`python3 --version`）
- [ ] Flask 可用（`GET /health` 返回 200）

## B. 数据链路验收
- [ ] HDFS 存在 `/data_lake/raw|cleaned|featured|model`
- [ ] Hive 库 `loan_ods/loan_dwd/loan_ads` 已创建
- [ ] MySQL 库 `loan_ods/loan_rt` 已创建
- [ ] Hive -> MySQL 同步作业可跑通
- [ ] MySQL -> Hive 汇总写入 `loan_ads.risk_daily_summary`

## C. 算法与修复验收
- [ ] Spark 预处理作业成功
- [ ] FP-Growth 修复作业成功
- [ ] ALS 修复作业成功
- [ ] 修复评估写入 Hive 与 MySQL

## D. 服务与看板验收
- [ ] Flask 预测接口可用：`/predict/default` `/predict/fraud` `/predict/limit`
- [ ] 统计接口可用：`/stats/overview` `/stats/risk_daily`
- [ ] 看板首页可访问并展示实时统计

## E. 实时流验收
- [ ] Structured Streaming 打分作业可运行
- [ ] 实时入库作业可写入 MySQL `realtime_decisions`
- [ ] 至少 1 次端到端实时样例验证成功

## F. 交付文档验收
- [ ] `PROJECT_STATUS.md`
- [ ] `docs/progress/module_*.md`
- [ ] `DELIVERY_CLIENT_V2.md`
- [ ] `docs/evidence/env_versions.md`
