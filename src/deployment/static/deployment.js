"use strict";
const $ = (id) => document.getElementById(id);
let csrf = "", version = "", baseline = "", services = {}, selected = "";
let formOriginal = {}, view = "form", pending = false;
const labels = {image: "镜像", restart: "重启策略", environment: "环境变量", ports: "端口映射", volumes: "挂载", depends_on: "依赖关系", healthcheck: "健康检查", profiles: "Profiles"};
const structured = new Set(["environment", "ports", "volumes", "depends_on", "healthcheck", "profiles"]);
function notice(text, error = false) { $("notice").textContent = text; $("notice").classList.toggle("error", error); }
async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login") showLogin();
    throw new Error(data.error?.message || "请求失败，请检查输入或连接。");
  }
  return data;
}
function formDirty() { return Object.keys(labels).some((key) => $("field-" + key) && $("field-" + key).value !== formOriginal[key]); }
function dirty() { return $("source").value !== baseline || formDirty(); }
function updateState() {
  $("save-state").textContent = dirty() ? "草稿未保存" : "已保存";
  ["save", "reload"].forEach((id) => { $(id).disabled = pending; });
}
async function action(fn) {
  if (pending) return;
  pending = true; updateState();
  try { await fn(); } catch (error) { notice(error.message, true); }
  finally { pending = false; updateState(); }
}
function showLogin() {
  csrf = "";
  $("login-panel").hidden = false; $("workspace").hidden = true; $("logout").hidden = true;
  $("password").focus();
}
function renderServices() {
  $("service-list").replaceChildren();
  for (const name of Object.keys(services)) {
    const button = document.createElement("button"); button.textContent = name;
    button.setAttribute("aria-pressed", String(name === selected));
    button.addEventListener("click", () => action(async () => { await syncForm(); selected = name; renderServices(); renderForm(); }));
    $("service-list").append(button);
  }
}
function renderForm() {
  $("fields").replaceChildren(); $("fields").className = "field-grid"; formOriginal = {};
  $("service-title").textContent = selected;
  for (const [key, label] of Object.entries(labels)) {
    const wrapper = document.createElement("div"); wrapper.className = structured.has(key) ? "field wide" : "field";
    const name = document.createElement("label"); name.htmlFor = "field-" + key; name.textContent = label + (structured.has(key) ? "（JSON）" : "");
    const input = document.createElement(structured.has(key) ? "textarea" : "input");
    input.id = "field-" + key;
    const value = services[selected]?.[key];
    input.value = value == null ? "" : structured.has(key) ? JSON.stringify(value, null, 2) : String(value);
    formOriginal[key] = input.value;
    input.addEventListener("input", updateState); wrapper.append(name, input); $("fields").append(wrapper);
  }
}
async function syncForm() {
  if (view !== "form" || !formDirty()) return;
  const changes = {};
  for (const key of Object.keys(labels)) {
    const value = $("field-" + key).value;
    if (value === formOriginal[key]) continue;
    if (!value.trim()) changes[key] = null;
    else if (structured.has(key)) {
      try { changes[key] = JSON.parse(value); } catch { throw new Error(labels[key] + "的 JSON 格式有误，草稿已保留。"); }
    } else changes[key] = value;
  }
  const data = await api("/api/compose/patch", "POST", {source: $("source").value, service: selected, changes});
  $("source").value = data.source; services = data.services; renderForm(); updateState();
}
async function switchView(next) {
  await syncForm();
  if (next === "form") {
    const data = await api("/api/compose/parse", "POST", {source: $("source").value, version});
    services = data.services; if (!services[selected]) selected = Object.keys(services)[0];
    renderServices(); renderForm();
  }
  view = next; $("form-view").hidden = next !== "form"; $("yaml-view").hidden = next !== "yaml";
  $("form-tab").setAttribute("aria-pressed", String(next === "form")); $("yaml-tab").setAttribute("aria-pressed", String(next === "yaml"));
}
function setDocument(data) {
  version = data.version; baseline = data.source; services = data.services;
  $("source").value = data.source;
  if (!services[selected]) selected = Object.keys(services)[0];
  renderServices(); renderForm();
  updateState();
}
async function load() {
  const capabilities = await api("/api/capabilities");
  await initializeConfigs(capabilities);
  if (!capabilities.compose) return;
  setDocument(await api("/api/compose"));
  await refreshBackups();
}
function confirmAction(title, message, diff, callback) {
  $("confirm-title").textContent = title; $("confirm-message").textContent = message;
  $("confirm-diff").textContent = diff || "没有配置差异。";
  $("confirm-action").onclick = () => { $("confirm-dialog").close(); action(callback); };
  $("confirm-dialog").showModal();
}
async function refreshBackups() {
  const data = await api("/api/backups"); $("backups").replaceChildren();
  if (!data.backups.length) $("backups").textContent = "首次保存变更后会自动生成备份。";
  for (const backup of data.backups.slice(0, 20)) {
    const row = document.createElement("div"); row.className = "backup-row";
    const label = document.createElement("span"); label.textContent = backup.id;
    const button = document.createElement("button"); button.textContent = "预览恢复";
    button.addEventListener("click", () => action(async () => {
      if (dirty()) throw new Error("请先保存或下载草稿，再恢复备份。");
      const preview = await api("/api/backups/" + backup.id);
      confirmAction("恢复配置备份", "仅恢复配置文件。当前配置也会备份，容器更新需在宿主机执行。", preview.diff, async () => {
        setDocument(await api("/api/backups/" + backup.id + "/restore", "POST", {version}));
        await refreshBackups(); notice("备份已恢复。");
      });
    })); row.append(label, button); $("backups").append(row);
  }
}
$("login-form").addEventListener("submit", (event) => { event.preventDefault(); action(async () => {
  const data = await api("/api/login", "POST", {password: $("password").value}); csrf = data.csrf; $("password").value = "";
  $("login-panel").hidden = true; $("workspace").hidden = false; $("logout").hidden = false;
  notice(""); await load();
}); });
$("logout").addEventListener("click", () => action(async () => { await api("/api/logout", "POST"); showLogin(); notice("已退出登录。"); }));
$("service-form").addEventListener("submit", (event) => { event.preventDefault(); action(async () => { await syncForm(); notice("草稿已更新，尚未保存。"); }); });
$("source").addEventListener("input", updateState);
$("form-tab").addEventListener("click", () => action(() => switchView("form")));
$("yaml-tab").addEventListener("click", () => action(() => switchView("yaml")));
$("save").addEventListener("click", () => action(async () => {
  setDocument(await api("/api/compose", "PUT", {source: $("source").value, version}));
  await refreshBackups(); notice("配置已保存。容器更新需在宿主机执行 docker compose up -d。");
}));
$("diff-panel").addEventListener("toggle", () => action(async () => {
  if (!$("diff-panel").open) return;
  const data = await api("/api/compose/validate", "POST", {source: $("source").value, version});
  $("diff").textContent = data.diff || "没有配置差异。";
}));
$("reload").addEventListener("click", () => action(async () => {
  if (dirty()) confirmAction("重新读取配置", "当前草稿将被替换，可先下载草稿。", "", load);
  else await load();
}));
$("download").addEventListener("click", () => action(async () => {
  await syncForm(); const url = URL.createObjectURL(new Blob([$("source").value], {type: "text/yaml;charset=utf-8"}));
  const link = document.createElement("a"); link.href = url; link.download = "compose.yaml"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}));
$("refresh-backups").addEventListener("click", () => action(refreshBackups));
$("confirm-cancel").addEventListener("click", () => $("confirm-dialog").close());
window.addEventListener("beforeunload", (event) => { if ((dirty() || configDirty()) && csrf) { event.preventDefault(); event.returnValue = ""; } });
(async () => {
  try { const session = await api("/api/session"); csrf = session.csrf; $("login-panel").hidden = true; $("workspace").hidden = false; $("logout").hidden = false; await load(); }
  catch (error) { showLogin(); if (error.message !== "请先登录") notice(error.message, true); }
})();
