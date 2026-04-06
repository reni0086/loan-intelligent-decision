# 模块 K：Python + Flask 服务升级（接入 Hive/MySQL）

## 模块目标
将服务层升级为双仓访问架构，满足 Flask + Python + Hive + MySQL 组合。

## 已完成功能
- 服务入口：`service/flask/app.py`
- 路由：`service/flask/routes/predict.py`、`service/flask/routes/stats.py`
- 数据访问层：
  - `service/flask/repositories/mysql_repo.py`
  - `service/flask/repositories/hive_repo.py`
- 模型加载：
  - `service/flask/model_loader.py`
- Hive 训练脚本：
  - `jobs/batch/train_from_hive.py`

## 实现方式
- 在线查询写 MySQL，离线统计读 Hive。
- Flask 提供预测、评分、统计接口。

## 未完成项
- 客户环境需要配置 Hive Thrift 与 MySQL 白名单。
