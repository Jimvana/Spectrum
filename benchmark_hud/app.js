const state = {
  preset: "small",
  repoUrl: "",
  source: null,
  events: 0,
  rawBytes: 0,
  engines: new Map(),
  history: new Map(),
  final: null,
};

const colors = {
  spectrum: "#00f6ff",
  tfidf: "#54ff8d",
  raw_bm25: "#ffd84d",
  dense_vector: "#b65cff",
  faiss: "#ff8b34",
};

const els = {
  runId: document.getElementById("runId"),
  corpusMeta: document.getElementById("corpusMeta"),
  rawBytes: document.getElementById("rawBytes"),
  phaseLabel: document.getElementById("phaseLabel"),
  engineGrid: document.getElementById("engineGrid"),
  eventTape: document.getElementById("eventTape"),
  eventCount: document.getElementById("eventCount"),
  queryCount: document.getElementById("queryCount"),
  queryValue: document.getElementById("queryValue"),
  repoControl: document.getElementById("repoControl"),
  repoInput: document.getElementById("repoInput"),
  startBtn: document.getElementById("startBtn"),
  stopBtn: document.getElementById("stopBtn"),
  presetGroup: document.getElementById("presetGroup"),
  modal: document.getElementById("summaryModal"),
  summaryBody: document.getElementById("summaryBody"),
  closeModal: document.getElementById("closeModal"),
  charts: {
    size: document.getElementById("sizeChart"),
    speed: document.getElementById("speedChart"),
    accuracy: document.getElementById("accuracyChart"),
  },
};

