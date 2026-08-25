const $ = (id) => document.getElementById(id);
const state = { timer: null, busy: false, paused: false, code: "", position: "", lastKey: "", history: [] };
const API_BASE_URL = String(window.APP_CONFIG?.API_BASE_URL || "").replace(/\/+$/, "");

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

function number(value, digits = 2) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "--";
}
function price(value) { return Number.isFinite(Number(value)) ? `¥ ${Number(value).toFixed(2)}` : "--"; }
function percent(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : "--"; }
function timeText(value) {
  if (!value) return "时间戳待核验";
  const d = new Date(value);
  return Number.isNaN(d.valueOf()) ? value : d.toLocaleTimeString("zh-CN", { hour12: false });
}

function setLive(kind, text) {
  $("liveDot").className = `dot ${kind || ""}`;
  $("liveText").textContent = text;
}
function setError(message = "") {
  $("error").hidden = !message;
  $("error").textContent = message;
}
function hideDashboard() {
  $("dashboard").hidden = true;
}
function updateRefreshButton() {
  const button = $("refreshToggleBtn");
  button.hidden = !state.code;
  button.textContent = state.paused ? "继续刷新" : "暂停刷新";
  button.setAttribute("aria-pressed", String(state.paused));
}
function scheduleRefresh() {
  clearInterval(state.timer);
  state.timer = null;
  if (!state.paused && state.code) state.timer = setInterval(refresh, 3000);
}
function listInto(id, items) {
  const list = $(id);
  list.replaceChildren();
  (items?.length ? items : ["暂无"]).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
}

function actionClass(action) {
  if (["EXIT"].includes(action)) return "exit";
  if (["TRIM"].includes(action)) return "trim";
  if (["VERIFY", "NOT_APPLICABLE"].includes(action)) return "verify";
  return "hold";
}
function operationText(decision) {
  if (!decision.sell_ratio_pct) return "暂不卖出";
  const qty = Number(decision.sell_quantity);
  return qty > 0 ? `卖出 ${qty} 股（${decision.sell_ratio_pct}%）` : `卖出 ${decision.sell_ratio_pct}%`;
}

function pushHistory(data) {
  const d = data.decision;
  const key = [d.action, d.sell_ratio_pct, d.headline].join("|");
  if (key === state.lastKey) return;
  state.lastKey = key;
  state.history.unshift({ at: data.server_time, label: d.label, headline: d.headline });
  state.history = state.history.slice(0, 12);
  const box = $("history");
  box.className = "history-list";
  box.replaceChildren();
  state.history.forEach((item) => {
    const row = document.createElement("div");
    row.className = "history-item";
    const at = document.createElement("time");
    at.textContent = timeText(item.at);
    const label = document.createElement("span");
    label.textContent = item.label;
    const text = document.createElement("strong");
    text.textContent = item.headline;
    row.append(at, label, text);
    box.appendChild(row);
  });
}

function render(data) {
  const { quote: q, profile: p, decision: d } = data;
  $("dashboard").hidden = false;
  $("decisionCard").className = `decision-card ${actionClass(d.action)}`;
  $("actionLabel").textContent = d.label;
  $("confidence").textContent = `${({ high: "高", medium: "中", low: "低" }[d.confidence] || "低")}置信度`;
  $("headline").textContent = d.headline;
  $("operation").textContent = operationText(d);
  $("executionPrice").textContent = price(d.execution_reference);
  $("guardPrice").textContent = price(d.protection_reference);
  $("bestWindow").textContent = `当前最优窗口：${d.best_window}`;
  $("urgency").textContent = `时效：${d.urgency}`;

  $("stockName").textContent = `${q.name || p?.name || "未知证券"} · ${q.code}`;
  const listing = p?.listing_date ? `上市日 ${p.listing_date}` : "上市日待核验";
  const issue = Number.isFinite(Number(p?.issue_price)) ? `发行价 ¥${Number(p.issue_price).toFixed(2)}` : "发行价待核验";
  $("stockMeta").textContent = `${listing} · ${issue}`;
  $("currentPrice").textContent = price(q.price);
  $("quoteTime").textContent = `${timeText(q.market_time)} · ${q.source}`;
  $("openPrice").textContent = price(q.open);
  $("highPrice").textContent = price(q.high);
  $("vwap").textContent = price(q.vwap);
  $("pullback").textContent = percent(d.metrics.pullback_pct);
  $("turnover").textContent = percent(q.turnover_pct);
  $("openPremium").textContent = percent(d.metrics.open_premium_pct);
  $("quoteSource").textContent = q.source;
  listInto("reasons", d.reasons);
  listInto("warnings", d.warnings);
  pushHistory(data);
}

