# 模块 I：HDFS/Hive/MySQL 数仓建模与同步

## 模块目标
完成 HDFS 分层布局、Hive 建库建表、MySQL 业务表设计及 Hive↔MySQL 同步作业。

## 已完成功能
- Hive 脚本：`sql/hive/create_tables.hql`
- MySQL 脚本：`sql/mysql/create_tables.sql`
- 同步作业：`jobs/batch/sync_hive_mysql.py`
- HDFS 初始化：`deploy/vm/init_hdfs_layout.sh`

## 实现方式
- Hive 分层：ODS/DWD/ADS（Parquet）
- MySQL 分层：ODS/RT 业务表
- Spark JDBC 实现 Hive -> MySQL 与 MySQL -> Hive 汇总写回

## 未完成项
- 需在客户 VM 中完成 JDBC 驱动放置与连通性验证。
