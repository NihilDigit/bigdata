#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <command...>" >&2
  exit 2
fi

cmd="$*"

distrobox enter ubuntu22 -- bash -lc "
set -euo pipefail
cd \"\${BIGDATA_ROOT_IN_CONTAINER:-\$HOME/Codes/bigdata}\"
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
export HADOOP_HOME=\$PWD/experiment3/hadoop
export HBASE_HOME=\$PWD/experiment4/hbase
export HIVE_HOME=\$PWD/experiment6/hive
export SPARK_HOME=\$PWD/experiment7/spark
export HADOOP_CONF_DIR=\$HADOOP_HOME/etc/hadoop
export YARN_CONF_DIR=\$HADOOP_HOME/etc/hadoop
export HBASE_CONF_DIR=\$HBASE_HOME/conf
export SPARK_CONF_DIR=\$SPARK_HOME/conf
export HADOOP_MAPRED_HOME=\$HADOOP_HOME
export LOCAL_DIRS=/tmp
export SPARK_LOCAL_DIRS=/tmp
export PATH=\$SPARK_HOME/bin:\$HIVE_HOME/bin:\$HBASE_HOME/bin:\$HADOOP_HOME/bin:\$HADOOP_HOME/sbin:\$PATH
$cmd
"
