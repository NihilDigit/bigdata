#!/usr/bin/env bash
set -euo pipefail

"$(dirname "${BASH_SOURCE[0]}")/distro-bigdata.sh" '
echo "PWD=$PWD"
echo "JAVA_HOME=$JAVA_HOME"
"$JAVA_HOME/bin/java" -version 2>&1 | sed -n "1,3p"

echo
echo "Hadoop:"
hadoop version | sed -n "1,4p"

echo
echo "HBase:"
hbase version | sed -n "1,6p"

echo
echo "Hive:"
hive --version 2>&1 | grep -E "^Hive " | head -1

echo
echo "Spark:"
spark-submit --version 2>&1 | sed -n "1,8p"
'