function fmtBytes(value) {
  if (!value) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = Number(value);
  for (const unit of units) {
    if (size < 1024 || unit === units[units.length - 1]) {
      return unit === "B" ? `${Math.round(size)} B` : `${size.toFixed(1)} ${unit}`;
    }
    size /= 1024;
  }
  return `${value} B`;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function sizeScore(bytes) {
  if (!bytes || !state.rawBytes) return 0;
  const ratio = bytes / state.rawBytes;
  return clamp((1 / Math.max(ratio, 0.01)) * 72, 0, 100);
}

function speedScore(ms) {
  if (!Number.isFinite(ms)) return 0;
  return clamp(100 / (1 + ms), 0, 100);
}

function accuracyScore(mrr) {
  return clamp((mrr || 0) * 100, 0, 100);
}

function addEvent(label, detail = "") {
  state.events += 1;
  els.eventCount.textContent = String(state.events);
  const li = document.createElement("li");
  li.innerHTML = `<strong>${label}</strong>${detail ? ` ${detail}` : ""}`;
  els.eventTape.prepend(li);
  while (els.eventTape.children.length > 90) {
    els.eventTape.lastElementChild.remove();
  }
}

function resetRun() {
  state.events = 0;
  state.rawBytes = 0;
  state.engines.clear();
  state.history.clear();
  state.final = null;
  els.eventTape.innerHTML = "";
  els.eventCount.textContent = "0";
  els.engineGrid.innerHTML = "";
  els.runId.textContent = "starting";
  els.corpusMeta.textContent = "-";
  els.rawBytes.textContent = "-";
  els.phaseLabel.textContent = "STARTING";
  drawAllCharts();
}

function makeEnginePanel(engine) {
  const panel = document.createElement("article");
  panel.className = "engine";
  panel.dataset.engine = engine.key;
  panel.innerHTML = `
    <div class="engine-title">
      <h3>${engine.label}</h3>
      <span class="engine-status">queued</span>
    </div>
    <div class="gauge-stack">
      ${gaugeMarkup("size", "Size", "-", "store bytes", colors[engine.key] || "#00f6ff")}
      ${gaugeMarkup("speed", "Speed", "-", "avg query ms", "#54ff8d")}
      ${gaugeMarkup("accuracy", "Accuracy", "-", "MRR", "#ffd84d")}
    </div>
    <canvas class="spark" height="42"></canvas>
    <div class="last-query">waiting for events</div>
  `;
  els.engineGrid.appendChild(panel);
}

function gaugeMarkup(key, label, value, sub, color) {
  return `
    <div class="gauge gauge-${key}">
      <div class="dial" style="--value:0;--gauge-color:${color}"><span>0</span></div>
      <div>
        <h4>${label}</h4>
        <strong>${value}</strong>
        <small>${sub}</small>
      </div>
    </div>
  `;
}

function setGauge(panel, key, score, value, sub) {
  const gauge = panel.querySelector(`.gauge-${key}`);
  const dial = gauge.querySelector(".dial");
  dial.style.setProperty("--value", String(clamp(score, 0, 100)));
  dial.querySelector("span").textContent = String(Math.round(clamp(score, 0, 100)));
  gauge.querySelector("strong").textContent = value;
  gauge.querySelector("small").textContent = sub;
}

function updateEnginePanel(key, payload) {
  const panel = els.engineGrid.querySelector(`[data-engine="${key}"]`);
  if (!panel) return;
  const status = panel.querySelector(".engine-status");
  if (payload.status) {
    status.textContent = payload.status;
    panel.classList.toggle("skipped", payload.status !== "ok" && payload.status !== "running");
  }
  if (payload.running !== undefined) {
    panel.classList.toggle("running", payload.running);
  }
  const metrics = payload.metrics || {};
  if (metrics.size_bytes || payload.size_bytes) {
    const bytes = metrics.size_bytes || payload.size_bytes;
    const ratio = state.rawBytes ? bytes / state.rawBytes : 0;
    setGauge(panel, "size", sizeScore(bytes), fmtBytes(bytes), `${ratio.toFixed(3)}x raw`);
  }
  if (metrics.avg_ms !== undefined) {
    setGauge(panel, "speed", speedScore(metrics.avg_ms), `${metrics.avg_ms.toFixed(3)} ms`, `p95 ${metrics.p95_ms.toFixed(3)} ms`);
  }
  if (metrics.mrr !== undefined) {
    setGauge(panel, "accuracy", accuracyScore(metrics.mrr), metrics.mrr.toFixed(3), `hit1 ${(metrics.hit1 * 100).toFixed(1)}%`);
  }
  if (payload.last) {
    panel.querySelector(".last-query").textContent = `${payload.last.query} -> ${payload.last.rank ? `rank ${payload.last.rank}` : "miss"}`;
  }
  drawSpark(panel.querySelector(".spark"), state.history.get(key) || [], colors[key] || "#00f6ff");
}

function handleRunStart(data) {
  state.rawBytes = data.corpus.raw_bytes;
  els.runId.textContent = data.run_id;
  els.corpusMeta.textContent = `${data.corpus.files} files / ${data.corpus.docs} docs / ${data.query_count} queries`;
  els.rawBytes.textContent = data.corpus.raw_label;
  els.phaseLabel.textContent = "LIVE";
  data.engines.forEach((engine) => {
    state.engines.set(engine.key, engine);
    state.history.set(engine.key, []);
    makeEnginePanel(engine);
  });
  addEvent("RUN", `${data.preset_label} corpus from ${data.run_dir}`);
}

function handleBuilt(data) {
  updateEnginePanel(data.engine, {
    status: data.status,
    size_bytes: data.size_bytes,
    running: data.status === "ok",
  });
  const note = data.status === "ok"
    ? `${fmtBytes(data.size_bytes)} / build ${data.build_ms.toFixed(1)} ms`
    : data.error;
  addEvent(data.label, note);
  drawAllCharts();
}

function handleMetric(data) {
  const history = state.history.get(data.engine) || [];
  history.push(data.metrics);
  state.history.set(data.engine, history);
  updateEnginePanel(data.engine, {
    metrics: data.metrics,
    last: data.last,
    status: "running",
    running: true,
  });
  addEvent(data.label, `${data.metrics.queries_done}/${data.metrics.queries_total} avg ${data.metrics.avg_ms.toFixed(3)} ms mrr ${data.metrics.mrr.toFixed(3)}`);
  drawAllCharts();
}

function handleEngineDone(data) {
  updateEnginePanel(data.engine, {
    metrics: data.metrics,
    status: "done",
    running: false,
  });
  addEvent(data.label, `done recall ${(data.metrics.recall * 100).toFixed(1)}%`);
}

function handleComplete(data) {
  state.final = data;
  els.phaseLabel.textContent = "COMPLETE";
  els.runId.textContent = data.run_id;
  addEvent("COMPLETE", data.run_dir);
  if (state.source) {
    state.source.close();
    state.source = null;
  }
  drawAllCharts();
  openSummary(data);
}

function handleError(data) {
  els.phaseLabel.textContent = "ERROR";
  addEvent("ERROR", data.message || "benchmark failed");
  if (state.source) {
    state.source.close();
    state.source = null;
  }
}

function startRun() {
  if (state.source) {
    state.source.close();
  }
  state.repoUrl = els.repoInput.value.trim();
  if (state.preset === "custom" && !state.repoUrl) {
    addEvent("REPO", "enter a GitHub repo first");
    els.repoInput.focus();
    return;
  }
  resetRun();
  const queries = encodeURIComponent(els.queryCount.value);
  const preset = encodeURIComponent(state.preset);
  const repo = state.preset === "custom" ? `&repo=${encodeURIComponent(state.repoUrl)}` : "";
  state.source = new EventSource(`/events?preset=${preset}&queries=${queries}&top_k=5${repo}`);
  const handlers = {
    phase: (data) => {
      els.phaseLabel.textContent = data.message.toUpperCase();
      addEvent("PHASE", data.message);
    },
    run_start: handleRunStart,
    engine_start: (data) => {
      updateEnginePanel(data.engine, { status: "building", running: true });
      addEvent(data.label, "building");
    },
    engine_built: handleBuilt,
    metric: handleMetric,
    engine_done: handleEngineDone,
    run_complete: handleComplete,
    error: handleError,
  };
  Object.entries(handlers).forEach(([type, handler]) => {
    state.source.addEventListener(type, (event) => handler(JSON.parse(event.data)));
  });
  state.source.onerror = () => {
    if (els.phaseLabel.textContent !== "COMPLETE") {
      addEvent("STREAM", "closed");
    }
  };
}

function stopRun() {
  if (state.source) {
    state.source.close();
    state.source = null;
    els.phaseLabel.textContent = "ABORTED";
    addEvent("ABORT", "client closed stream");
  }
}

function drawSpark(canvas, points, color) {
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.height;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(width * dpr));
  canvas.height = Math.floor(height * dpr);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(110,244,255,0.14)";
  ctx.lineWidth = 1;
  for (let y = 8; y < height; y += 12) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  if (!points.length) return;
  const values = points.map((p) => p.mrr || 0);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = values.length === 1 ? 0 : (index / (values.length - 1)) * width;
    const y = height - value * (height - 6) - 3;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function latestRows() {
  const rows = [];
  state.engines.forEach((engine, key) => {
    const history = state.history.get(key) || [];
    const latest = history[history.length - 1];
    if (latest) {
      rows.push({ key, label: engine.label, ...latest });
    }
  });
  if (state.final) {
    state.final.results.forEach((row) => {
      if (!rows.some((item) => item.key === row.engine) && row.status === "ok") {
        rows.push({ key: row.engine, label: row.label, ...row });
      }
    });
  }
  return rows;
}

function drawAllCharts() {
  drawBars(els.charts.size, latestRows(), "size", "lower");
  drawBars(els.charts.speed, latestRows(), "avg_ms", "lower");
  drawBars(els.charts.accuracy, latestRows(), "mrr", "higher");
}

function drawBars(canvas, rows, field, direction) {
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.height;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(width * dpr));
  canvas.height = Math.floor(height * dpr);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(0,246,255,0.05)";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(110,244,255,0.16)";
  ctx.lineWidth = 1;
  for (let y = 18; y < height; y += 22) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  if (!rows.length) return;
  const values = rows.map((row) => {
    if (field === "size") return row.size_bytes && state.rawBytes ? row.size_bytes / state.rawBytes : 0;
    return row[field] || 0;
  });
  const max = Math.max(...values, 0.001);
  const barGap = 8;
  const barWidth = Math.max(14, (width - barGap * (rows.length + 1)) / rows.length);
  rows.forEach((row, index) => {
    const value = values[index];
    const pct = direction === "lower" ? value / max : value;
    const barHeight = clamp(pct, 0, 1) * (height - 42);
    const x = barGap + index * (barWidth + barGap);
    const y = height - barHeight - 22;
    ctx.fillStyle = colors[row.key] || "#00f6ff";
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 12;
    ctx.fillRect(x, y, barWidth, barHeight);
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#ecfbff";
    ctx.font = "10px Consolas, monospace";
    ctx.textAlign = "center";
    const label = field === "size" ? `${value.toFixed(2)}x` : value.toFixed(3);
    ctx.fillText(label, x + barWidth / 2, Math.max(12, y - 5));
    ctx.fillStyle = "#86a0a7";
    ctx.fillText(row.label.slice(0, 10), x + barWidth / 2, height - 7);
  });
}

