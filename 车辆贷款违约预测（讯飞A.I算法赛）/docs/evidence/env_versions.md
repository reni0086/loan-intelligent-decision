# 环境版本验收证据（VM）

> 在虚拟机中执行下列命令，并把输出粘贴到本文件。

## 1) Java / Python / Flask
```bash
java -version
python3 --version
python3 -c "import flask; print(flask.__version__)"
```

## 2) MySQL
```bash
mysql --version
mysql -uroot -p -e "SHOW DATABASES;"
```

## 3) Hadoop / HDFS
```bash
hadoop version
hdfs dfs -ls /
```

## 4) Spark
```bash
spark-submit --version
pyspark --version
```

## 5) Hive
```bash
hive --version
hive -e "SHOW DATABASES;"
```

## 6) 进程状态
```bash
jps
systemctl status mysql --no-pager
```

## 7) 证据截图说明
- 截图1：`jps` 输出（NameNode/DataNode/Spark/Hive 服务）
- 截图2：`SHOW DATABASES` 和 `SHOW TABLES`
- 截图3：`hdfs dfs -ls /data_lake`
