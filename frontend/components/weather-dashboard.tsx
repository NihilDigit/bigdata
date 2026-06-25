"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  BarChart3,
  Cloud,
  CloudDrizzle,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  Download,
  RefreshCw,
  Sun,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

type ViewName = "overview" | "detail" | "analysis";
type MetricKey = "temperature" | "humidity" | "pressure" | "wind_speed" | "wind_direction";

type StationCurrent = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  time: string;
  temperature: number;
  humidity: number;
  pressure: number;
  wind_speed: number;
  wind_direction: number;
  weather_code: number;
};

type Metric = {
  id: MetricKey;
  name: string;
  unit: string;
};

type Summary = {
  station_id: string;
  station_name: string;
  records: number;
  avg_temperature: number;
  min_temperature: number;
  max_temperature: number;
  avg_humidity: number;
  avg_pressure: number;
  avg_wind_speed: number;
  pressure_delta: number;
  max_wind_speed: number;
  dominant_wind_direction: number;
};

type WeatherRow = {
  collect_time: string;
  station_id: string;
  station_name: string;
  temperature: number;
  humidity: number;
  pressure: number;
  wind_speed: number;
  wind_direction: number;
  weather_code: number;
  sample_seq?: number;
};

type DashboardData = {
  metrics: Metric[];
  current: StationCurrent[];
  summary: Summary[];
  records: WeatherRow[];
  meta: {
    historical_range: { start_date: string; end_date: string };
    record_count: number;
    spark_completed_at: string | null;
  };
};

type SparkJobStatus = {
  job_id: string | null;
  status: "idle" | "running" | "succeeded" | "failed";
  message: string;
  started_at?: string | null;
  completed_at?: string | null;
  exit_code?: number | null;
  pid?: number | null;
  application_id?: string;
  progress_percent?: number;
  progress_label?: string;
  tracking_url?: string;
  log_tail?: string[];
};

const stationOrder = ["tangshan", "beijing", "shanghai"];
const refreshIntervalMs = 1000;
const stationLabelOffset: Record<string, { x: string; y: string }> = {
  beijing: { x: "-150px", y: "-82px" },
  tangshan: { x: "20px", y: "-58px" },
  shanghai: { x: "34px", y: "20px" },
};

const mapFrame = {
  width: 1023,
  height: 1149,
};

const stationMapAnchor: Record<string, { x: number; y: number }> = {
  beijing: { x: 688, y: 376 },
  tangshan: { x: 718, y: 386 },
  shanghai: { x: 820, y: 526 },
};

const metricColors: Record<MetricKey, string> = {
  temperature: "var(--metric-temperature)",
  humidity: "var(--metric-humidity)",
  pressure: "var(--metric-pressure)",
  wind_speed: "var(--metric-wind-speed)",
  wind_direction: "var(--metric-wind-direction)",
};

const stationColors: Record<string, string> = {
  tangshan: "var(--primary)",
  beijing: "var(--metric-temperature)",
  shanghai: "var(--metric-humidity)",
};

const metricReadouts: Array<[MetricKey, string, string, number]> = [
  ["temperature", "温度", "°C", 1],
  ["humidity", "湿度", "%", 0],
  ["pressure", "气压", "hPa", 2],
  ["wind_speed", "风速", "m/s", 1],
  ["wind_direction", "风向", "°", 0],
];

function stationMapPosition(station: Pick<StationCurrent, "id">) {
  const { x, y } = stationMapAnchor[station.id];
  return {
    left: `${((x / mapFrame.width) * 100).toFixed(2)}%`,
    top: `${((y / mapFrame.height) * 100).toFixed(2)}%`,
  };
}

function formatNumber(value: unknown, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "暂无";
  return number.toFixed(digits).replace(/\.0$/, "");
}

function directionLabel(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "暂无";
  const labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return labels[Math.round(number / 22.5) % 16];
}

