项目目标技术栈：
- Spark
- Hive
- MySQL
- Python
- Flask

---

## 一、部署前准备

### 1. 虚拟机要求
- VMWare 虚拟机（建议 Ubuntu 22.04）
- 建议配置：4 核 CPU / 8GB 内存 / 80GB 磁盘
- 可联网（用于安装依赖）

### 2. 项目文件
请确保已获得完整项目目录，且包含以下关键目录与文件：
- `deploy/vm/`
- `sql/hive/create_tables.hql`
- `sql/mysql/create_tables.sql`
- `jobs/batch/`
- `jobs/streaming/`
- `service/flask/app.py`
- `scripts/acceptance/run_all_checks.sh`
- `docs/ACCEPTANCE_CHECKLIST.md`
- `docs/evidence/env_versions.md`

---

## 二、标准部署步骤

> 说明：以下命令均在项目根目录执行。

### 第 1 步：赋予脚本权限
```bash
chmod +x deploy/vm/*.sh
chmod +x jobs/streaming/run_streaming.sh
chmod +x scripts/acceptance/run_all_checks.sh
```

### 第 2 步：安装基础环境
```bash
bash deploy/vm/bootstrap.sh
bash deploy/vm/install_hadoop_spark_hive.sh
source /etc/profile.d/loan-bigdata.sh
export MYSQL_ROOT_PASSWORD="root123"
bash deploy/vm/install_mysql_python.sh
```

### 第 3 步：初始化存储与数据库
```bash
bash deploy/vm/init_hdfs_layout.sh
mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" < sql/mysql/create_tables.sql
hive -f sql/hive/create_tables.hql
```

### 第 4 步：安装 Python 依赖
```bash
python3 -m pip install -r requirements.txt
```

### 第 5 步：执行批处理链路
```bash
python run_ingest_storage.py
python run_repair_pipeline.py
python run_decision_suite.py
```

### 第 6 步：执行 Spark 数仓与修复任务
```bash
hdfs dfs -mkdir -p /data_lake/raw/input
hdfs dfs -put -f car_loan_train.csv /data_lake/raw/input/

spark-submit jobs/batch/preprocess_spark.py \
  --input-path /data_lake/raw/input/car_loan_train.csv \
  --output-table loan_dwd.loan_cleaned \
  --output-path /data_lake/cleaned/loan_cleaned

spark-submit jobs/batch/repair_fpgrowth_spark.py \
  --source-table loan_dwd.loan_cleaned \
  --output-table loan_dwd.loan_repaired_fp

spark-submit jobs/batch/repair_als_spark.py \
  --source-table loan_dwd.loan_repaired_fp \
  --output-table loan_dwd.loan_repaired_als

spark-submit jobs/batch/evaluate_repair.py \
  --source-table loan_dwd.loan_repaired_als \
  --mysql-url "jdbc:mysql://127.0.0.1:3306/loan_ods?useSSL=false&serverTimezone=UTC" \
  --mysql-user loan_user \
  --mysql-password loan_pass_123 \
  --output-json artifacts/spark_repair_metrics.json
```

### 第 7 步：安装 Sqoop（MySQL ↔ Hive 同步）

```bash
bash deploy/vm/install_sqoop.sh

# 验证安装：
sqoop version
```

### 第 8 步：执行 Sqoop Hive→MySQL 同步

```bash
bash deploy/vm/sqoop_export_hive_mysql.sh
```

### 第 9 步：启动 API 服务
```bash
python service/flask/app.py
```

访问地址：
- `http://127.0.0.1:5000/`

---

## 三、可选：启动实时流处理

新开一个终端执行：
```bash
bash jobs/streaming/run_streaming.sh
```

---

## 四、验收步骤（必须执行）

### 1. 运行一键验收脚本
```bash
bash scripts/acceptance/run_all_checks.sh
```

### 2. 补充证据文件
将关键命令输出与截图填写到：
- `docs/evidence/env_versions.md`

建议截图：
- `jps` 进程列表
- MySQL/Hive 库表查询结果
- HDFS `/data_lake` 目录结构

### 3. 对照验收清单打勾
- `docs/ACCEPTANCE_CHECKLIST.md`

---

## 五、常见问题

### 1) Hive 命令不可用
```bash
source /etc/profile.d/loan-bigdata.sh
```

### 2) Spark 写 MySQL 失败
- 检查 MySQL 是否启动
- 检查 JDBC 驱动是否可被 Spark 读取
- 检查账号 `loan_user` 权限

### 3) Flask 启动后接口报数据库连接错误
- 检查 MySQL/Hive 服务状态
- 检查连接参数是否与脚本默认值一致

### 4) 实时流无输出
- 检查输入目录是否持续有新文件
- 检查 checkpoint 目录权限

---

## 六、完成标准
当以下条件全部满足，即可判定“部署成功”：
- 技术栈服务可用（Spark/Hive/MySQL/Python/Flask）
- API 可访问且返回正常
- 看板可打开并展示数据
- 验收脚本执行完成
- 验收清单全部通过并有证据归档
