"use strict";

const $ = (id) => document.getElementById(id);
const configuredBase = String(window.APP_CONFIG?.apiBaseUrl || "").replace(/\/+$/, "");
const API = configuredBase;
let accessToken = "";
const state = { conversationId: null, busy: false, records: [], page: 1, pageSize: 12, dataLoaded: false, editing: null, deleting: null };
const welcome = $("welcome");

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notice(message, type = "") {
  $("notice").textContent = message;
  $("notice").className = `notice ${type}`;
  $("notice").hidden = !message;
}
function openAccess() {
  $("access-button").hidden = false;
  if (!$("access-dialog").open) $("access-dialog").showModal();
}
async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(API + path, {
      ...options,
      headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(accessToken ? { "X-App-Token": accessToken } : {}), ...(options.headers || {}) },
      signal: controller.signal,
    });
    const payload = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const detail = payload?.detail;
      let message = typeof detail === "string" ? detail : detail?.message;
      if (Array.isArray(detail)) message = "입력 내용을 확인해 주세요. 날짜·기온·메모 형식이 올바르지 않습니다.";
      const error = new Error(message || `요청을 처리하지 못했습니다. (${response.status})`);
      error.reply = detail?.reply;
      if (detail?.code === "access_denied") { accessToken = ""; openAccess(); }
      throw error;
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("서버 응답을 기다리는 시간이 초과됐습니다. 서버 실행 상태를 확인하세요. 자동 재요청하지 않았습니다.");
    if (error instanceof TypeError) throw new Error("서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.");
    throw error;
  } finally { clearTimeout(timer); }
}
function rememberConversation(id) {
  state.conversationId = id;
  try { if (id) sessionStorage.setItem("weather-conversation", id); else sessionStorage.removeItem("weather-conversation"); } catch { /* 저장 불가 시 현재 화면에서만 유지 */ }
}
function setBusy(value) {
  state.busy = value;
  $("send").disabled = value;
  $("question").disabled = value;
  $("new-chat").disabled = value;
  $("thinking").hidden = !value;
  document.querySelectorAll(".history-open,.history-delete,.suggestions button").forEach((button) => { button.disabled = value; });
}
function showView(name) {
  $("chat-view").hidden = name !== "chat";
  $("data-view").hidden = name !== "data";
  document.querySelectorAll("[data-view]").forEach((button) => {
    const selected = button.dataset.view === name;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  if (name === "data" && !state.dataLoaded) loadData().catch((error) => notice(error.message, "error"));
}
function addMessage(role, content) {
  welcome.remove();
  const node = element("div", undefined, `message ${role}`);
  node.append(element("span", role === "user" ? "나의 질문" : "대전 기온 비서", "message-label"), document.createTextNode(content));
  $("messages").append(node);
  $("messages").scrollTop = $("messages").scrollHeight;
}
function renderMessages(messages) {
  $("messages").replaceChildren();
  if (!messages.length) $("messages").append(welcome);
  for (const message of messages) addMessage(message.role, message.content);
}
function formatTemp(value) { return Number.isFinite(value) ? `${value.toFixed(2).replace(/\.?0+$/, "")}℃` : "—"; }
function renderMetric(id, value, suffix) {
  $(id).replaceChildren(document.createTextNode(Number.isFinite(value) ? String(value) : "—"));
  if (Number.isFinite(value)) $(id).append(element("small", suffix));
}
async function loadSummary() {
  const data = await request("/api/data/summary");
  renderMetric("average", data.metrics?.average, "℃");
  renderMetric("maximum", data.metrics?.max, "℃");
  renderMetric("minimum", data.metrics?.min, "℃");
  renderMetric("record-count", data.count, "건");
  $("period").textContent = data.period || "저장된 데이터가 없습니다";
  $("warmest").textContent = data.warmest_dates?.join(" · ") || "—";
  $("coldest").textContent = data.coldest_dates?.join(" · ") || "—";
  $("trend-note").textContent = data.trend
    ? `${data.trend.comparison}: ${Number(data.trend.difference_celsius).toFixed(2)}℃ · ${data.trend.direction}`
    : "비교할 월별 데이터가 아직 충분하지 않습니다.";
  drawChart(data.monthly || []);
}
function drawChart(monthly) {
  const host = $("monthly-chart");
  host.replaceChildren();
  const rows = monthly.filter((row) => Number.isFinite(row.average));
  if (!rows.length) { host.append(element("p", "표시할 기온 기록이 없습니다.", "empty-note")); return; }
  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("viewBox", "0 0 400 230");
  const add = (tag, attributes, content) => {
    const node = document.createElementNS(namespace, tag);
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
    if (content !== undefined) node.textContent = content;
    svg.append(node);
    return node;
  };
  const low = Math.floor(Math.min(...rows.map((row) => row.average), 0) / 10) * 10;
  const high = Math.ceil(Math.max(...rows.map((row) => row.average), 10) / 10) * 10;
  const x = (index) => 35 + index * 345 / Math.max(rows.length - 1, 1);
  const y = (value) => 192 - (value - low) / (high - low || 1) * 171;
  for (let tick = low; tick <= high; tick += 10) {
    add("line", { x1: 35, x2: 380, y1: y(tick), y2: y(tick), stroke: "#edf1f7", "stroke-dasharray": "3 4" });
    add("text", { x: 23, y: y(tick) + 4, fill: "#9aa8bc", "font-size": 10, "text-anchor": "end" }, tick);
  }
  const points = rows.map((row, index) => `${x(index)},${y(row.average)}`).join(" ");
  add("polygon", { points: `${x(0)},192 ${points} ${x(rows.length - 1)},192`, fill: "#eff5ff" });
  add("polyline", { points, stroke: "#3b7bee", "stroke-width": 2.5, fill: "none", "stroke-linejoin": "round" });
  rows.forEach((row, index) => {
    const dot = add("circle", { cx: x(index), cy: y(row.average), r: 3, fill: "white", stroke: "#3b7bee", "stroke-width": 2 });
    const title = document.createElementNS(namespace, "title");
    title.textContent = `${row.month}: ${row.average}℃`;
    dot.append(title);
    if (rows.length <= 14 || index % Math.ceil(rows.length / 12) === 0) {
      add("text", { x: x(index), y: 216, fill: "#9aa8bc", "font-size": 9, "text-anchor": "middle" }, rows.length <= 12 ? `${Number(row.month.slice(5))}월` : row.month);
    }
  });
  host.setAttribute("aria-label", rows.map((row) => `${row.month} 평균 ${row.average}도`).join(", "));
  host.append(svg);
}
async function loadHistory() {
  const rows = await request("/api/conversations");
  const host = $("history-list");
  host.replaceChildren();
  if (!rows.length) host.append(element("p", "아직 저장된 대화가 없습니다.", "side-empty"));
  rows.forEach((row) => {
    const item = element("div", undefined, "history-item");
    item.classList.toggle("selected", row.id === state.conversationId);
    const open = element("button", undefined, "history-open");
    open.type = "button";
    open.dataset.id = row.id;
    open.disabled = state.busy;
    open.append(element("strong", row.title || "이전 대화"));
    const date = new Date(row.updated_at);
    open.append(element("small", Number.isNaN(date.valueOf()) ? "저장된 대화" : date.toLocaleDateString("ko-KR")));
    open.addEventListener("click", () => loadConversation(row.id).catch((error) => notice(error.message, "error")));
    const remove = element("button", "×", "history-delete");
    remove.type = "button";
    remove.disabled = state.busy;
    remove.setAttribute("aria-label", `${row.title || "대화"} 삭제`);
    remove.addEventListener("click", () => openDelete("conversation", row.id, row.title || "이전 대화"));
    item.append(open, remove);
    host.append(item);
  });
}
async function loadConversation(id) {
  if (state.busy) return;
  const data = await request(`/api/conversations/${encodeURIComponent(id)}`);
  rememberConversation(id);
  renderMessages(data.messages || []);
  $("conversation-status").textContent = "저장된 대화를 불러왔습니다 · 이어서 질문할 수 있습니다";
  showView("chat");
  document.querySelectorAll(".history-item").forEach((item) => item.classList.toggle("selected", item.querySelector(".history-open")?.dataset.id === id));
  notice("");
}
function newChat() {
  if (state.busy) return;
  rememberConversation(null);
  renderMessages([]);
  $("question").value = "";
  $("char-count").textContent = "0 / 2000";
  $("conversation-status").textContent = "새 대화 · 답변은 자동으로 저장됩니다";
  document.querySelectorAll(".history-item").forEach((item) => item.classList.remove("selected"));
  showView("chat");
  notice("");
  $("question").focus();
}
$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("question").value.trim();
  if (!message || state.busy) return;
  addMessage("user", message);
  $("question").value = "";
  $("char-count").textContent = "0 / 2000";
  notice("");
  setBusy(true);
  const slow = setTimeout(() => notice("서버 응답을 기다리고 있습니다. 처음 접속할 때는 준비에 시간이 걸릴 수 있습니다."), 12000);
  try {
    const result = await request("/api/chat", { method: "POST", body: JSON.stringify({ message, conversation_id: state.conversationId }) });
    addMessage("assistant", result.reply);
    rememberConversation(result.conversation_id);
    $("conversation-status").textContent = "대화가 저장됐습니다 · 이어서 질문할 수 있습니다";
    notice("");
    try { await loadHistory(); } catch { notice("답변과 대화는 저장됐지만 목록을 갱신하지 못했습니다. 목록의 새로고침을 눌러주세요."); }
  } catch (error) {
    if (error.reply) addMessage("assistant", error.reply);
    $("conversation-status").textContent = "이번 요청은 저장되지 않았습니다";
    notice(error.message, "error");
    if (!error.reply) $("question").value = message;
    $("char-count").textContent = `${$("question").value.length} / 2000`;
  } finally { clearTimeout(slow); setBusy(false); $("question").focus(); }
});
$("question").addEventListener("input", () => { $("char-count").textContent = `${$("question").value.length} / 2000`; });
$("question").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("chat-form").requestSubmit(); }
});
$("messages").addEventListener("click", (event) => {
  const button = event.target.closest("[data-question]");
  if (!button || state.busy) return;
  $("question").value = button.dataset.question;
  $("question").dispatchEvent(new Event("input"));
  $("question").focus();
});
$("new-chat").addEventListener("click", newChat);
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
$("refresh-history").addEventListener("click", () => loadHistory().catch((error) => notice(error.message, "error")));
async function loadData() {
  state.records = await request("/api/data");
  state.dataLoaded = true;
  renderTable();
}
function renderTable() {
  const query = $("search").value.trim().toLowerCase();
  const rows = state.records.filter((row) => `${row.date} ${row.memo}`.toLowerCase().includes(query));
  const pages = Math.max(1, Math.ceil(rows.length / state.pageSize));
  state.page = Math.min(state.page, pages);
  const start = (state.page - 1) * state.pageSize;
  const host = $("data-rows");
  host.replaceChildren();
  rows.slice(start, start + state.pageSize).forEach((row) => {
    const tr = element("tr");
    tr.append(element("td", row.date), element("td", formatTemp(row.value)), element("td", row.memo || "—"));
    const actions = element("td");
    const edit = element("button", "수정", "row-button");
    edit.type = "button";
    edit.setAttribute("aria-label", `${row.date} ${row.memo || "기온"} 수정`);
    edit.addEventListener("click", () => openEdit(row));
    const remove = element("button", "삭제", "row-button delete");
    remove.type = "button";
    remove.setAttribute("aria-label", `${row.date} ${row.memo || "기온"} 삭제`);
    remove.addEventListener("click", () => openDelete("data", row.id, `${row.date} · ${formatTemp(row.value)} · ${row.memo || "메모 없음"}`));
    actions.append(edit, remove);
    tr.append(actions);
    host.append(tr);
  });
  $("table-count").textContent = `${state.records.length}건`;
  $("data-empty").hidden = rows.length > 0;
  $("page-info").textContent = rows.length ? `${start + 1}–${Math.min(start + state.pageSize, rows.length)} / ${rows.length}건` : "0건";
  $("page-prev").disabled = state.page <= 1;
  $("page-next").disabled = state.page >= pages;
}
$("search").addEventListener("input", () => { state.page = 1; renderTable(); });
$("page-prev").addEventListener("click", () => { state.page--; renderTable(); });
$("page-next").addEventListener("click", () => { state.page++; renderTable(); });
function formRecord(prefix) {
  const value = Number($(`${prefix}-value`).value);
  if (!$(`${prefix}-value`).value.trim() || !Number.isFinite(value)) throw new Error("기온을 숫자로 입력하세요.");
  return { date: $(`${prefix}-date`).value, value, memo: $(`${prefix}-memo`).value.trim() };
}
async function refreshAfterSave(message) {
  const results = await Promise.allSettled([loadSummary(), loadData()]);
  const failed = results.some((result) => result.status === "rejected");
  notice(failed ? `${message} 다만 화면을 갱신하지 못했습니다. 새로고침을 눌러주세요.` : message, failed ? "" : "success");
}
$("data-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  if (button.disabled) return;
  button.disabled = true;
  try {
    await request("/api/data", { method: "POST", body: JSON.stringify(formRecord("data")) });
    $("data-form").reset();
    state.page = 1;
    await refreshAfterSave("데이터를 추가했습니다.");
  } catch (error) { notice(error.message, "error"); }
  finally { button.disabled = false; }
});
function openEdit(row) {
  state.editing = row.id;
  $("edit-date").value = row.date;
  $("edit-value").value = row.value;
  $("edit-memo").value = row.memo || "";
  $("edit-error").textContent = "";
  $("edit-dialog").showModal();
}
$("edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (document.body.classList.contains("modal-busy")) return;
  document.body.classList.add("modal-busy");
  try {
    await request(`/api/data/${encodeURIComponent(state.editing)}`, { method: "PUT", body: JSON.stringify(formRecord("edit")) });
    $("edit-dialog").close();
    await refreshAfterSave("수정한 내용을 저장했습니다.");
  } catch (error) { $("edit-error").textContent = error.message; }
  finally { document.body.classList.remove("modal-busy"); }
});
function openDelete(type, id, description) {
  if (type === "conversation" && state.busy) return;
  state.deleting = { type, id };
  $("delete-title").textContent = type === "conversation" ? "이 대화를 삭제할까요?" : "이 기온 기록을 삭제할까요?";
  $("delete-description").textContent = description;
  $("delete-error").textContent = "";
  $("delete-dialog").showModal();
}
$("confirm-delete").addEventListener("click", async () => {
  if (document.body.classList.contains("modal-busy")) return;
  const pending = state.deleting;
  if (!pending) return;
  document.body.classList.add("modal-busy");
  try {
    const kind = pending.type === "conversation" ? "conversations" : "data";
    await request(`/api/${kind}/${encodeURIComponent(pending.id)}`, { method: "DELETE" });
    $("delete-dialog").close();
    state.deleting = null;
    if (kind === "conversations") {
      if (state.conversationId === pending.id) newChat();
      try { await loadHistory(); notice("대화를 삭제했습니다.", "success"); }
      catch { notice("대화는 삭제됐지만 목록을 갱신하지 못했습니다. 새로고침을 눌러주세요."); }
    } else await refreshAfterSave("기온 기록을 삭제했습니다.");
  } catch (error) { $("delete-error").textContent = error.message; }
  finally { document.body.classList.remove("modal-busy"); }
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => { if (!document.body.classList.contains("modal-busy")) $(button.dataset.close).close(); }));
document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("cancel", (event) => { if (document.body.classList.contains("modal-busy")) event.preventDefault(); }));
$("refresh-all").addEventListener("click", async () => {
  const button = $("refresh-all");
  button.disabled = true;
  const tasks = [loadSummary(), loadHistory()];
  if (state.dataLoaded) tasks.push(loadData());
  const results = await Promise.allSettled(tasks);
  const errors = results.filter((result) => result.status === "rejected");
  notice(errors.length ? errors[0].reason.message : "저장된 최신 기록으로 갱신했습니다.", errors.length ? "error" : "success");
  button.disabled = false;
});
async function startWorkspace() {
  const results = await Promise.allSettled([loadSummary(), loadHistory()]);
  const failed = results.find((result) => result.status === "rejected");
  if (failed) notice(failed.reason.message, "error");
  let savedId;
  try { savedId = sessionStorage.getItem("weather-conversation"); } catch { /* 복원 없이 시작 */ }
  if (savedId) {
    try { await loadConversation(savedId); }
    catch { rememberConversation(null); }
  }
}
$("access-button").addEventListener("click", openAccess);
$("access-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  if (button.disabled) return;
  button.disabled = true;
  accessToken = $("access-password").value;
  $("access-error").textContent = "";
  try {
    await request("/api/conversations");
    $("access-dialog").close();
    $("access-password").value = "";
    notice("");
    await startWorkspace();
  } catch (error) { accessToken = ""; $("access-error").textContent = error.message; }
  finally { button.disabled = false; }
});
async function init() {
  if (configuredBase && !/^https?:\/\//.test(configuredBase)) { notice("서버 주소 설정이 올바르지 않습니다.", "error"); return; }
  $("api-docs").href = `${API}/docs`;
  try {
    const health = await request("/health");
    if (health.access_required) { notice("접속 암호를 입력하면 기온 기록과 대화를 볼 수 있습니다."); openAccess(); return; }
    await startWorkspace();
  } catch (error) { notice(error.message, "error"); }
}
init();
