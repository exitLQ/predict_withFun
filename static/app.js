const API_BASE = "/api";
const state = { categoryId: "", categoryName: "", markets: [], busy: false };

const $ = (id) => document.getElementById(id);
const categorySelect = $("categorySelect");
const limitSelect = $("limitSelect");
const loadButton = $("loadMarketsBtn");
const analyzeButton = $("analyzeBtn");

document.addEventListener("DOMContentLoaded", initialize);
categorySelect.addEventListener("change", handleCategoryChange);
loadButton.addEventListener("click", loadMarkets);
analyzeButton.addEventListener("click", analyzeMarkets);

async function initialize() {
  await Promise.allSettled([checkHealth(), loadCategories()]);
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  let body = {};
  try { body = await response.json(); } catch (_) { /* empty response */ }
  if (!response.ok) throw new Error(body.detail || "Die Anfrage ist fehlgeschlagen.");
  return body;
}

async function checkHealth() {
  try {
    const health = await api("/health");
    $("apiStatus").textContent = health.openai_configured
      ? "Live · KI bereit"
      : "Live · KI-Schlüssel fehlt";
  } catch (_) {
    $("apiStatus").textContent = "Verbindung nicht verfügbar";
    document.querySelector(".status-dot").classList.add("offline");
  }
}

async function loadCategories() {
  setBusy(true, "Kategorien werden geladen …");
  try {
    const categories = await api("/categories");
    categorySelect.innerHTML = '<option value="">Kategorie auswählen</option>';
    categories.forEach(({ id, name }) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = name;
      categorySelect.appendChild(option);
    });
    categorySelect.disabled = false;
    showNotice(`${categories.length} Kategorien verfügbar.`, "success", 2400);
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
  loadButton.disabled = !state.categoryId;
  $("marketsSection").hidden = true;
  $("analysisSection").hidden = true;
}

async function loadMarkets() {
  if (!state.categoryId) return;
  setBusy(true, "Marktdaten werden ausgewertet …", loadButton);
  $("analysisSection").hidden = true;
  try {
    state.markets = await api(
      `/markets/${encodeURIComponent(state.categoryId)}?limit=${limitSelect.value}`,
    );
    renderMarkets();
    showNotice(
      state.markets.length
        ? `${state.markets.length} aktive Märkte geladen.`
        : "In dieser Kategorie wurden keine aktiven Märkte gefunden.",
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
  const totalVolume = state.markets.reduce((sum, market) => sum + market.volume, 0);
  const totalLiquidity = state.markets.reduce((sum, market) => sum + (market.liquidity || 0), 0);
  $("marketStats").innerHTML = `
    <div><span>Märkte</span><strong>${state.markets.length}</strong></div>
    <div><span>Volumen</span><strong>${formatMoney(totalVolume)}</strong></div>
    <div><span>Liquidität</span><strong>${formatMoney(totalLiquidity)}</strong></div>
  `;
  $("marketsGrid").replaceChildren(...state.markets.map(marketCard));
  analyzeButton.disabled = state.markets.length === 0;
  $("marketsSection").hidden = false;
  $("marketsSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function marketCard(market, index) {
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
    ${market.url ? '<a class="card-link" target="_blank" rel="noopener noreferrer" aria-label="Markt bei Polymarket öffnen">↗</a>' : ""}
  `;
  article.querySelector("h3").textContent = market.title;
  article.querySelector(".probability span").textContent = outcomeName;
  const link = article.querySelector(".card-link");
  if (link) link.href = market.url;
  return article;
}

async function analyzeMarkets() {
  if (!state.categoryId || state.markets.length === 0) return;
  setBusy(true, "KI-Analyse läuft – das kann einen Moment dauern …", analyzeButton);
  try {
    const limit = Math.min(Number(limitSelect.value), 10);
    const analysis = await api(
      `/analyze?category_id=${encodeURIComponent(state.categoryId)}&limit=${limit}`,
      { method: "POST" },
    );
    renderAnalysis(analysis);
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    setBusy(false, "", analyzeButton);
  }
}

function renderAnalysis(analysis) {
  const container = $("analysisContent");
  container.replaceChildren();

  const summary = document.createElement("div");
  summary.className = "analysis-summary";
  summary.innerHTML = "<span>Zusammenfassung</span><p></p>";
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

  const disclaimer = document.createElement("p");
  disclaimer.className = "disclaimer";
  disclaimer.textContent = analysis.disclaimer;
  container.append(disclaimer);

  $("analysisSection").hidden = false;
  $("analysisSection").scrollIntoView({ behavior: "smooth", block: "start" });
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
      <div><span>Markt</span><strong>${formatPercent(item.market_probability)}</strong></div>
      <div><span>KI-Schätzung</span><strong>${item.fair_probability == null ? "—" : formatPercent(item.fair_probability)}</strong></div>
      <div><span>Differenz</span><strong class="${delta == null ? "" : delta >= 0 ? "positive" : "negative"}">${delta == null ? "—" : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp`}</strong></div>
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
  if (value.includes("unter")) return "under";
  if (value.includes("über")) return "over";
  return "fair";
}

function formatMoney(value) {
  return new Intl.NumberFormat("de-DE", {
    style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1,
  }).format(value);
}

function formatPercent(value) {
  return new Intl.NumberFormat("de-DE", {
    style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1,
  }).format(value);
}
