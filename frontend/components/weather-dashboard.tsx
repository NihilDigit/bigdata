"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Cloud,
  CloudDrizzle,
  CloudLightning,
  CloudRain,
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

type ViewName = "overview" | "detail";

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
  source: string;
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
};

type HourlyRow = {
  collect_time: string;
  station_id: string;
  station_name: string;
  temperature: number;
  humidity: number;
  pressure: number;
  wind_speed: number;
  wind_direction: number;
  weather_code: number;
};

type LiveRow = HourlyRow & {
  source?: string;
  sample_seq?: number;
};

type DashboardData = {
  stations: Array<{ id: string; name: string; latitude: number; longitude: number }>;
  metrics: Metric[];
  current: StationCurrent[];
  summary: Summary[];
  hourly: HourlyRow[];
  tangshanLive: LiveRow[];
  meta: {
    historical_range: { start_date: string; end_date: string };
    record_count: number;
  };
};

type MetricKey = "temperature" | "humidity" | "pressure" | "wind_speed" | "wind_direction";

const stationOrder = ["tangshan", "beijing", "shanghai"];
const refreshIntervalMs = 1000;
const stationLabelOffset: Record<string, { x: string; y: string }> = {
  beijing: { x: "-148px", y: "-14px" },
  tangshan: { x: "24px", y: "-64px" },
  shanghai: { x: "20px", y: "-4px" },
};

const mapFrame = {
  width: 1023,
  height: 780,
  sourceHeight: 1149,
};

const stationMapAnchor: Record<string, { x: number; y: number }> = {
  beijing: { x: 692, y: 372 },
  tangshan: { x: 718, y: 386 },
  shanghai: { x: 825, y: 553 },
};

function stationMapPosition(station: Pick<StationCurrent, "id">) {
  const { x, y } = stationMapAnchor[station.id];
  return {
    left: `${((x / mapFrame.width) * 100).toFixed(2)}%`,
    top: `${((y / mapFrame.height) * 100).toFixed(2)}%`,
  };
}

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
  ["pressure", "气压", "hPa", 1],
  ["wind_speed", "风速", "m/s", 1],
  ["wind_direction", "风向", "deg", 0],
];

function formatNumber(value: unknown, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "暂无";
  return number.toFixed(digits).replace(/\.0$/, "");
}

function formatFixed(value: unknown, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "暂无";
  return number.toFixed(digits);
}

function directionLabel(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "暂无";
  const labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return labels[Math.round(number / 22.5) % 16];
}

function sourceLabel(source: string) {
  return source.startsWith("esp32_") ? "ESP32 + Open-Meteo" : "Open-Meteo";
}

function weatherLabel(code: number) {
  if (code === 0) return "晴";
  if ([1, 2, 3].includes(code)) return "多云";
  if ([45, 48].includes(code)) return "雾";
  if ([51, 53, 55].includes(code)) return "毛毛雨";
  if ([61, 63, 65, 80, 81, 82].includes(code)) return "雨";
  if ([95, 96, 99].includes(code)) return "雷暴";
  return "天气";
}

function WeatherIcon({ code, className }: { code: number; className?: string }) {
  const props = { className: cn("h-4 w-4", className), "aria-hidden": true };
  if (code === 0) return <Sun {...props} />;
  if ([1, 2, 3].includes(code)) return <CloudSun {...props} />;
  if ([51, 53, 55].includes(code)) return <CloudDrizzle {...props} />;
  if ([61, 63, 65, 80, 81, 82].includes(code)) return <CloudRain {...props} />;
  if ([95, 96, 99].includes(code)) return <CloudLightning {...props} />;
  return <Cloud {...props} />;
}

function toNumberRow(row: Record<string, string>): HourlyRow {
  return {
    collect_time: row.collect_time,
    station_id: row.station_id,
    station_name: row.station_name,
    temperature: Number(row.temperature),
    humidity: Number(row.humidity),
    pressure: Number(row.pressure),
    wind_speed: Number(row.wind_speed),
    wind_direction: Number(row.wind_direction),
    weather_code: Number(row.weather_code),
  };
}