function weatherLabel(code: number) {
  if (code === 0) return "晴";
  if ([1, 2, 3].includes(code)) return "多云";
  if ([45, 48].includes(code)) return "雾";
  if ([51, 53, 55].includes(code)) return "毛毛雨";
  if ([61, 63, 65, 80, 81, 82].includes(code)) return "雨";
  if ([71, 73, 75, 77].includes(code)) return "雪";
  if ([95, 96, 99].includes(code)) return "雷暴";
  return "天气";
}

function WeatherIcon({ code, className }: { code: number; className?: string }) {
  const props = { className: cn("h-5 w-5", className), "aria-hidden": true };
  if (code === 0) return <Sun {...props} />;
  if ([1, 2, 3].includes(code)) return <CloudSun {...props} />;
  if ([51, 53, 55].includes(code)) return <CloudDrizzle {...props} />;
  if ([61, 63, 65, 80, 81, 82].includes(code)) return <CloudRain {...props} />;
  if ([71, 73, 75, 77].includes(code)) return <CloudSnow {...props} />;
  if ([95, 96, 99].includes(code)) return <CloudLightning {...props} />;
  return <Cloud {...props} />;
}

function formatClock(value: string | undefined) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("zh-CN", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function sparkComputedDescription(value: string | null | undefined) {
  return `上次计算 ${formatClock(value ?? undefined)}`;
}

function toWeatherRow(row: Record<string, unknown>): WeatherRow {
  return {
    collect_time: String(row.collect_time ?? ""),
    station_id: String(row.station_id ?? ""),
    station_name: String(row.station_name ?? ""),
    temperature: Number(row.temperature),
    humidity: Number(row.humidity),
    pressure: Number(row.pressure),
    wind_speed: Number(row.wind_speed),
    wind_direction: Number(row.wind_direction),
    weather_code: Number(row.weather_code),
    sample_seq: row.sample_seq == null || row.sample_seq === "" ? undefined : Number(row.sample_seq),
  };
}

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
  return (await response.json()) as T;
}

async function fetchDashboard(): Promise<DashboardData> {
  const [current, metrics, summary, records, sparkStatus] = await Promise.all([
    readJson<StationCurrent[]>("/api/stations/current"),
    readJson<Metric[]>("/api/metrics"),
    readJson<Summary[]>("/api/analysis/summary"),
    readJson<Array<Record<string, unknown>>>("/api/hourly"),
    readJson<SparkJobStatus>("/api/analysis/refresh/status").catch(() => null),
  ]);
  const normalizedRecords = records.map(toWeatherRow);
  const times = normalizedRecords.map((row) => row.collect_time).sort();
  return {
    metrics,
    current,
    summary,
    records: normalizedRecords,
    meta: {
      historical_range: {
        start_date: times[0]?.slice(0, 10) ?? "暂无",
        end_date: times.at(-1)?.slice(0, 10) ?? "暂无",
      },
      record_count: normalizedRecords.length,
      spark_completed_at: sparkStatus?.completed_at ?? null,
    },
  };
}

async function fetchLiveRows(stationId: string): Promise<WeatherRow[]> {
  const rows = await readJson<Array<Record<string, unknown>>>(`/api/stations/${stationId}/live?seconds=150`);
  return rows.map(toWeatherRow);
}

async function fetchHdfsRows(stationId: string): Promise<WeatherRow[]> {
  const suffix = stationId === "all" ? "" : `&station_id=${stationId}`;
  const rows = await readJson<Array<Record<string, unknown>>>(`/api/hdfs/records?limit=120${suffix}`);
  return rows.map(toWeatherRow);
}

