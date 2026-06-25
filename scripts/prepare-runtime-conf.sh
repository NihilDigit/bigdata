#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/bigdata-env.sh"

mkdir -p "$HADOOP_CONF_DIR" "$HBASE_CONF_DIR" "$SPARK_CONF_DIR"

cp "$HADOOP_HOME/etc/hadoop/core-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/hdfs-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/yarn-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/mapred-site.xml" "$HADOOP_CONF_DIR/"
cp "$HADOOP_HOME/etc/hadoop/capacity-scheduler.xml" "$HADOOP_CONF_DIR/"
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
import xml.etree.ElementTree as ET
import re

root = Path(sys.argv[1])
host_java_home = sys.argv[2]
container_java_home = "/usr/lib/jvm/java-8-openjdk-amd64"

for path in root.rglob("*"):
    if path.is_file():
        text = path.read_text(errors="ignore")
        next_text = re.sub(r"/usr/lib/jvm/java-8-openjdk(?:-amd64)*", container_java_home, text)
        if host_java_home != "/usr/lib/jvm/java-8-openjdk":
            next_text = next_text.replace(host_java_home, container_java_home)
        if next_text != text:
            path.write_text(next_text)

yarn_site = root / "hadoop-conf" / "yarn-site.xml"
tree = ET.parse(yarn_site)
config = tree.getroot()
props = {prop.findtext("name"): prop for prop in config.findall("property")}

def set_prop(name: str, value: str) -> None:
    prop = props.get(name)
    if prop is None:
        prop = ET.SubElement(config, "property")
        ET.SubElement(prop, "name").text = name
        ET.SubElement(prop, "value").text = value
        props[name] = prop
        return
    value_node = prop.find("value")
    if value_node is None:
        value_node = ET.SubElement(prop, "value")
    value_node.text = value

set_prop("yarn.resourcemanager.hostname", "localhost")
set_prop("yarn.resourcemanager.address", "localhost:8032")
set_prop("yarn.resourcemanager.scheduler.address", "localhost:8030")
set_prop("yarn.resourcemanager.resource-tracker.address", "localhost:8031")
set_prop("yarn.resourcemanager.admin.address", "localhost:8033")
set_prop("yarn.resourcemanager.webapp.address", "localhost:8088")
ET.indent(tree, space="  ")
tree.write(yarn_site, encoding="unicode", xml_declaration=True)

hbase_site = root / "hbase-conf" / "hbase-site.xml"
hbase_tree = ET.parse(hbase_site)
hbase_config = hbase_tree.getroot()
hbase_props = {prop.findtext("name"): prop for prop in hbase_config.findall("property")}

def set_hbase_prop(name: str, value: str) -> None:
    prop = hbase_props.get(name)
    if prop is None:
        prop = ET.SubElement(hbase_config, "property")
        ET.SubElement(prop, "name").text = name
        ET.SubElement(prop, "value").text = value
        hbase_props[name] = prop
        return
    value_node = prop.find("value")
    if value_node is None:
        value_node = ET.SubElement(prop, "value")
    value_node.text = value

set_hbase_prop("hbase.zookeeper.property.admin.serverPort", "18080")
ET.indent(hbase_tree, space="  ")
hbase_tree.write(hbase_site, encoding="unicode", xml_declaration=True)

spark_env = root / "spark-conf" / "spark-env.sh"
spark_text = spark_env.read_text(errors="ignore")
spark_lines = [
    line
    for line in spark_text.splitlines()
    if not line.startswith("export YARN_CONF_DIR=") and not line.startswith("export HADOOP_CONF_DIR=")
]
spark_lines.append(f"export HADOOP_CONF_DIR={root / 'hadoop-conf'}")
spark_lines.append("export YARN_CONF_DIR=$HADOOP_CONF_DIR")
spark_env.write_text("\n".join(spark_lines) + "\n")
PY

echo "Runtime config prepared at $WEATHER_RUNTIME_DIR"
echo "HADOOP_CONF_DIR=$HADOOP_CONF_DIR"
echo "HBASE_CONF_DIR=$HBASE_CONF_DIR"
echo "SPARK_CONF_DIR=$SPARK_CONF_DIR"
