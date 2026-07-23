const API_BASE = "/api";
function loadWatchlist() {
  try {
    const stored = JSON.parse(localStorage.getItem("predict_withFun.watchlist") || "[]");
    return Array.isArray(stored) ? stored : [];
  } catch (_) {
    return [];
  }
}

const state = {
  categoryId: "",
  categoryName: "",
  markets: [],
  visibleMarkets: [],
  busy: false,
  watchlist: new Set(loadWatchlist()),
  comparison: new Set(),
  savedAnalyses: [],
};

const $ = (id) => document.getElementById(id);
const categorySelect = $("categorySelect");
const limitSelect = $("limitSelect");
const loadButton = $("loadMarketsBtn");
const analyzeButton = $("analyzeBtn");
const providerSelect = $("providerSelect");
const marketSearch = $("marketSearch");
const marketSort = $("marketSort");
const marketView = $("marketView");

document.addEventListener("DOMContentLoaded", initialize);
categorySelect.addEventListener("change", handleCategoryChange);
loadButton.addEventListener("click", loadMarkets);
analyzeButton.addEventListener("click", analyzeMarkets);
marketSearch.addEventListener("input", applyMarketFilters);
marketSort.addEventListener("change", applyMarketFilters);
marketView.addEventListener("change", applyMarketFilters);
$("exportCsv").addEventListener("click", () => exportMarkets("csv"));
$("exportJson").addEventListener("click", () => exportMarkets("json"));
$("clearComparison").addEventListener("click", () => {
  state.comparison.clear();
  renderComparison();
  applyMarketFilters();
});
$("syncAccuracy").addEventListener("click", syncAccuracy);
$("refreshAnalyses").addEventListener("click", loadSavedAnalyses);
$("analysisSearch").addEventListener("input", renderSavedAnalyses);
$("analysisProvider").addEventListener("change", renderSavedAnalyses);
$("analysisLimit").addEventListener("change", loadSavedAnalyses);
$("loadAdmin").addEventListener("click", loadAdminDashboard);
$("adminToken").value = sessionStorage.getItem("predict_withFun.adminToken") || "";

async function initialize() {
  await Promise.allSettled([
    checkHealth(), loadCategories(), loadAccuracy(), loadSavedAnalyses(),
  ]);
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  let body = {};
  try { body = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) throw new Error(body.detail || "The request failed.");
  return body;
}

async function waitForJob(job, onProgress) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    if (job.status === "finished") return job.result;
    if (job.status === "failed") throw new Error(job.error || "Background job failed.");
    if (onProgress) onProgress(job.status);
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    job = await api(`/jobs/${encodeURIComponent(job.id)}`);
  }
  throw new Error("Background job timed out.");
}

async function checkHealth() {
  try {
    const health = await api("/health");
    const ready = [
      health.openai_configured ? "OpenAI" : null,
      health.grok_configured ? "Grok" : null,
      health.claude_configured ? "Claude" : null,
    ].filter(Boolean);
    const infrastructure = health.redis_configured
      ? ` · Redis + ${health.background_queue.toUpperCase()} jobs`
      : " · Local jobs";
    $("apiStatus").textContent = ready.length
      ? `Live · ${ready.join(" + ")} ready${infrastructure}`
      : health.demo_mode ? `Live · Demo mode${infrastructure}` : "Live · AI key missing";
  } catch (_) {
    $("apiStatus").textContent = "Connection unavailable";
    document.querySelector(".status-dot").classList.add("offline");
  }
}

async function loadAccuracy() {
  try {
    const summaries = await api("/accuracy");
    const grid = $("accuracyGrid");
    if (!summaries.length) return;
    grid.replaceChildren(...summaries.map((summary) => {
      const card = document.createElement("article");
      card.className = "comparison-market";
      const improvement = summary.mean_market_brier_score - summary.mean_brier_score;
      card.innerHTML = `
        <span class="comparison-label"></span>
        <h3></h3>
        <div class="comparison-facts">
          <div><span>Resolved forecasts</span><strong>${summary.resolved_forecasts}</strong></div>
          <div><span>AI Brier score</span><strong>${summary.mean_brier_score.toFixed(4)}</strong></div>
          <div><span>Market Brier score</span><strong>${summary.mean_market_brier_score.toFixed(4)}</strong></div>
          <div><span>vs. market</span><strong class="${improvement > 0 ? "positive" : "negative"}">${improvement > 0 ? "Better" : "Worse"} ${Math.abs(improvement).toFixed(4)}</strong></div>
        </div>
      `;
      card.querySelector(".comparison-label").textContent = "Provider";
      card.querySelector("h3").textContent = summary.provider;
      return card;
    }));
  } catch (_) {
    // Accuracy is optional while the database is being initialized.
  }
}

