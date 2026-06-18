const state = {
  data: null,
  selectedStation: "tangshan",
  selectedMetric: "temperature",
  activeView: "overview",
};

const stationOrder = ["tangshan", "beijing", "shanghai"];
const stationColors = {
  tangshan: "oklch(0.58 0.12 190)",
  beijing: "oklch(0.63 0.14 45)",
  shanghai: "oklch(0.6 0.12 245)",
};
const metricColors = {
  temperature: "oklch(0.63 0.14 45)",
  humidity: "oklch(0.6 0.12 245)",
  pressure: "oklch(0.57 0.08 300)",
  wind_speed: "oklch(0.58 0.11 150)",
  wind_direction: "oklch(0.56 0.1 270)",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toFixed(digits).replace(/\.0$/, "");
}

function formatBytes(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0 B";
  if (number < 1024) return `${number} B`;
  if (number < 1024 * 1024) return `${(number / 1024).toFixed(1)} KB`;
  return `${(number / 1024 / 1024).toFixed(1)} MB`;
}

function directionLabel(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  const labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return labels[Math.round(number / 22.5) % 16];
}

function currentById(id) {
  return state.data.current.find((item) => item.id === id);
}

function metricById(id) {
  return state.data.metrics.find((item) => item.id === id);
}

function summaryById(id) {
  return state.data.summary.find((item) => item.station_id === id);
}

function hourlyByStation(id) {
  return state.data.hourly.filter((row) => row.station_id === id);
}

