#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BIGDATA_ROOT="$(cd "$PROJECT_ROOT/../.." && pwd)/bigdata"
BIGDATA_ROOT="${BIGDATA_ROOT:-$DEFAULT_BIGDATA_ROOT}"

JAVA8_HOME="${JAVA8_HOME:-/usr/lib/jvm/java-8-openjdk}"
if [[ ! -x "$JAVA8_HOME/bin/java" ]]; then
  echo "Java 8 not found at $JAVA8_HOME" >&2
  exit 1
fi

export JAVA_HOME="$JAVA8_HOME"
export HADOOP_HOME="${HADOOP_HOME:-$BIGDATA_ROOT/experiment3/hadoop}"
export HBASE_HOME="${HBASE_HOME:-$BIGDATA_ROOT/experiment4/hbase}"
export HIVE_HOME="${HIVE_HOME:-$BIGDATA_ROOT/experiment6/hive}"
export SPARK_HOME="${SPARK_HOME:-$BIGDATA_ROOT/experiment7/spark}"

export WEATHER_RUNTIME_DIR="${WEATHER_RUNTIME_DIR:-$PROJECT_ROOT/.runtime}"
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-$WEATHER_RUNTIME_DIR/hadoop-conf}"
export YARN_CONF_DIR="${YARN_CONF_DIR:-$HADOOP_CONF_DIR}"
export HBASE_CONF_DIR="${HBASE_CONF_DIR:-$WEATHER_RUNTIME_DIR/hbase-conf}"
export SPARK_CONF_DIR="${SPARK_CONF_DIR:-$WEATHER_RUNTIME_DIR/spark-conf}"

export PATH="$SPARK_HOME/bin:$HIVE_HOME/bin:$HBASE_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH"

export WEATHER_PROJECT_ROOT="$PROJECT_ROOT"
export WEATHER_DATA_DIR="${WEATHER_DATA_DIR:-$PROJECT_ROOT/data}"
export WEATHER_REPORT_ASSETS="${WEATHER_REPORT_ASSETS:-$PROJECT_ROOT/reports/assets}"
