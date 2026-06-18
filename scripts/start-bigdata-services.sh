#!/usr/bin/env bash
set -euo pipefail

"$(dirname "${BASH_SOURCE[0]}")/distro-bigdata.sh" '
echo "Starting HDFS"
hdfs --daemon start namenode || true
hdfs --daemon start datanode || true
hdfs --daemon start secondarynamenode || true

echo "Starting YARN"
yarn --daemon start resourcemanager || true
yarn --daemon start nodemanager || true

echo "Waiting for HDFS"
for i in $(seq 1 20); do
  if hdfs dfs -ls / >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Ensuring HDFS directories"
hdfs dfs -mkdir -p /weathertextdb /weather_analysis /tmp/hive /user/hive/warehouse /hbase /spark/jars
hdfs dfs -chmod -R 777 /tmp/hive /user/hive/warehouse

if ! hdfs dfs -test -e /spark/jars/spark-core_2.12-3.5.1.jar; then
  echo "Uploading Spark jars to HDFS"
  hdfs dfs -put -f "$SPARK_HOME"/jars/*.jar /spark/jars/
fi

echo "Starting HBase"
hbase-daemon.sh start zookeeper || true
hbase-daemon.sh start master || true
hbase-daemon.sh start regionserver || true
hbase-daemon.sh start thrift -p 9090 || true

echo "Current Java processes"
jps
'
