#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <command...>" >&2
  exit 2
fi

cmd="$*"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

distrobox enter ubuntu22 -- bash -lc "
set -euo pipefail
cd \"\${BIGDATA_ROOT_IN_CONTAINER:-\$HOME/Codes/bigdata}\"
export WEATHER_PROJECT_ROOT='$PROJECT_ROOT'
export WEATHER_RUNTIME_DIR=\"\$WEATHER_PROJECT_ROOT/.runtime\"
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
export HADOOP_HOME=\$PWD/experiment3/hadoop
export HBASE_HOME=\$PWD/experiment4/hbase
export HIVE_HOME=\$PWD/experiment6/hive
export SPARK_HOME=\$PWD/experiment7/spark
export HADOOP_CONF_DIR=\"\$WEATHER_RUNTIME_DIR/hadoop-conf\"
export YARN_CONF_DIR=\"\$HADOOP_CONF_DIR\"
export HBASE_CONF_DIR=\"\$WEATHER_RUNTIME_DIR/hbase-conf\"
export SPARK_CONF_DIR=\"\$WEATHER_RUNTIME_DIR/spark-conf\"
export HADOOP_MAPRED_HOME=\$HADOOP_HOME
export LOCAL_DIRS=/tmp
export SPARK_LOCAL_DIRS=/tmp
export PATH=\$SPARK_HOME/bin:\$HIVE_HOME/bin:\$HBASE_HOME/bin:\$HADOOP_HOME/bin:\$HADOOP_HOME/sbin:\$PATH
$cmd
"