function openSummary(data) {
  const okRows = data.results.filter((row) => row.status === "ok");
  const skipped = data.results.filter((row) => row.status !== "ok");
  const tableRows = data.results.map((row) => `
    <tr>
      <td>${row.label}</td>
      <td>${row.status}</td>
      <td>${row.size_bytes ? fmtBytes(row.size_bytes) : "-"}</td>
      <td>${row.compression_ratio ? row.compression_ratio.toFixed(3) : "-"}</td>
      <td>${row.avg_ms !== undefined ? row.avg_ms.toFixed(4) : "-"}</td>
      <td>${row.p95_ms !== undefined ? row.p95_ms.toFixed(4) : "-"}</td>
      <td>${row.mrr !== undefined ? row.mrr.toFixed(4) : "-"}</td>
      <td>${row.recall !== undefined ? (row.recall * 100).toFixed(1) + "%" : row.error || "-"}</td>
    </tr>
  `).join("");
  els.summaryBody.innerHTML = `
    <table class="summary-table">
      <thead>
        <tr>
          <th>Engine</th><th>Status</th><th>Size</th><th>Ratio</th><th>Avg ms</th><th>P95 ms</th><th>MRR</th><th>Recall</th>
        </tr>
      </thead>
      <tbody>${tableRows}</tbody>
    </table>
    <div class="summary-grid">
      <div class="panel"><div class="panel-head"><span>SIZE</span><strong>STORE / RAW</strong></div><canvas id="modalSize" height="210"></canvas></div>
      <div class="panel"><div class="panel-head"><span>SPEED</span><strong>AVG MS</strong></div><canvas id="modalSpeed" height="210"></canvas></div>
      <div class="panel"><div class="panel-head"><span>ACCURACY</span><strong>MRR</strong></div><canvas id="modalAccuracy" height="210"></canvas></div>
    </div>
    ${skipped.length ? `<p class="last-query">${skipped.map((row) => `${row.label}: ${row.error}`).join(" | ")}</p>` : ""}
  `;
  els.modal.classList.add("open");
  els.modal.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => {
    drawBars(document.getElementById("modalSize"), okRows.map((row) => ({ key: row.engine, ...row })), "size", "lower");
    drawBars(document.getElementById("modalSpeed"), okRows.map((row) => ({ key: row.engine, ...row })), "avg_ms", "lower");
    drawBars(document.getElementById("modalAccuracy"), okRows.map((row) => ({ key: row.engine, ...row })), "mrr", "higher");
  });
}

