const state = {
  loaded: false,
  loading: false,
};

const $ = (id) => document.getElementById(id);

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function formatMetric(value) {
  return Number.isFinite(value) ? value.toFixed(3) : "-";
}

function setBusy(isBusy, label = "Working") {
  state.loading = isBusy;
  $("loadBtn").disabled = isBusy;
  $("searchBtn").disabled = isBusy || !state.loaded;
  $("benchmarkBtn").disabled = isBusy || !state.loaded;
  if (isBusy) $("status").textContent = label;
}

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function showSummary(summary) {
  state.loaded = true;
  $("summaryPanel").hidden = false;
  $("filesMetric").textContent = summary.files.toLocaleString();
  $("rawBytesMetric").textContent = formatBytes(summary.raw_bytes);
  $("rawStoreMetric").textContent = formatBytes(summary.raw_payload_bytes + summary.raw_index_bytes);
  $("specStoreMetric").textContent = formatBytes(summary.spectrum_bytes);
  $("embeddingStoreMetric").textContent = "Lazy";
  $("status").textContent = "Corpus loaded";
  $("searchBtn").disabled = false;
  $("benchmarkBtn").disabled = false;
}

function renderResults(container, results) {
  if (!results.length) {
    container.className = "results empty";
    container.textContent = "No results";
    return;
  }
  container.className = "results";
  container.replaceChildren(
    ...results.map((result) => {
      const item = document.createElement("article");
      item.className = "result";

      const title = document.createElement("div");
      title.className = "result-title";
      const name = document.createElement("strong");
      name.textContent = `#${result.rank} ${result.name || result.source_path}`;
      const score = document.createElement("span");
      score.className = "score";
      score.textContent = `score ${formatMetric(result.score)}`;
      title.append(name, score);

      const path = document.createElement("p");
      path.className = "path";
      path.textContent = result.source_path || result.path;

      const snippet = document.createElement("p");
      snippet.className = "snippet";
      snippet.textContent = result.snippet || "";

      item.append(title, path, snippet);
      if (Array.isArray(result.matched_tokens) && result.matched_tokens.length) {
        const tokens = document.createElement("div");
        tokens.className = "tokens";
        result.matched_tokens.slice(0, 10).forEach((token) => {
          const pill = document.createElement("span");
          pill.textContent = token;
          tokens.append(pill);
        });
        item.append(tokens);
      }
      return item;
    }),
  );
}

async function loadCorpus() {
  setBusy(true, "Loading corpus");
  try {
    const data = await postJSON("/api/load", {
      path: $("pathInput").value,
      includeAll: $("includeAllInput").checked,
    });
    showSummary(data.summary);
    $("specResults").className = "results empty";
    $("rawResults").className = "results empty";
    $("embeddingResults").className = "results empty";
    $("specResults").textContent = "Corpus loaded. Run a search.";
    $("rawResults").textContent = "Corpus loaded. Run a search.";
    $("embeddingResults").textContent = "Corpus loaded. First search builds embeddings.";
  } catch (error) {
    $("status").textContent = error.message;
  } finally {
    setBusy(false);
    if (state.loaded) $("status").textContent = "Corpus loaded";
  }
}

async function runSearch() {
  setBusy(true, "Searching");
  try {
    const data = await postJSON("/api/search", {
      query: $("queryInput").value,
      topK: Number($("topKInput").value || 5),
    });
    $("specLatency").textContent = `${data.spectrum.query_ms.toFixed(3)} ms`;
    $("rawTitle").textContent = data.raw.backend || "Raw Text Baseline";
    $("rawLatency").textContent = `${data.raw.query_ms.toFixed(3)} ms · ${data.raw.backend || "Raw baseline"}`;
    $("embeddingLatency").textContent = `${data.embedding.query_ms.toFixed(3)} ms`;
    $("embeddingStoreMetric").textContent = formatBytes(data.embedding.memory_bytes);
    renderResults($("specResults"), data.spectrum.results);
    renderResults($("rawResults"), data.raw.results);
    renderResults($("embeddingResults"), data.embedding.results);
    $("embeddingBackend").textContent = `Embedding backend: ${data.embedding.backend}`;
    $("status").textContent = "Search complete";
  } catch (error) {
    $("status").textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function rankText(rank) {
  return rank > 0 ? String(rank) : "miss";
}

async function runBenchmark() {
  setBusy(true, "Benchmarking");
  try {
    const data = await postJSON("/api/benchmark", {
      queries: Number($("queriesInput").value || 60),
      topK: Number($("topKInput").value || 5),
    });
    $("benchOutput").hidden = false;
    $("rawHit").textContent = formatMetric(data.raw.hit_at_1);
    $("specHit").textContent = formatMetric(data.spectrum.hit_at_1);
    $("embeddingHit").textContent = formatMetric(data.embedding.hit_at_1);
    $("rawMrr").textContent = formatMetric(data.raw.mrr);
    $("specMrr").textContent = formatMetric(data.spectrum.mrr);
    $("embeddingMrr").textContent = formatMetric(data.embedding.mrr);
    $("rawAvg").textContent = `${formatMetric(data.raw.avg_query_ms)} ms`;
    $("specAvg").textContent = `${formatMetric(data.spectrum.avg_query_ms)} ms`;
    $("embeddingAvg").textContent = `${formatMetric(data.embedding.avg_query_ms)} ms`;
    $("embeddingStoreMetric").textContent = formatBytes(data.embedding.bytes);
    $("embeddingBackend").textContent = `Raw backend: ${data.raw.backend || "Raw baseline"} · Embedding backend: ${data.embedding.backend}`;

    const rows = data.per_query.map((item) => {
      const row = document.createElement("tr");
      [
        item.query,
        item.expected_path,
        rankText(item.raw_rank),
        rankText(item.spectrum_rank),
        rankText(item.embedding_rank),
      ].forEach((value, idx) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (idx >= 2 && value === "miss") cell.className = "rank-miss";
        row.append(cell);
      });
      return row;
    });
    $("benchRows").replaceChildren(...rows);
    $("status").textContent = `Benchmark complete: ${data.queries} queries`;
  } catch (error) {
    $("status").textContent = error.message;
  } finally {
    setBusy(false);
  }
}

$("loadBtn").addEventListener("click", loadCorpus);
$("searchBtn").addEventListener("click", runSearch);
$("benchmarkBtn").addEventListener("click", runBenchmark);
$("queryInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && state.loaded && !state.loading) runSearch();
});

$("searchBtn").disabled = true;
$("benchmarkBtn").disabled = true;
