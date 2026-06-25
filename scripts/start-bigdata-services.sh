#!/usr/bin/env bash
set -euo pipefail

"$(dirname "${BASH_SOURCE[0]}")/prepare-runtime-conf.sh"

"$(dirname "${BASH_SOURCE[0]}")/distro-bigdata.sh" '
daemon_running() {
  jps | awk "{print \$2}" | grep -qx "$1"
}

start_hdfs_daemon() {
  local process="$1"
  local daemon="$2"
  if daemon_running "$process"; then
    echo "$process already running"
    return
  fi
  hdfs --daemon start "$daemon"
}

start_yarn_daemon() {
  local process="$1"
  local daemon="$2"
  if daemon_running "$process"; then
    echo "$process already running"
    return
  fi
  nohup yarn "$daemon" >/tmp/weather-yarn-"$daemon".log 2>&1 &
}

start_hbase_daemon() {
  local process="$1"
  local daemon="$2"
  shift 2
  if daemon_running "$process"; then
    echo "$process already running"
    return
  fi
  hbase-daemon.sh start "$daemon" "$@"
}

echo "Starting HDFS"
start_hdfs_daemon NameNode namenode
start_hdfs_daemon DataNode datanode
start_hdfs_daemon SecondaryNameNode secondarynamenode

echo "Starting YARN"
start_yarn_daemon ResourceManager resourcemanager
start_yarn_daemon NodeManager nodemanager

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
start_hbase_daemon HQuorumPeer zookeeper
start_hbase_daemon HMaster master
start_hbase_daemon HRegionServer regionserver
start_hbase_daemon ThriftServer thrift -p 9090

echo "Current Java processes"
jps
'