function toLiveRow(row: Record<string, string>): LiveRow {
  return {
    ...toNumberRow(row),
    source: row.source,
    sample_seq: row.sample_seq ? Number(row.sample_seq) : undefined,
  };
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
    fractionalSecondDigits: 3,
  });
}

async function readJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
  return (await response.json()) as T;
}

async function fetchDashboard(): Promise<DashboardData> {
  const [current, metrics, summary, records, tangshanLiveRows] = await Promise.all([
    readJson<StationCurrent[]>("/api/stations/current"),
    readJson<Metric[]>("/api/metrics"),
    readJson<Summary[]>("/api/analysis/summary"),
    readJson<Array<Record<string, string>>>("/api/records?limit=504"),
    readJson<Array<Record<string, string>>>("/api/stations/tangshan/live?seconds=300"),
  ]);
  const hourly = records.map(toNumberRow);
  const tangshanLive = tangshanLiveRows.map(toLiveRow);
  const times = hourly.map((row) => row.collect_time).sort();
  return {
    stations: current.map(({ id, name, latitude, longitude }) => ({ id, name, latitude, longitude })),
    metrics,
    current,
    summary,
    hourly,
    tangshanLive,
    meta: {
      historical_range: {
        start_date: times[0]?.slice(0, 10) ?? "暂无",
        end_date: times.at(-1)?.slice(0, 10) ?? "暂无",
      },
      record_count: hourly.length,
    },
  };
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
    <main className="mx-auto max-w-[1220px] px-6 py-7 max-[720px]:px-4">
      <header className="mb-4 grid grid-cols-[minmax(180px,1fr)_auto_auto] items-center gap-4 max-[820px]:grid-cols-1">
        <div>
          <p className="eyebrow">气象大数据计算与可视化系统</p>
          <h1 className="m-0 text-xl font-semibold tracking-normal">Weather Lab</h1>
        </div>
        <nav className="view-tabs" aria-label="页面视图">
          <Link className={cn("tab-link", view === "overview" && "active")} href="/">
            总览
          </Link>
          <Link className={cn("tab-link", view === "detail" && "active")} href="/detail">
            详细数据
          </Link>
        </nav>
        <Button variant="outline" size="icon" onClick={onRefresh} aria-label="刷新数据" title="刷新数据">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </header>
      <div className="mb-3 min-h-6 text-xs font-medium text-[color:var(--muted-foreground)]">{status}</div>
      {children}
    </main>
  );
}

export function WeatherDashboard({ view }: { view: ViewName }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [selectedStation, setSelectedStation] = useState("tangshan");
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>("temperature");
  const [status, setStatus] = useState("读取数据中");
  const [lastLoadedAt, setLastLoadedAt] = useState<string>("");

  const load = async () => {
    setStatus("读取数据中");
    try {
      const nextData = await fetchDashboard();
      setData(nextData);
      const loadedAt = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      setLastLoadedAt(loadedAt);
      setStatus(`数据已更新 ${loadedAt}，每 1 秒自动刷新`);
    } catch (error) {
      setStatus(error instanceof Error ? `数据读取失败：${error.message}` : "数据读取失败");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void load();
    }, refreshIntervalMs);
    return () => window.clearInterval(timer);
  }, []);

  const current = data?.current.find((item) => item.id === selectedStation) ?? data?.current[0];
  const hourly = useMemo(
    () => data?.hourly.filter((item) => item.station_id === selectedStation) ?? [],
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
          tangshanLive={data.tangshanLive}
          lastLoadedAt={lastLoadedAt}
          onStationChange={setSelectedStation}
        />
      ) : (
        <Detail
          data={data}
          hourly={hourly}
          selectedStation={selectedStation}
          selectedMetric={selectedMetric}
          tangshanLive={data.tangshanLive}
          lastLoadedAt={lastLoadedAt}
          onStationChange={setSelectedStation}
          onMetricChange={setSelectedMetric}
        />
      )}
    </Shell>
  );
}