async function loadSavedAnalyses() {
  const button = $("refreshAnalyses");
  button.disabled = true;
  button.textContent = "Loading …";
  try {
    state.savedAnalyses = await api(`/analyses?limit=${$("analysisLimit").value}`);
    renderSavedAnalyses();
  } catch (error) {
    state.savedAnalyses = [];
    $("savedAnalyses").innerHTML = '<div class="empty-state"></div>';
    $("savedAnalyses").querySelector(".empty-state").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Refresh history";
  }
}

function renderSavedAnalyses() {
  const query = $("analysisSearch").value.trim().toLowerCase();
  const provider = $("analysisProvider").value;
  const records = state.savedAnalyses.filter((item) => (
    (!query || item.category.toLowerCase().includes(query))
    && (provider === "all" || item.provider === provider)
  ));
  const container = $("savedAnalyses");
  if (!records.length) {
    container.innerHTML = '<div class="empty-state">No matching saved analyses.</div>';
    return;
  }
  container.replaceChildren(...records.map((item) => {
    const article = document.createElement("article");
    article.className = "saved-analysis-row";
    const providerName = { openai: "OpenAI", grok: "Grok", claude: "Claude" }[item.provider];
    const created = new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium", timeStyle: "short",
    }).format(new Date(item.created_at));
    article.innerHTML = `
      <div class="saved-analysis-main">
        <span class="comparison-label"></span>
        <h3></h3>
        <p></p>
      </div>
      <div class="saved-analysis-facts">
        <span><strong>${item.market_count}</strong> markets</span>
        <span><strong>$${item.estimated_cost_usd.toFixed(4)}</strong> estimated</span>
      </div>
      <button class="text-button">Open result</button>`;
    article.querySelector(".comparison-label").textContent = providerName;
    article.querySelector("h3").textContent = item.category;
    article.querySelector("p").textContent = created;
    article.querySelector("button").addEventListener("click", () => openSavedAnalysis(item));
    return article;
  }));
}

