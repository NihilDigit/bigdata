# 气象大数据采集、分析与可视化系统

本项目实现唐山、北京、上海三个站点的气象数据采集、存储、计算和可视化展示。实现范围按 `设计文档.md` 组织：ESP32-C3 + DHT11 采集，TCP 采集服务，HBase/HDFS/Hive/Spark 数据链路，以及 FastAPI + Next.js 可视化。

## 数据来源

- 唐山当前温湿度：ESP32-C3 + DHT11，当前实物数据口为 GPIO4；正式演示走 Wi-Fi/TCP，USB 串口用于刷写、上传和调试。
- 唐山、北京、上海历史数据：Open-Meteo Archive API，当前数据补充来自 Open-Meteo Forecast API。
- 历史范围：`2026-06-11` 至 `2026-06-17`，共 7 天、504 条小时记录。

## 大数据组件

大数据环境运行在 `ubuntu22` distrobox 中。默认假定参考大数据环境位于当前仓库上两级目录下的 `bigdata/`，也可以通过 `BIGDATA_ROOT` 和 `BIGDATA_ROOT_IN_CONTAINER` 覆盖：

- Hadoop/HDFS：历史 CSV 上传到 `/weathertextdb`
- Hive：外部表 `weather_table`
- Spark：从 Hive 表读取数据，在 YARN 上计算 10 秒窗口均值，输出到 `/weather_analysis`，并兼容生成 `/weather_10secmean`
- HBase：当前三站数据写入 `realtime_weather`
- Web API：FastAPI，默认运行在 `http://127.0.0.1:8008`
- 前端：Next.js + shadcn/ui 风格组件 + Recharts，默认运行在 `http://127.0.0.1:3000`

## Web 演示

启动服务：

```bash
./scripts/run-web.sh
```

打开页面：

```text
http://127.0.0.1:3000
```

主要接口：

```text
/api/stations/current
/api/stations
/api/metrics
/api/stations/tangshan/live?seconds=150
/api/analysis/trends?metric=pressure&station_id=tangshan
/api/analysis/summary
/api/records?station_id=tangshan
/api/export/weather_observations.csv
```

前端包含两个页面：

- `总览`：地图、站点当前读数和五项指标。
- `详细数据`：站点筛选、指标筛选、趋势图、统计摘要、三站对比、记录表和 CSV 导出。

## ESP32 与采集服务

上传 ESP32 气象站程序：

```bash
ESP32_SSID=<热点名称> ESP32_WIFI_KEY=<热点密码> ./scripts/upload-esp32-weatherstation.sh
```

启动在线采集服务：

```bash
python backend/scripts/weather_dataserver.py --station-host <ESP32_IP>
```

采集服务接收 ESP32 的 TCP CSV 数据，合并 Open-Meteo 当前气压、风速、风向和天气代码，追加本地实时 CSV，并写入 HBase 和 HDFS。

前端总览页和详细数据页都会显示 `ESP32 实时采样` 区块。DHT11 本身为整数级温湿度传感器，因此页面用一位小数统一格式展示，同时显示毫秒级采样时间和 ESP32 递增样本号，用于证明实时数据正在更新。

## Hive 与 Spark

创建 Hive 外部表：

```bash
./scripts/create-hive-weather-table.sh
```

按设计文档路径在 YARN 上运行 Spark 分析：

```bash
./scripts/run-spark-analysis-yarn.sh
```

## MVP 验收

在服务启动后运行：

```bash
./scripts/verify-mvp.sh
```

该脚本会检查本地真实数据文件、FastAPI 接口、HDFS 输入目录、Spark 输出目录和 HBase 当前表。

完整版验收：

```bash
./scripts/verify-full.sh
```

连接 ESP32 实机时可让验收脚本先刷新实时 HDFS/HBase 数据：

```bash
ESP32_STATION_HOST=<ESP32_IP> ./scripts/verify-full.sh
```

该脚本会额外检查设计覆盖入口、扩展 API、CSV 导出和 Next.js 两页渲染。

## 报告

同步维护的 Markdown 报告位于：

```text
reports/实验报告.md
```

生成可浏览、可打印的 HTML 报告：

```bash
python scripts/build-report-html.py reports/实验报告.md reports/实验报告.html
```

过程截图位于：

```text
reports/assets/
```