function Overview({
  data,
  selected,
  selectedStation,
  tangshanLive,
  lastLoadedAt,
  onStationChange,
}: {
  data: DashboardData;
  selected: StationCurrent;
  selectedStation: string;
  tangshanLive: LiveRow[];
  lastLoadedAt: string;
  onStationChange: (station: string) => void;
}) {
  const range = data.meta.historical_range;
  const latestLive = tangshanLive.at(-1);
  return (
    <div className="grid gap-4">
      <Card className="p-5">
        <CardHeader>
          <div>
            <CardTitle>三站实时概览</CardTitle>
            <CardDescription>
              历史范围 {range.start_date} 至 {range.end_date}，共 {data.meta.record_count} 条
            </CardDescription>
          </div>
          <span className="source-pill">{sourceLabel(selected.source)}</span>
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
                height={mapFrame.sourceHeight}
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
          <div className="map-source">自然资源部标准地图服务系统，单色化展示</div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-start justify-between gap-4 max-[720px]:flex-col">
          <div>
            <p className="eyebrow">当前读数</p>
            <h2 className="m-0 text-base font-semibold">{selected.name}</h2>
            <p className="mt-1 text-xs font-medium text-[color:var(--muted-foreground)]">{selected.time}</p>
          </div>
          <Link className="link-button" href="/detail">
            查看详细数据
          </Link>
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
        <div className="live-panel">
          <div>
            <p className="eyebrow">ESP32 实时采样</p>
            <strong>{latestLive ? `${formatFixed(latestLive.temperature)} °C / ${formatFixed(latestLive.humidity)}%` : "暂无实时样本"}</strong>
            <span>
              最新采样 {formatClock(latestLive?.collect_time)}
              {latestLive?.sample_seq ? `，样本 #${latestLive.sample_seq}` : ""}，近 5 分钟 {tangshanLive.length} 条，页面刷新 {lastLoadedAt || "暂无"}
            </span>
          </div>
          <div className="live-spark">
            {tangshanLive.slice(-8).map((row) => (
              <span key={`${row.collect_time}-${row.humidity}`} title={row.collect_time}>
                {formatFixed(row.temperature)}°/{formatFixed(row.humidity)}%
                {row.sample_seq ? ` #${row.sample_seq}` : ""}
              </span>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}

function Detail({
  data,
  hourly,
  selectedStation,
  selectedMetric,
  tangshanLive,
  lastLoadedAt,
  onStationChange,
  onMetricChange,
}: {
  data: DashboardData;
  hourly: HourlyRow[];
  selectedStation: string;
  selectedMetric: MetricKey;
  tangshanLive: LiveRow[];
  lastLoadedAt: string;
  onStationChange: (station: string) => void;
  onMetricChange: (metric: MetricKey) => void;
}) {
  const currentMetric = data.metrics.find((item) => item.id === selectedMetric) ?? data.metrics[0];
  const comparisonRows = useMemo(() => {
    const byTime = new Map<string, Record<string, string | number>>();
    data.hourly.forEach((row) => {
      const item = byTime.get(row.collect_time) ?? { collect_time: row.collect_time.slice(5).replace("T", " ") };
      item[row.station_name] = row[selectedMetric];
      byTime.set(row.collect_time, item);
    });
    return Array.from(byTime.values());
  }, [data.hourly, selectedMetric]);

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between gap-3 max-[720px]:flex-col max-[720px]:items-start">
        <Link className="inline-flex items-center gap-2 text-sm font-medium text-[color:var(--muted-foreground)] hover:text-[color:var(--primary)]" href="/">
          <ArrowLeft className="h-4 w-4" />
          返回总览
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
            label="对比指标"
            value={selectedMetric}
            onChange={(event) => onMetricChange(event.target.value as MetricKey)}
          >
            {data.metrics.map((metric) => (
              <option key={metric.id} value={metric.id}>
                {metric.name}
              </option>
            ))}
          </Select>
          <a className="link-button" href={`/api/export/weather_observations.csv?station_id=${selectedStation}`}>
            <Download className="h-4 w-4" />
            导出 CSV
          </a>
        </div>
      </div>

      <section className="chart-grid">
        <ChartCard title="温湿度趋势" description="按各指标范围绘制">
          <ResponsiveContainer width="100%" height={310}>
            <LineChart data={hourly}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="collect_time" tickFormatter={(value) => String(value).slice(5).replace("T", " ")} minTickGap={44} />
              <YAxis yAxisId="temperature" stroke="var(--metric-temperature)" width={46} />
              <YAxis yAxisId="humidity" orientation="right" stroke="var(--metric-humidity)" width={42} />
              <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 8 }} />
              <Line yAxisId="temperature" dataKey="temperature" name="温度" stroke="var(--metric-temperature)" dot={false} strokeWidth={2} />
              <Line yAxisId="humidity" dataKey="humidity" name="湿度" stroke="var(--metric-humidity)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="风况" description="风速与风向">
          <ResponsiveContainer width="100%" height={310}>
            <LineChart data={hourly}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="collect_time" tickFormatter={(value) => String(value).slice(5).replace("T", " ")} minTickGap={44} />
              <YAxis yAxisId="speed" stroke="var(--metric-wind-speed)" width={46} />
              <YAxis yAxisId="direction" orientation="right" stroke="var(--metric-wind-direction)" width={42} />
              <Tooltip contentStyle={{ borderColor: "var(--border)", borderRadius: 8 }} />
              <Line yAxisId="speed" dataKey="wind_speed" name="风速" stroke="var(--metric-wind-speed)" dot={false} strokeWidth={2} />
              <Line yAxisId="direction" dataKey="wind_direction" name="风向" stroke="var(--metric-wind-direction)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="多站对比" description={currentMetric.name} className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={330}>
            <LineChart data={comparisonRows}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="collect_time" minTickGap={44} />
              <YAxis width={46} />
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
      </section>

      <section className="summary-strip">
        {stationOrder.map((id) => {
          const item = data.summary.find((summary) => summary.station_id === id);
          if (!item) return null;
          return (
            <Card key={id} className="p-4">
              <strong className="block text-sm">{item.station_name}</strong>
              <span className="mt-2 block text-xs leading-6 text-[color:var(--muted-foreground)]">
                记录 {item.records} 条，均温 {item.avg_temperature} °C，均湿 {item.avg_humidity}%
              </span>
              <span className="block text-xs leading-6 text-[color:var(--muted-foreground)]">
                温度范围 {item.min_temperature} 至 {item.max_temperature} °C
              </span>
            </Card>
          );
        })}
      </section>

      <Card className="p-5">
        <CardHeader>
          <div>
            <CardTitle>ESP32 实时采样</CardTitle>
            <CardDescription>自动刷新于 {lastLoadedAt || "暂无"}，展示最近 5 分钟 TCP 采集记录</CardDescription>
          </div>
          <span className="source-pill">ESP32 + Open-Meteo</span>
        </CardHeader>
        <div className="live-record-grid">
          {tangshanLive.slice(-10).reverse().map((row) => (
            <article key={`${row.collect_time}-${row.humidity}`} className="live-record">
              <strong>{formatClock(row.collect_time)}</strong>
              {row.sample_seq ? <span>样本 #{row.sample_seq}</span> : null}
              <span>{formatFixed(row.temperature)} °C</span>
              <span>{formatFixed(row.humidity)}%</span>
            </article>
          ))}
          {tangshanLive.length === 0 ? (
            <p className="text-sm text-[color:var(--muted-foreground)]">暂无 ESP32 实时采样记录</p>
          ) : null}
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader>
          <div>
            <CardTitle>数据记录</CardTitle>
            <CardDescription>当前站点最近 48 条小时记录</CardDescription>
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
                <th>天气代码</th>
              </tr>
            </thead>
            <tbody>
              {hourly
                .slice(-48)
                .reverse()
                .map((row) => (
                  <tr key={`${row.station_id}-${row.collect_time}`}>
                    <td>{row.collect_time}</td>
                    <td>{row.station_name}</td>
                    <td>{formatNumber(row.temperature)} °C</td>
                    <td>{formatNumber(row.humidity, 0)}%</td>
                    <td>{formatNumber(row.pressure)} hPa</td>
                    <td>{formatNumber(row.wind_speed)} m/s</td>
                    <td>
                      {formatNumber(row.wind_direction, 0)} deg {directionLabel(row.wind_direction)}
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
  description: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
      </CardHeader>
      <div className="mt-3">{children}</div>
    </Card>
  );
}