function Shell({
  view,
  status,
  onRefresh,
  children,
}: {
  view: ViewName;
  status: string;
  onRefresh: () => void;
  children: React.ReactNode;
}) {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="m-0 text-xl font-semibold tracking-normal">气象大数据计算与可视化系统</h1>
        </div>
        <nav className="view-tabs" aria-label="页面视图">
          <Link className={cn("tab-link", view === "overview" && "active")} href="/">
            总览
          </Link>
          <Link className={cn("tab-link", view === "detail" && "active")} href="/detail">
            详情
          </Link>
          <Link className={cn("tab-link", view === "analysis" && "active")} href="/analysis">
            对比分析
          </Link>
        </nav>
        <Button variant="outline" size="icon" onClick={onRefresh} aria-label="刷新数据" title="刷新数据">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </header>
      {status ? <div className="status-line">{status}</div> : null}
      {children}
    </main>
  );
}

export function WeatherDashboard({ view }: { view: ViewName }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [liveRows, setLiveRows] = useState<WeatherRow[]>([]);
  const [hdfsRows, setHdfsRows] = useState<WeatherRow[]>([]);
  const [selectedStation, setSelectedStation] = useState("tangshan");
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>("temperature");
  const [recordStation, setRecordStation] = useState("all");
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextData, nextLive] = await Promise.all([fetchDashboard(), fetchLiveRows(selectedStation)]);
      setData(nextData);
      setLiveRows(nextLive);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? `数据读取失败：${error.message}` : "数据读取失败");
    }
  }, [selectedStation]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void load();
    }, refreshIntervalMs);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (view !== "analysis") return undefined;
    const loadHdfsRows = () => {
      fetchHdfsRows(recordStation)
        .then(setHdfsRows)
        .catch((error) => {
          setStatus(error instanceof Error ? `HDFS 数据读取失败：${error.message}` : "HDFS 数据读取失败");
        });
    };
    loadHdfsRows();
    const timer = window.setInterval(loadHdfsRows, 2000);
    return () => window.clearInterval(timer);
  }, [view, recordStation]);

  const current = data?.current.find((item) => item.id === selectedStation) ?? data?.current[0];
  const historyRows = useMemo(
    () => data?.records.filter((item) => item.station_id === selectedStation) ?? [],
    [data, selectedStation],
  );

  if (!data || !current) {
    return (
      <Shell view={view} status={status} onRefresh={load}>
        <Card className="grid min-h-[520px] place-items-center p-6 text-sm text-[color:var(--muted-foreground)]">
          读取站点数据
        </Card>
      </Shell>
    );
  }

  return (
    <Shell view={view} status={status} onRefresh={load}>
      {view === "overview" ? (
        <Overview
          data={data}
          selected={current}
          selectedStation={selectedStation}
          onStationChange={setSelectedStation}
        />
      ) : null}
      {view === "detail" ? (
        <Detail
          data={data}
          liveRows={liveRows}
          historyRows={historyRows}
          selectedStation={selectedStation}
          selectedMetric={selectedMetric}
          onStationChange={setSelectedStation}
          onMetricChange={setSelectedMetric}
        />
      ) : null}
      {view === "analysis" ? (
        <Analysis
          data={data}
          selectedMetric={selectedMetric}
          recordStation={recordStation}
          hdfsRows={hdfsRows}
          onMetricChange={setSelectedMetric}
          onRecordStationChange={setRecordStation}
          onRefresh={load}
        />
      ) : null}
    </Shell>
  );
}