function setView(name) {
  state.activeView = name;
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${name}View`);
  });
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === name);
  });
  if (state.data) renderAll();
}

function setStation(id) {
  state.selectedStation = id;
  renderAll();
}

function renderStatus(message, kind = "ready") {
  const line = document.getElementById("statusLine");
  line.textContent = message;
  line.dataset.kind = kind;
}

function renderControls() {
  const stationSelect = document.getElementById("stationSelect");
  stationSelect.innerHTML = stationOrder
    .map((id) => {
      const station = currentById(id);
      return `<option value="${id}">${escapeHtml(station.name)}</option>`;
    })
    .join("");
  stationSelect.value = state.selectedStation;

  const metricSelect = document.getElementById("metricSelect");
  metricSelect.innerHTML = state.data.metrics
    .map((metric) => `<option value="${metric.id}">${escapeHtml(metric.name)}</option>`)
    .join("");
  metricSelect.value = state.selectedMetric;

  const suffix = `?station_id=${encodeURIComponent(state.selectedStation)}`;
  document.getElementById("stationExportLink").href = `/api/export/weather_observations.csv${suffix}`;
}

function renderOverview() {
  const selected = currentById(state.selectedStation);
  const sourceText = selected.source === "esp32_usb_open_meteo" ? "ESP32 USB + Open-Meteo" : "Open-Meteo";
  const range = state.data.meta.historical_range;

  document.getElementById("selectedName").textContent = selected.name;
  document.getElementById("selectedTime").textContent = selected.time;
  document.getElementById("sourcePill").textContent = sourceText;
  document.getElementById("rangeText").textContent =
    `历史范围 ${range.start_date} 至 ${range.end_date}，共 ${state.data.meta.record_count} 条`;

  document.querySelectorAll(".station-marker").forEach((marker) => {
    const station = currentById(marker.dataset.station);
    marker.classList.toggle("selected", station.id === state.selectedStation);
    marker.style.setProperty("--station-color", stationColors[station.id]);
    const label = marker.querySelector(".marker-label");
    label.innerHTML = `<span class="marker-name">${escapeHtml(station.name)}</span><span class="marker-temp">${formatNumber(station.temperature)} °C · ${formatNumber(station.humidity, 0)}%</span>`;
    label.onclick = () => setStation(station.id);
  });

  document.getElementById("stationList").innerHTML = stationOrder
    .map((id) => {
      const station = currentById(id);
      const active = station.id === state.selectedStation ? " active" : "";
      const source = station.source === "esp32_usb_open_meteo" ? "硬件采集" : "接口采集";
      return `<button class="station-row${active}" type="button" data-station="${station.id}">
        <span>
          <strong>${escapeHtml(station.name)}</strong>
          <small>${source} · ${escapeHtml(station.time)}</small>
        </span>
        <b>${formatNumber(station.temperature)} °C</b>
      </button>`;
    })
    .join("");
  document.querySelectorAll(".station-row").forEach((row) => {
    row.onclick = () => setStation(row.dataset.station);
  });

  const metricDefs = [
    ["temperature", "温度", "°C", 1],
    ["humidity", "湿度", "%", 0],
    ["pressure", "气压", "hPa", 1],
    ["wind_speed", "风速", "m/s", 1],
    ["wind_direction", "风向", "°", 0],
  ];
  document.getElementById("metricGrid").innerHTML = metricDefs
    .map(([key, label, unit, digits]) => {
      const extra = key === "wind_direction" ? `<em>${directionLabel(selected[key])}</em>` : "";
      return `<article class="metric" style="--metric-color:${metricColors[key]}">
        <strong>${formatNumber(selected[key], digits)}<small>${unit}</small></strong>
        <span>${label}${extra}</span>
      </article>`;
    })
    .join("");
}

function chartBounds(seriesList, keys) {
  const values = [];
  seriesList.forEach((series) => {
    series.rows.forEach((row) => {
      keys.forEach((key) => {
        const value = Number(row[key]);
        if (Number.isFinite(value)) values.push(value);
      });
    });
  });
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max(1, (max - min) * 0.08);
  return { min: min - pad, max: max + pad, span: Math.max(1, max - min + pad * 2) };
}

function seriesBounds(rows, key) {
  const values = rows.map((row) => Number(row[key])).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max(1, (max - min) * 0.08);
  return { min: min - pad, max: max + pad, span: Math.max(1, max - min + pad * 2) };
}

function setupCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

function drawChart(canvas, seriesList, keys) {
  const { ctx, width, height } = setupCanvas(canvas);
  const pad = { left: 46, right: 18, top: 18, bottom: 38 };
  const sharedScale = new Set(keys).size === 1;
  const bounds = chartBounds(seriesList, keys);
  ctx.clearRect(0, 0, width, height);

  ctx.strokeStyle = "oklch(0.88 0.01 225)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i < 4; i += 1) {
    const y = pad.top + ((height - pad.top - pad.bottom) * i) / 3;
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
  }
  ctx.stroke();

  ctx.fillStyle = "oklch(0.45 0.014 225)";
  ctx.font = "12px system-ui, sans-serif";
  if (sharedScale) {
    ctx.fillText(bounds.max.toFixed(1), 6, pad.top + 4);
    ctx.fillText(bounds.min.toFixed(1), 6, height - pad.bottom);
  } else {
    ctx.fillText("相对变化", 6, pad.top + 4);
  }

  seriesList.forEach((series) => {
    const localBounds = sharedScale ? bounds : seriesBounds(series.rows, series.key);
    ctx.strokeStyle = series.color;
    ctx.lineWidth = series.width || 2.2;
    ctx.beginPath();
    series.rows.forEach((row, index) => {
      const x = pad.left + ((width - pad.left - pad.right) * index) / Math.max(1, series.rows.length - 1);
      const y =
        height - pad.bottom - ((Number(row[series.key]) - localBounds.min) / localBounds.span) * (height - pad.top - pad.bottom);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  const first = seriesList[0]?.rows[0]?.collect_time?.slice(5).replace("T", " ");
  const last = seriesList[0]?.rows.at(-1)?.collect_time?.slice(5).replace("T", " ");
  ctx.fillStyle = "oklch(0.45 0.014 225)";
  ctx.fillText(first || "", pad.left, height - 12);
  ctx.textAlign = "right";
  ctx.fillText(last || "", width - pad.right, height - 12);
  ctx.textAlign = "left";

  let legendX = pad.left;
  seriesList.forEach((series) => {
    ctx.fillStyle = series.color;
    ctx.fillRect(legendX, 8, 18, 3);
    ctx.fillStyle = "oklch(0.31 0.012 230)";
    ctx.fillText(series.label, legendX + 24, 12);
    legendX += 92;
  });
}

function renderDetail() {
  const selectedRows = hourlyByStation(state.selectedStation);
  const metric = metricById(state.selectedMetric);
  const station = currentById(state.selectedStation);
  document.getElementById("comparisonCaption").textContent = metric.name;

  drawChart(document.getElementById("temperatureHumidityChart"), [
    { rows: selectedRows, key: "temperature", label: "温度", color: metricColors.temperature },
    { rows: selectedRows, key: "humidity", label: "湿度", color: metricColors.humidity },
  ], ["temperature", "humidity"]);

  drawChart(document.getElementById("pressureWindChart"), [
    { rows: selectedRows, key: "pressure", label: "气压", color: metricColors.pressure },
    { rows: selectedRows, key: "wind_speed", label: "风速", color: metricColors.wind_speed },
  ], ["pressure", "wind_speed"]);

  drawChart(document.getElementById("comparisonChart"), stationOrder.map((id) => ({
    rows: hourlyByStation(id),
    key: state.selectedMetric,
    label: currentById(id).name,
    color: stationColors[id],
  })), [state.selectedMetric]);

  document.getElementById("summaryStrip").innerHTML = stationOrder
    .map((id) => {
      const item = summaryById(id);
      return `<article class="summary-item">
        <strong>${escapeHtml(item.station_name)}</strong>
        <span>记录 ${item.records} 条</span>
        <span>均温 ${item.avg_temperature} °C · 均湿 ${item.avg_humidity}%</span>
        <span>温度范围 ${item.min_temperature} 至 ${item.max_temperature} °C</span>
      </article>`;
    })
    .join("");

  document.getElementById("recordsBody").innerHTML = selectedRows
    .slice(-48)
    .reverse()
    .map((row) => `<tr>
      <td>${escapeHtml(row.collect_time)}</td>
      <td>${escapeHtml(row.station_name)}</td>
      <td>${formatNumber(row.temperature)} °C</td>
      <td>${formatNumber(row.humidity, 0)}%</td>
      <td>${formatNumber(row.pressure)} hPa</td>
      <td>${formatNumber(row.wind_speed)} m/s</td>
      <td>${formatNumber(row.wind_direction, 0)}° ${directionLabel(row.wind_direction)}</td>
      <td>${escapeHtml(row.weather_code)}</td>
    </tr>`)
    .join("");

  renderStatus(`当前查看 ${station.name}，${metric.name}对比`, "ready");
}

function renderSystem() {
  const system = state.data.system;
  const counts = system.counts;
  const paths = system.paths;
  const range = system.historical_range;

  document.getElementById("systemRange").textContent = `${range.start_date} 至 ${range.end_date}`;
  document.getElementById("pipelineList").innerHTML = [
    ["ESP32 USB", `最新样本 ${system.latest_esp32_sample?.collect_time || "未读取"}`],
    ["Open-Meteo", `历史记录 ${counts.weather_observations} 条`],
    ["HDFS", paths.hdfs_input],
    ["Hive", paths.hive_table],
    ["Spark", paths.spark_output],
    ["HBase", paths.hbase_table],
    ["FastAPI", "/api/dashboard"],
  ].map(([title, body], index) => `<div class="pipeline-step">
      <b>${index + 1}</b>
      <span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(body)}</small></span>
    </div>`)
    .join("");

  document.getElementById("countGrid").innerHTML = [
    ["历史记录", counts.weather_observations],
    ["当前站点", counts.current_stations],
    ["小时序列", counts.hourly_series],
    ["ESP32 样本", counts.esp32_samples],
  ].map(([label, value]) => `<article class="count-card"><strong>${value}</strong><span>${label}</span></article>`).join("");

  document.getElementById("filesBody").innerHTML = system.files
    .map((file) => `<tr>
      <td>${escapeHtml(file.path)}</td>
      <td><span class="file-state ${file.exists ? "ok" : "missing"}">${file.exists ? "存在" : "缺失"}</span></td>
      <td>${formatBytes(file.bytes)}</td>
    </tr>`)
    .join("");
  renderStatus("系统状态已更新", "ready");
}

function renderAll() {
  if (!state.data) return;
  renderControls();
  renderOverview();
  if (state.activeView === "detail") renderDetail();
  if (state.activeView === "system") renderSystem();
}

async function loadDashboard() {
  renderStatus("读取数据中", "loading");
  const response = await fetch("/api/dashboard", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  state.data = await response.json();
  renderStatus("数据已更新", "ready");
  renderAll();
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => setView(tab.dataset.view);
});
document.getElementById("refreshButton").onclick = () => loadDashboard().catch((error) => renderStatus(`数据读取失败：${error.message}`, "error"));
document.getElementById("openDetailButton").onclick = () => setView("detail");
document.getElementById("stationSelect").onchange = (event) => {
  state.selectedStation = event.target.value;
  renderAll();
};
document.getElementById("metricSelect").onchange = (event) => {
  state.selectedMetric = event.target.value;
  renderAll();
};
window.addEventListener("resize", () => {
  if (state.data) renderAll();
});

loadDashboard().catch((error) => renderStatus(`数据读取失败：${error.message}`, "error"));