function closeSummary() {
  els.modal.classList.remove("open");
  els.modal.setAttribute("aria-hidden", "true");
}

els.queryCount.addEventListener("input", () => {
  els.queryValue.textContent = els.queryCount.value;
});

els.presetGroup.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-preset]");
  if (!button) return;
  state.preset = button.dataset.preset;
  [...els.presetGroup.querySelectorAll("button")].forEach((item) => item.classList.toggle("active", item === button));
  els.repoControl.classList.toggle("visible", state.preset === "custom");
  const defaults = { small: 18, medium: 42, large: 70, custom: 42 };
  els.queryCount.value = defaults[state.preset] || 18;
  els.queryValue.textContent = els.queryCount.value;
  if (state.preset === "custom") {
    els.repoInput.focus();
  }
});

els.startBtn.addEventListener("click", startRun);
els.stopBtn.addEventListener("click", stopRun);
els.closeModal.addEventListener("click", closeSummary);
els.modal.addEventListener("click", (event) => {
  if (event.target === els.modal) closeSummary();
});

window.addEventListener("resize", () => {
  document.querySelectorAll(".spark").forEach((canvas) => {
    const panel = canvas.closest(".engine");
    drawSpark(canvas, state.history.get(panel.dataset.engine) || [], colors[panel.dataset.engine] || "#00f6ff");
  });
  drawAllCharts();
});

drawAllCharts();
