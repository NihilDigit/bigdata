# 气象大数据采集、分析与可视化系统

本项目是课程设计 MVP，实现唐山、北京、上海三个站点的气象数据采集、存储、计算和可视化展示。

## 数据来源

- 唐山当前温湿度：ESP32-C3 + DHT11，数据口 GPIO4，通过 USB 串口传入宿主机。
- 唐山、北京、上海历史数据：Open-Meteo Archive API，当前数据补充来自 Open-Meteo Forecast API。
- 历史范围：`2026-06-11` 至 `2026-06-17`，共 7 天、504 条小时记录。

## 大数据组件

大数据环境运行在 `ubuntu22` distrobox 中。默认假定参考大数据环境位于当前仓库上两级目录下的 `bigdata/`，也可以通过 `BIGDATA_ROOT` 和 `BIGDATA_ROOT_IN_CONTAINER` 覆盖：

- Hadoop/HDFS：历史 CSV 上传到 `/weathertextdb`
- Hive：外部表 `weather_table`
- Spark：统计结果输出到 `/weather_analysis`
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

该脚本会额外检查扩展 API、CSV 导出和 Next.js 两页渲染。

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