async function openSavedAnalysis(item) {
  try {
    const analysis = await api(`/analyses/${encodeURIComponent(item.id)}`);
    renderAnalysis(analysis);
    const restored = document.createElement("div");
    restored.className = "saved-result-banner";
    restored.textContent = `Saved analysis · ${new Date(item.created_at).toLocaleString()}`;
    $("analysisContent").prepend(restored);
    $("analysisSection").hidden = false;
    $("analysisSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function syncAccuracy() {
  const button = $("syncAccuracy");
  button.disabled = true;
  button.textContent = "Checking …";
  try {
    const job = await api("/jobs/accuracy-sync", { method: "POST" });
    const result = await waitForJob(job, (status) => {
      button.textContent = status === "queued" ? "Queued …" : "Checking …";
    });
    showNotice(
      `Checked ${result.checked_markets} markets · scored ${result.scored_forecasts} forecasts.`,
      "success",
      3500,
    );
    await loadAccuracy();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Check resolutions";
  }
}

async function loadAdminDashboard() {
  const button = $("loadAdmin");
  const token = $("adminToken").value.trim();
  if (token) sessionStorage.setItem("predict_withFun.adminToken", token);
  else sessionStorage.removeItem("predict_withFun.adminToken");
  button.disabled = true;
  button.textContent = "Loading …";
  try {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const metrics = await api("/admin/metrics", { headers });
    const infrastructure = metrics.redis_configured
      ? (metrics.redis_available ? `Redis · ${metrics.background_queue.toUpperCase()}` : "Redis unavailable")
      : `Local · ${metrics.background_queue.toUpperCase()}`;
    const stats = [
      ["Stored analyses", metrics.stored_analyses],
      ["Estimated spend", `$${metrics.estimated_cost_usd.toFixed(4)}`],
      ["Cache hit rate", `${(metrics.cache_hit_rate * 100).toFixed(1)}%`],
      ["Jobs", `${metrics.jobs_finished} done · ${metrics.jobs_failed} failed`],
      ["Rate limited", metrics.rate_limited],
      ["Infrastructure", infrastructure],
    ];
    $("adminStats").replaceChildren(...stats.map(([label, value]) => {
      const item = document.createElement("div");
      const name = document.createElement("span");
      const amount = document.createElement("strong");
      name.textContent = label;
      amount.textContent = value;
      item.append(name, amount);
      return item;
    }));
    $("adminProviders").replaceChildren(...metrics.providers.map((provider) => {
      const card = document.createElement("article");
      card.className = "comparison-market";
      card.innerHTML = `
        <span class="comparison-label">Provider</span>
        <h3></h3>
        <div class="comparison-facts">
          <div><span>Runtime calls</span><strong>${provider.calls}</strong></div>
          <div><span>Success / failure</span><strong>${provider.successes} / ${provider.failures}</strong></div>
          <div><span>Average latency</span><strong>${provider.average_duration_ms.toFixed(1)} ms</strong></div>
          <div><span>Stored analyses</span><strong>${provider.stored_analyses}</strong></div>
          <div><span>Estimated spend</span><strong>$${provider.estimated_cost_usd.toFixed(4)}</strong></div>
        </div>`;
      card.querySelector("h3").textContent = provider.provider;
      return card;
    }));
    $("adminDashboard").hidden = false;
    showNotice("Admin metrics loaded.", "success", 2400);
  } catch (error) {
    $("adminDashboard").hidden = true;
    showNotice(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Load dashboard";
  }
}

async function loadCategories() {
  setBusy(true, "Loading categories …");
  try {
    const categories = await api("/categories");
    categorySelect.innerHTML = '<option value="">Choose a category</option>';
    categories.forEach(({ id, name }) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = name;
      categorySelect.appendChild(option);
    });
    categorySelect.disabled = false;
    showNotice(`${categories.length} categories available.`, "success", 2400);
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function handleCategoryChange() {
  state.categoryId = categorySelect.value;
  state.categoryName = categorySelect.options[categorySelect.selectedIndex]?.text || "";
  state.markets = [];
  state.visibleMarkets = [];
  state.comparison.clear();
  marketSearch.value = "";
  marketView.value = "all";
  loadButton.disabled = !state.categoryId;
  $("marketsSection").hidden = true;
  $("comparisonSection").hidden = true;
  $("analysisSection").hidden = true;
}

async function loadMarkets() {
  if (!state.categoryId) return;
  setBusy(true, "Processing market data …", loadButton);
  $("analysisSection").hidden = true;
  try {
    state.markets = await api(
      `/markets/${encodeURIComponent(state.categoryId)}?limit=${limitSelect.value}`,
    );
    renderMarkets();
    showNotice(
      state.markets.length
        ? `${state.markets.length} active markets loaded.`
        : "No active markets were found in this category.",
      state.markets.length ? "success" : "neutral",
      2600,
    );
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(false, "", loadButton);
  }
}

function renderMarkets() {
  $("marketsHeading").textContent = state.categoryName;
  applyMarketFilters(false);
  $("marketsSection").hidden = false;
  $("marketsSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyMarketFilters(updateSection = true) {
  const query = marketSearch.value.trim().toLocaleLowerCase();
  const watchlistOnly = marketView.value === "watchlist";
  const sort = marketSort.value;
  const markets = state.markets.filter((market) => {
    const matchesQuery = !query || market.title.toLocaleLowerCase().includes(query);
    const matchesView = !watchlistOnly || state.watchlist.has(market.slug);
    return matchesQuery && matchesView;
  });
  markets.sort((a, b) => {
    if (sort === "liquidity") return (b.liquidity || 0) - (a.liquidity || 0);
    if (sort === "probability-high") return (b.outcomes[0]?.probability || 0) - (a.outcomes[0]?.probability || 0);
    if (sort === "probability-low") return (a.outcomes[0]?.probability || 0) - (b.outcomes[0]?.probability || 0);
    return b.volume - a.volume;
  });
  state.visibleMarkets = markets;
  const totalVolume = markets.reduce((sum, market) => sum + market.volume, 0);
  const totalLiquidity = markets.reduce((sum, market) => sum + (market.liquidity || 0), 0);
  $("marketStats").innerHTML = `
    <div><span>Markets</span><strong>${markets.length}</strong></div>
    <div><span>Volume</span><strong>${formatMoney(totalVolume)}</strong></div>
    <div><span>Liquidity</span><strong>${formatMoney(totalLiquidity)}</strong></div>
  `;
  if (markets.length) {
    $("marketsGrid").replaceChildren(...markets.map(marketCard));
  } else {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = watchlistOnly
      ? "Your watchlist has no markets in this category."
      : "No markets match these filters.";
    $("marketsGrid").replaceChildren(empty);
  }
  analyzeButton.disabled = state.markets.length === 0;
  if (updateSection) renderComparison();
}

function marketCard(market, index) {
  const wrapper = document.createElement("div");
  wrapper.className = "market-wrapper";
  const article = document.createElement("article");
  article.className = "market-card";
  const probability = market.outcomes[0]?.probability;
  const outcomeName = market.outcomes[0]?.title || "Kein Preis";
  article.innerHTML = `
    <div class="card-index">${String(index + 1).padStart(2, "0")}</div>
    <div class="card-main">
      <h3></h3>
      <div class="market-meta">
        <span>Vol. ${formatMoney(market.volume)}</span>
        <span>Liq. ${formatMoney(market.liquidity || 0)}</span>
      </div>
    </div>
    <div class="probability">
      <span></span>
      <strong>${probability == null ? "—" : formatPercent(probability)}</strong>
      <div class="probability-track"><i style="width:${(probability || 0) * 100}%"></i></div>
    </div>
    <div class="card-actions">
      <button class="text-button watch-button">${state.watchlist.has(market.slug) ? "★ Saved" : "☆ Watch"}</button>
      <button class="text-button compare-button">${state.comparison.has(market.slug) ? "✓ Compared" : "Compare"}</button>
      <button class="text-button analyze-one">Analyze</button>
      <button class="text-button history-button">History</button>
      ${market.url ? '<a class="card-link" target="_blank" rel="noopener noreferrer" aria-label="Open market on Polymarket">↗</a>' : ""}
    </div>
  `;
  article.querySelector("h3").textContent = market.title;
  article.querySelector(".probability span").textContent = outcomeName;
  const link = article.querySelector(".card-link");
  if (link) link.href = market.url;
  article.querySelector(".watch-button").addEventListener("click", () => toggleWatchlist(market));
  article.querySelector(".compare-button").addEventListener("click", () => toggleComparison(market));
  article.querySelector(".analyze-one").addEventListener("click", () => analyzeSingleMarket(market, article));
  article.querySelector(".history-button").addEventListener("click", () => showHistory(market, wrapper));
  wrapper.append(article);
  return wrapper;
}

function toggleWatchlist(market) {
  if (state.watchlist.has(market.slug)) state.watchlist.delete(market.slug);
  else state.watchlist.add(market.slug);
  localStorage.setItem("predict_withFun.watchlist", JSON.stringify([...state.watchlist]));
  applyMarketFilters();
}

function toggleComparison(market) {
  if (state.comparison.has(market.slug)) {
    state.comparison.delete(market.slug);
  } else if (state.comparison.size < 3) {
    state.comparison.add(market.slug);
  } else {
    showNotice("You can compare up to three markets.", "neutral", 2400);
    return;
  }
  applyMarketFilters();
}

function renderComparison() {
  const markets = state.markets.filter((market) => state.comparison.has(market.slug));
  $("comparisonSection").hidden = markets.length === 0;
  const grid = $("comparisonGrid");
  grid.replaceChildren();
  markets.forEach((market) => {
    const card = document.createElement("article");
    card.className = "comparison-market";
    const probability = market.outcomes[0]?.probability;
    card.innerHTML = `
      <span class="comparison-label"></span>
      <h3></h3>
      <div class="comparison-facts">
        <div><span>Probability</span><strong>${probability == null ? "—" : formatPercent(probability)}</strong></div>
        <div><span>Volume</span><strong>${formatMoney(market.volume)}</strong></div>
        <div><span>Liquidity</span><strong>${formatMoney(market.liquidity || 0)}</strong></div>
      </div>
    `;
    card.querySelector(".comparison-label").textContent = market.outcomes[0]?.title || "Primary outcome";
    card.querySelector("h3").textContent = market.title;
    grid.append(card);
  });
}

function exportMarkets(format) {
  const markets = state.visibleMarkets;
  if (!markets.length) {
    showNotice("There are no visible markets to export.", "neutral", 2400);
    return;
  }
  const rows = markets.map((market) => ({
    title: market.title,
    probability: market.outcomes[0]?.probability ?? null,
    volume: market.volume,
    liquidity: market.liquidity,
    category: market.category,
    url: market.url,
  }));
  const content = format === "json"
    ? JSON.stringify(rows, null, 2)
    : toCsv(rows);
  downloadFile(
    content,
    `predict_withFun-${state.categoryName.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}.${format}`,
    format === "json" ? "application/json" : "text/csv",
  );
}

function toCsv(rows) {
  const columns = Object.keys(rows[0]);
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return [columns.join(","), ...rows.map((row) => columns.map((column) => escape(row[column])).join(","))].join("\n");
}

function downloadFile(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

async function analyzeSingleMarket(market, article) {
  const button = article.querySelector(".analyze-one");
  button.disabled = true;
  button.textContent = "Analyzing …";
  try {
    if (providerSelect.value === "compare") {
      showNotice("Provider comparison is available for category analysis.", "neutral", 3000);
      return;
    }
    const analysis = await api(
      `/analyze/${encodeURIComponent(state.categoryId)}/${encodeURIComponent(market.slug)}?provider=${providerSelect.value}`,
      { method: "POST" },
    );
    renderAnalysis(analysis);
    await loadSavedAnalyses();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Analyze";
  }
}

async function showHistory(market, wrapper) {
  let panel = wrapper.querySelector(".history-panel");
  if (panel) {
    panel.remove();
    return;
  }
  panel = document.createElement("div");
  panel.className = "history-panel";
  panel.innerHTML = '<span class="history-loading">Loading one-month history …</span>';
  wrapper.append(panel);
  try {
    const history = await api(
      `/history/${encodeURIComponent(state.categoryId)}/${encodeURIComponent(market.slug)}?interval=1m`,
    );
    if (history.length < 2) {
      panel.textContent = "No price history is available for this market.";
      return;
    }
    panel.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "history-heading";
    heading.innerHTML = `<span>One-month price history · ${market.outcomes[0]?.title || "Primary outcome"}</span><strong>${formatPercent(history.at(-1).price)}</strong>`;
    const canvas = document.createElement("canvas");
    canvas.width = 1000;
    canvas.height = 240;
    canvas.setAttribute("aria-label", `Price history for ${market.title}`);
    panel.append(heading, canvas);
    drawHistory(canvas, history);
  } catch (error) {
    panel.textContent = error.message;
  }
}

function drawHistory(canvas, history) {
  const context = canvas.getContext("2d");
  const { width, height } = canvas;
  const padding = 18;
  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#282d37";
  context.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach((value) => {
    const y = padding + (1 - value) * (height - padding * 2);
    context.beginPath();
    context.moveTo(padding, y);
    context.lineTo(width - padding, y);
    context.stroke();
  });
  context.strokeStyle = "#c8f45d";
  context.lineWidth = 4;
  context.lineJoin = "round";
  context.beginPath();
  history.forEach((point, index) => {
    const x = padding + (index / (history.length - 1)) * (width - padding * 2);
    const y = padding + (1 - point.price) * (height - padding * 2);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.stroke();
}

async function analyzeMarkets() {
  if (!state.categoryId || state.markets.length === 0) return;
  setBusy(true, "AI analysis in progress — this may take a moment …", analyzeButton);
  try {
    const limit = Math.min(Number(limitSelect.value), 10);
    const isComparison = providerSelect.value === "compare";
    let analysis = await api(
      isComparison
        ? `/jobs/compare?category_id=${encodeURIComponent(state.categoryId)}&limit=${limit}`
        : `/analyze?category_id=${encodeURIComponent(state.categoryId)}&limit=${limit}&provider=${providerSelect.value}`,
      { method: "POST" },
    );
    if (isComparison) {
      analysis = await waitForJob(analysis, (status) => {
        analyzeButton.innerHTML = `<span class="mini-spinner"></span>${status === "queued" ? "Queued …" : "Comparing providers …"}`;
      });
    }
    if (isComparison) renderComparisonAnalysis(analysis);
    else renderAnalysis(analysis);
    await loadSavedAnalyses();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(false, "", analyzeButton);
  }
}

function renderComparisonAnalysis(comparison) {
  const container = $("analysisContent");
  container.replaceChildren();
  if (comparison.synthesis) {
    const synthesis = document.createElement("section");
    synthesis.className = "synthesis";
    const heading = document.createElement("div");
    heading.className = "synthesis-heading";
    heading.innerHTML = "<span>Consensus synthesis</span><p></p>";
    heading.querySelector("p").textContent = comparison.synthesis.method;
    const weights = document.createElement("div");
    weights.className = "synthesis-weights";
    Object.entries(comparison.synthesis.provider_weights).forEach(([provider, weight]) => {
      const item = document.createElement("span");
      item.textContent = `${provider} ${formatPercent(weight)}`;
      weights.append(item);
    });
    const markets = document.createElement("div");
    markets.className = "synthesis-grid";
    comparison.synthesis.markets.forEach((market) => {
      const card = document.createElement("article");
      card.className = "synthesis-card";
      card.innerHTML = `
        <span class="comparison-label">${market.disagreement} disagreement</span>
        <h3></h3>
        <div class="comparison-facts">
          <div><span>Weighted consensus</span><strong>${formatPercent(market.weighted_probability)}</strong></div>
          <div><span>Median</span><strong>${formatPercent(market.median_probability)}</strong></div>
          <div><span>Provider range</span><strong>${formatPercent(market.minimum_probability)}–${formatPercent(market.maximum_probability)}</strong></div>
          <div><span>Market</span><strong>${formatPercent(market.market_probability)}</strong></div>
        </div>
      `;
      card.querySelector("h3").textContent = market.market_title;
      markets.append(card);
    });
    synthesis.append(heading, weights, markets);
    container.append(synthesis);
  }
  const grid = document.createElement("div");
  grid.className = "provider-comparison";
  comparison.results.forEach((analysis) => {
    const column = document.createElement("section");
    column.className = "provider-result";
    renderAnalysis(analysis, column, false);
    grid.append(column);
  });
  container.append(grid);
  Object.entries(comparison.errors || {}).forEach(([provider, message]) => {
    const error = document.createElement("div");
    error.className = "demo-banner";
    error.textContent = `${provider}: ${message}`;
    container.append(error);
  });
  $("analysisSection").hidden = false;
  $("analysisSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderAnalysis(analysis, container = $("analysisContent"), reset = true) {
  if (reset) container.replaceChildren();

  if (analysis.demo) {
    const demo = document.createElement("div");
    demo.className = "demo-banner";
    const demoMessages = {
      grok: "Demo mode · Configure XAI_API_KEY for live X research.",
      claude: "Demo mode · Configure ANTHROPIC_API_KEY for live Claude web research.",
      openai: "Demo mode · Configure OPENAI_API_KEY for live web research.",
    };
    demo.textContent = demoMessages[analysis.research_provider];
    container.append(demo);
  }

  const providerBadge = document.createElement("div");
  providerBadge.className = "provider-badge";
  const providerLabels = {
    grok: "Grok · X research",
    claude: "Claude · Web research",
    openai: "OpenAI · Web research",
  };
  providerBadge.textContent = providerLabels[analysis.research_provider];
  container.append(providerBadge);

  const usage = document.createElement("div");
  usage.className = "usage-strip";
  const fallback = analysis.fallback_used
    ? ` · fallback from ${analysis.requested_provider}`
    : "";
  usage.textContent = analysis.cached
    ? `Cached result · $0.000000 new API cost${fallback}`
    : `${analysis.usage.input_tokens.toLocaleString()} input · ${analysis.usage.output_tokens.toLocaleString()} output · ${analysis.usage.search_calls} searches · est. $${analysis.usage.estimated_cost_usd.toFixed(6)}${fallback}`;
  container.append(usage);

  const summary = document.createElement("div");
  summary.className = "analysis-summary";
  summary.innerHTML = "<span>Summary</span><p></p>";
  summary.querySelector("p").textContent = analysis.summary;
  container.append(summary);

  if (analysis.overall_insights) {
    const insight = document.createElement("blockquote");
    insight.textContent = analysis.overall_insights;
    container.append(insight);
  }

  const grid = document.createElement("div");
  grid.className = "analysis-grid";
  analysis.markets.forEach((item) => grid.append(analysisCard(item)));
  container.append(grid);

  if (analysis.sources?.length) {
    const sources = document.createElement("div");
    sources.className = "sources";
    const title = document.createElement("h3");
    title.textContent = "Sources";
    sources.append(title);
    analysis.sources.forEach((source, index) => {
      const row = document.createElement("div");
      row.className = "source-row";
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${index + 1}. ${source.title}`;
      const metadata = document.createElement("div");
      metadata.className = "source-meta";
      const category = document.createElement("span");
      category.textContent = source.category;
      const quality = document.createElement("span");
      quality.className = `source-quality quality-${source.quality}`;
      quality.textContent = `${source.quality} · ${Math.round(source.quality_score * 100)}`;
      quality.title = source.quality_reason;
      const domain = document.createElement("span");
      domain.textContent = source.domain;
      metadata.append(category, quality, domain);
      row.append(link, metadata);
      sources.append(row);
    });
    container.append(sources);
  }

  const disclaimer = document.createElement("p");
  disclaimer.className = "disclaimer";
  disclaimer.textContent = analysis.disclaimer;
  container.append(disclaimer);

  if (reset) {
    $("analysisSection").hidden = false;
    $("analysisSection").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function analysisCard(item) {
  const article = document.createElement("article");
  article.className = "analysis-card";
  const delta = item.fair_probability == null
    ? null
    : item.fair_probability - item.market_probability;
  article.innerHTML = `
    <div class="analysis-card-head">
      <span class="badge badge-${assessmentClass(item.assessment)}"></span>
      <h3></h3>
    </div>
    <div class="comparison">
      <div><span>Market</span><strong>${formatPercent(item.market_probability)}</strong></div>
      <div><span>AI estimate</span><strong>${item.fair_probability == null ? "—" : formatPercent(item.fair_probability)}</strong></div>
      <div><span>Difference</span><strong class="${delta == null ? "" : delta >= 0 ? "positive" : "negative"}">${delta == null ? "—" : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp`}</strong></div>
    </div>
    <p class="reasoning"></p>
    <div class="risks"></div>
  `;
  article.querySelector(".badge").textContent = item.assessment;
  article.querySelector("h3").textContent = item.market_title;
  article.querySelector(".reasoning").textContent = item.reasoning;
  const risks = article.querySelector(".risks");
  item.risks.forEach((risk) => {
    const span = document.createElement("span");
    span.textContent = risk;
    risks.append(span);
  });
  return article;
}

function setBusy(busy, message = "", button = null) {
  state.busy = busy;
  if (button) {
    if (!button.dataset.label) button.dataset.label = button.innerHTML;
    button.innerHTML = busy ? `<span class="mini-spinner"></span>${message}` : button.dataset.label;
  }
  categorySelect.disabled = busy || categorySelect.options.length <= 1;
  limitSelect.disabled = busy;
  providerSelect.disabled = busy;
  loadButton.disabled = busy || !state.categoryId;
  analyzeButton.disabled = busy || state.markets.length === 0;
}

function showNotice(message, type = "neutral", timeout = 0) {
  const notice = $("notice");
  notice.textContent = message;
  notice.className = `notice notice-${type}`;
  notice.hidden = false;
  if (timeout) window.setTimeout(() => { notice.hidden = true; }, timeout);
}

function assessmentClass(value) {
  if (value.includes("under")) return "under";
  if (value.includes("over")) return "over";
  return "fair";
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1,
  }).format(value);
}

function formatPercent(value) {
  return new Intl.NumberFormat("en-US", {
    style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1,
  }).format(value);
}
