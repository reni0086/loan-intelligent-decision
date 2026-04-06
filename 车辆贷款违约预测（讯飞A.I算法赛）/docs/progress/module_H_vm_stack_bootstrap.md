# 模块 H：VM 技术栈基础环境

## 模块目标
在 VMWare 虚拟机内完成 Spark/Hive/MySQL/Python/Flask 环境安装与版本验收。

## 已完成功能
- 新增 VM 部署脚本：
  - `deploy/vm/bootstrap.sh`
  - `deploy/vm/install_hadoop_spark_hive.sh`
  - `deploy/vm/install_mysql_python.sh`
  - `deploy/vm/init_hdfs_layout.sh`
- 新增环境证据模板：
  - `docs/evidence/env_versions.md`

## 实现方式
- 通过 Shell 脚本固化安装流程，降低人工配置差异。
- 通过证据模板统一验收输出。

## 未完成项
- 需在客户 VM 实际执行脚本并粘贴版本输出证据。