function Overview({
  data,
  selected,
  selectedStation,
  onStationChange,
}: {
  data: DashboardData;
  selected: StationCurrent;
  selectedStation: string;
  onStationChange: (station: string) => void;
}) {
  const range = data.meta.historical_range;
  return (
    <div className="overview-layout">
      <Card className="overview-map-card p-5">
        <CardHeader>
          <div>
            <CardTitle>三站实时概览</CardTitle>
            <CardDescription>
              历史小时序列 {range.start_date} 至 {range.end_date}，共 {data.meta.record_count} 条
            </CardDescription>
          </div>
        </CardHeader>
        <div className="map-stage">
          <div className="map-canvas">
            <svg
              className="china-map"
              viewBox={`0 0 ${mapFrame.width} ${mapFrame.height}`}
              role="img"
              aria-label="由标准地图服务系统中国地图图片单色化得到的中国地图轮廓，站点按轮廓图校准定位"
            >
              <image
                className="map-raster"
                href="/maps/china-standard-outline-mono.png"
                x="0"
                y="0"
                width={mapFrame.width}
                height={mapFrame.height}
                preserveAspectRatio="xMidYMin meet"
              />
            </svg>
            {stationOrder.map((id) => {
              const station = data.current.find((item) => item.id === id);
              if (!station) return null;
              const position = stationMapPosition(station);
              const labelOffset = stationLabelOffset[id];
              return (
                <button
                  key={id}
                  type="button"
                  className={cn("station-marker", `station-${id}`, id === selectedStation && "selected")}
                  style={{
                    left: position.left,
                    top: position.top,
                    ["--label-x" as string]: labelOffset.x,
                    ["--label-y" as string]: labelOffset.y,
                    ["--station-color" as string]: stationColors[id],
                  }}
                  onClick={() => onStationChange(id)}
                >
                  <span className="marker-dot" />
                  <span className="marker-label">
                    <span className="flex items-center gap-1.5">
                      <WeatherIcon code={station.weather_code} />
                      <strong>{station.name}</strong>
                    </span>
                    <span>
                      {formatNumber(station.temperature)} °C · {weatherLabel(station.weather_code)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      <Card className="station-card overview-station-card">
        <div className="station-card-main">
          <div>
            <h2>{selected.name}</h2>
            <div className="weather-state">
              <WeatherIcon code={selected.weather_code} />
              <span>{weatherLabel(selected.weather_code)}</span>
            </div>
            <strong>{formatNumber(selected.temperature)}°C</strong>
          </div>
        </div>
        <div className="metric-grid">
          {metricReadouts.map(([key, label, unit, digits]) => (
            <article key={key} className="metric-readout" style={{ ["--metric-color" as string]: metricColors[key] }}>
              <strong>
                {formatNumber(selected[key], digits)}
                <small>{unit}</small>
              </strong>
              <span>
                {label}
                {key === "wind_direction" ? <em>{directionLabel(selected[key])}</em> : null}
              </span>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Detail({
  data,
  liveRows,
  historyRows,
  selectedStation,
  selectedMetric,
  onStationChange,
  onMetricChange,
}: {
  data: DashboardData;
  liveRows: WeatherRow[];
  historyRows: WeatherRow[];
  selectedStation: string;
  selectedMetric: MetricKey;
  onStationChange: (station: string) => void;
  onMetricChange: (metric: MetricKey) => void;
}) {
  const currentStation = data.current.find((item) => item.id === selectedStation);
  const currentMetric = data.metrics.find((item) => item.id === selectedMetric) ?? data.metrics[0];
  return (
    <div className="page-stack">
      <div className="page-toolbar">
        <Link className="inline-flex items-center gap-2 text-sm font-medium text-[color:var(--muted-foreground)] hover:text-[color:var(--primary)]" href="/">
          <ArrowLeft className="h-4 w-4" />
          总览
        </Link>
        <div className="filter-bar">
          <Select label="站点" value={selectedStation} onChange={(event) => onStationChange(event.target.value)}>
            {stationOrder.map((id) => {
              const station = data.current.find((item) => item.id === id);
              return (
                <option key={id} value={id}>
                  {station?.name ?? id}
                </option>
              );
            })}
          </Select>
          <Select
            label="指标"
            value={selectedMetric}
            onChange={(event) => onMetricChange(event.target.value as MetricKey)}
          >
            {data.metrics.map((metric) => (
              <option key={metric.id} value={metric.id}>
                {metric.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <ChartCard title={`${currentStation?.name ?? selectedStation} 实时趋势`}>
        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={liveRows}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="collect_time" tickFormatter={formatClock} minTickGap={36} />
            <YAxis width={50} />
            <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 8 }} />
            <Line dataKey={selectedMetric} name={currentMetric.name} stroke={metricColors[selectedMetric]} dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title={`${currentStation?.name ?? selectedStation} 历史趋势`} description={sparkComputedDescription(data.meta.spark_completed_at)}>
        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={historyRows}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="collect_time" tickFormatter={(value) => String(value).slice(5).replace("T", " ")} minTickGap={44} />
            <YAxis width={50} />
            <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 8 }} />
            <Line dataKey={selectedMetric} name={currentMetric.name} stroke={metricColors[selectedMetric]} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

function Analysis({
  data,
  selectedMetric,
  recordStation,
  hdfsRows,
  onMetricChange,
  onRecordStationChange,
  onRefresh,
}: {
  data: DashboardData;
  selectedMetric: MetricKey;
  recordStation: string;
  hdfsRows: WeatherRow[];
  onMetricChange: (metric: MetricKey) => void;
  onRecordStationChange: (station: string) => void;
  onRefresh: () => void;
}) {
  const [refreshStatus, setRefreshStatus] = useState("");
  const [sparkStatus, setSparkStatus] = useState<SparkJobStatus | null>(null);
  const sparkLogRef = useRef<HTMLPreElement | null>(null);
  const comparisonRows = useMemo(() => {
    const byTime = new Map<string, Record<string, string | number>>();
    data.records.forEach((row) => {
      const item = byTime.get(row.collect_time) ?? { collect_time: row.collect_time.slice(5).replace("T", " ") };
      item[row.station_name] = row[selectedMetric];
      byTime.set(row.collect_time, item);
    });
    return Array.from(byTime.values());
  }, [data.records, selectedMetric]);
  const tableRows = hdfsRows.slice().reverse();

  const submitSpark = async () => {
    setRefreshStatus("提交 Spark 重算中");
    const nextStatus = await readJson<SparkJobStatus>("/api/analysis/refresh", { method: "POST" });
    setSparkStatus(nextStatus);
    setRefreshStatus(nextStatus.message);
  };

  useEffect(() => {
    let cancelled = false;
    readJson<SparkJobStatus>("/api/analysis/refresh/status")
      .then((nextStatus) => {
        if (!cancelled && (nextStatus.status === "running" || Boolean(nextStatus.job_id))) {
          setSparkStatus(nextStatus);
          setRefreshStatus(nextStatus.message);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (sparkStatus?.status !== "running") return undefined;
    const timer = window.setInterval(() => {
      readJson<SparkJobStatus>("/api/analysis/refresh/status")
        .then((nextStatus) => {
          setSparkStatus(nextStatus);
          setRefreshStatus(nextStatus.message);
          if (nextStatus.status === "succeeded") {
            void onRefresh();
          }
        })
        .catch((error) => {
          setRefreshStatus(error instanceof Error ? error.message : "Spark 状态读取失败");
        });
    }, 1500);
    return () => window.clearInterval(timer);
  }, [sparkStatus?.job_id, sparkStatus?.status, onRefresh]);

  useEffect(() => {
    const logEl = sparkLogRef.current;
    if (logEl) {
      logEl.scrollTop = logEl.scrollHeight;
    }
  }, [sparkStatus?.log_tail]);

  return (
    <div className="page-stack">
      <div className="page-toolbar">
        <Link className="inline-flex items-center gap-2 text-sm font-medium text-[color:var(--muted-foreground)] hover:text-[color:var(--primary)]" href="/detail">
          <ArrowLeft className="h-4 w-4" />
          详情
        </Link>
        <div className="filter-bar">
          <Select label="对比指标" value={selectedMetric} onChange={(event) => onMetricChange(event.target.value as MetricKey)}>
            {data.metrics.map((metric) => (
              <option key={metric.id} value={metric.id}>
                {metric.name}
              </option>
            ))}
          </Select>
          <Button variant="outline" onClick={submitSpark} disabled={sparkStatus?.status === "running"}>
            <RefreshCw className="h-4 w-4" />
            手动刷新
          </Button>
        </div>
      </div>
      {refreshStatus || sparkStatus ? (
        <section className="spark-status" aria-live="polite">
          <div>
            <strong>{sparkStatus?.status === "running" ? "Spark 运行中" : "Spark 状态"}</strong>
            <span>{refreshStatus || sparkStatus?.message}</span>
          </div>
          {sparkStatus?.job_id ? (
            <div className="spark-meta">
              job {sparkStatus.job_id}
              {sparkStatus.application_id ? ` · ${sparkStatus.application_id}` : ""}
              {sparkStatus.pid ? ` · pid ${sparkStatus.pid}` : ""}
              {sparkStatus.exit_code != null ? ` · exit ${sparkStatus.exit_code}` : ""}
            </div>
          ) : null}
          {sparkStatus ? (
            <div className="spark-progress" aria-label={`Spark 进度 ${sparkStatus.progress_percent ?? 0}%`}>
              <div className="spark-progress-header">
                <span>{sparkStatus.progress_label ?? sparkStatus.message}</span>
                <span>{formatNumber(sparkStatus.progress_percent ?? 0, 0)}%</span>
              </div>
              <div className="spark-progress-track">
                <div style={{ width: `${Math.min(100, Math.max(0, Number(sparkStatus.progress_percent ?? 0)))}%` }} />
              </div>
            </div>
          ) : null}
          {sparkStatus?.log_tail?.length ? (
            <pre ref={sparkLogRef} className="spark-log">{sparkStatus.log_tail.join("\n")}</pre>
          ) : null}
        </section>
      ) : null}

      <ChartCard title="多站对比" description={sparkComputedDescription(data.meta.spark_completed_at)}>
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={comparisonRows}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="collect_time" minTickGap={44} />
            <YAxis width={50} />
            <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 8 }} />
            {stationOrder.map((id) => {
              const station = data.current.find((item) => item.id === id);
              return (
                <Line
                  key={id}
                  dataKey={station?.name ?? id}
                  name={station?.name ?? id}
                  stroke={stationColors[id]}
                  dot={false}
                  strokeWidth={2}
                  connectNulls
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <Card className="p-5">
        <CardHeader>
          <div>
            <CardTitle>数据记录</CardTitle>
            <CardDescription>来源：HDFS /weathertextdb/live_*.csv，实时写入记录</CardDescription>
          </div>
          <div className="filter-bar">
            <Select label="站点" value={recordStation} onChange={(event) => onRecordStationChange(event.target.value)}>
              <option value="all">全部</option>
              {stationOrder.map((id) => {
                const station = data.current.find((item) => item.id === id);
                return (
                  <option key={id} value={id}>
                    {station?.name ?? id}
                  </option>
                );
              })}
            </Select>
            <a className="link-button" href={`/api/export/weather_observations.csv${recordStation === "all" ? "" : `?station_id=${recordStation}`}`}>
              <Download className="h-4 w-4" />
              导出 CSV
            </a>
          </div>
        </CardHeader>
        <div className="mt-3 overflow-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>站点</th>
                <th>温度</th>
                <th>湿度</th>
                <th>气压</th>
                <th>风速</th>
                <th>风向</th>
                <th>天气码</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row) => (
                <tr key={`${row.station_id}-${row.collect_time}`}>
                  <td>{row.collect_time}</td>
                  <td>{row.station_name}</td>
                  <td>{formatNumber(row.temperature)} °C</td>
                  <td>{formatNumber(row.humidity, 0)}%</td>
                  <td>{formatNumber(row.pressure, 2)} hPa</td>
                  <td>{formatNumber(row.wind_speed)} m/s</td>
                  <td>
                    {formatNumber(row.wind_direction, 0)}° {directionLabel(row.wind_direction)}
                  </td>
                  <td>{row.weather_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function ChartCard({
  title,
  description,
  className,
  children,
}: {
  title: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <CardHeader>
        <div>
          <CardTitle className="inline-flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            {title}
          </CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
      </CardHeader>
      <div className="mt-3">{children}</div>
    </Card>
  );
}