async function refresh() {
  if (state.busy || state.paused || !state.code) return;
  state.busy = true;
  $("startBtn").disabled = true;
  setLive("active", "正在更新");
  setError();
  const params = new URLSearchParams({ code: state.code });
  if (state.position) params.set("position", state.position);
  const token = localStorage.getItem("bseAccessToken") || "";
  try {
    const response = await fetch(apiUrl(`/api/analyze?${params}`), {
      cache: "no-store",
      headers: token ? { "X-App-Token": token } : {},
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) $("accessBox").open = true;
      if (response.status === 409) {
        state.paused = true;
        scheduleRefresh();
        updateRefreshButton();
      }
      throw new Error(payload.detail || payload.error || `服务返回 ${response.status}`);
    }
    render(payload);
    const sourceTime = payload.quote?.market_time;
    setLive("active", sourceTime ? `自动刷新 · ${timeText(sourceTime)}` : "自动刷新");
  } catch (error) {
    hideDashboard();
    setLive("error", "更新失败");
    setError(error.message || "无法读取行情，请稍后重试");
  } finally {
    state.busy = false;
    $("startBtn").disabled = false;
  }
}

$("searchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const code = $("code").value.replace(/\D/g, "");
  if (code.length !== 6) return setError("请输入 6 位北交所证券代码");
  state.code = code;
  state.position = $("position").value.trim();
  state.paused = false;
  state.lastKey = "";
  state.history = [];
  hideDashboard();
  history.replaceState(null, "", `?code=${encodeURIComponent(code)}`);
  updateRefreshButton();
  refresh();
  scheduleRefresh();
});

$("refreshToggleBtn").addEventListener("click", () => {
  if (!state.code) return;
  state.paused = !state.paused;
  updateRefreshButton();
  scheduleRefresh();
  if (state.paused) {
    setLive("", "已暂停刷新");
  } else {
    setLive("active", "正在恢复刷新");
    refresh();
  }
});

$("saveToken").addEventListener("click", () => {
  const value = $("accessToken").value.trim();
  if (value) localStorage.setItem("bseAccessToken", value);
  else localStorage.removeItem("bseAccessToken");
  setError();
  if (state.code && !state.paused) refresh();
});

const launchParams = new URLSearchParams(location.hash.replace(/^#/, ""));
const launchToken = launchParams.get("token")?.trim() || "";
if (/^[A-Za-z0-9_-]{12,128}$/.test(launchToken)) {
  localStorage.setItem("bseAccessToken", launchToken);
  history.replaceState(null, "", `${location.pathname}${location.search}`);
}

const initialCode = new URLSearchParams(location.search).get("code")?.replace(/\D/g, "") || "";
$("accessToken").value = localStorage.getItem("bseAccessToken") || "";
if (initialCode.length === 6) {
  $("code").value = initialCode;
  $("searchForm").requestSubmit();
}

window.addEventListener("offline", () => {
  setLive("error", "网络已断开");
  setError("实时行情需要网络连接；恢复网络后将自动重试。");
});
window.addEventListener("online", () => {
  setError();
  if (state.code && !state.paused) refresh();
  else setLive("", "网络已恢复");
});
