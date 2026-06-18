#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/bigdata-env.sh"

mkdir -p "$HADOOP_CONF_DIR" "$HBASE_CONF_DIR" "$SPARK_CONF_DIR"

cp "$HADOOP_HOME/etc/hadoop/core-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/hdfs-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/yarn-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/mapred-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/workers" "$HADOOP_CONF_DIR/" 2>/dev/null || true
cp "$HADOOP_HOME/etc/hadoop/hadoop-env.sh" "$HADOOP_CONF_DIR/"

cp "$HBASE_HOME/conf/hbase-site.xml" "$HBASE_CONF_DIR/"
cp "$HBASE_HOME/conf/hbase-env.sh" "$HBASE_CONF_DIR/"
cp "$HBASE_HOME/conf/regionservers" "$HBASE_CONF_DIR/" 2>/dev/null || true
cp "$HBASE_HOME/conf/backup-masters" "$HBASE_CONF_DIR/" 2>/dev/null || true

cp "$SPARK_HOME/conf/spark-env.sh" "$SPARK_CONF_DIR/"
cp "$SPARK_HOME/conf/spark-defaults.conf" "$SPARK_CONF_DIR/"
cp "$SPARK_HOME/conf/log4j2.properties" "$SPARK_CONF_DIR/" 2>/dev/null || true

python - <<'PY' "$WEATHER_RUNTIME_DIR" "$JAVA_HOME"
from pathlib import Path
import sys

root = Path(sys.argv[1])
java_home = sys.argv[2]
old = "/usr/lib/jvm/java-8-openjdk-amd64"

for path in root.rglob("*"):
    if path.is_file():
        text = path.read_text(errors="ignore")
        if old in text:
            path.write_text(text.replace(old, java_home))
PY

echo "Runtime config prepared at $WEATHER_RUNTIME_DIR"
echo "HADOOP_CONF_DIR=$HADOOP_CONF_DIR"
echo "HBASE_CONF_DIR=$HBASE_CONF_DIR"
echo "SPARK_CONF_DIR=$SPARK_CONF_DIR"
