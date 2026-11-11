"use strict";
let configName = "bot.toml", configVersion = "", configBaseline = "", configValues = {}, configView = "form";
let configInputs = [], configInitialized = false, configMode = "";
const botLabels = {server_address: "LLBot API 地址", client_address: "Bot 事件监听地址", bot_name: "Bot 名称", debug: "调试模式", database_enable: "启用数据库", database_username: "数据库用户名", database_address: "数据库地址", database_passwd: "数据库密码", database_name: "数据库名称", owner_id: "所有者 QQ 号", assistant_group: "助教群号", enable_webhook_handler: "启用 Gitea Webhook", webhook_handler_address: "Webhook 监听地址", webhook_response_group: "Webhook 回复群号", api_url: "Gitea API 地址", api_token: "Gitea API 令牌"};
function configDirty() {
  return configInitialized && ($("config-source").value !== configBaseline || configInputs.some(({input, original}) => (input.type === "checkbox" ? input.checked : input.value) !== original));
}
function configState() { $("config-state").textContent = configDirty() ? "草稿未保存" : "已保存"; }
function configPath(suffix = "") { return "/api/configs/" + encodeURIComponent(configName) + suffix; }
function configBody() { return {source: $("config-source").value, version: configVersion}; }
function configField(path, value, label, secret = false) {
  const wrapper = document.createElement("div"); wrapper.className = "field";
  const name = document.createElement("label"), input = document.createElement("input");
  input.id = "config-field-" + configInputs.length; name.htmlFor = input.id; name.textContent = label;
  input.type = typeof value === "boolean" ? "checkbox" : secret ? "password" : typeof value === "number" ? "number" : "text";
  if (input.type === "checkbox") input.checked = value; else input.value = String(value);
  input.autocomplete = "off";
  input.addEventListener("input", configState);
  configInputs.push({path, input, original: input.type === "checkbox" ? input.checked : input.value, type: typeof value});
  wrapper.append(name, input);
  if (secret) {
    const toggle = document.createElement("button"); toggle.type = "button"; toggle.textContent = "显示";
    toggle.addEventListener("click", () => { input.type = input.type === "password" ? "text" : "password"; toggle.textContent = input.type === "password" ? "显示" : "隐藏"; });
    wrapper.append(toggle);
  }
  $("config-form").append(wrapper);
}
function renderConfigForm() {
  $("config-form").replaceChildren(); configInputs = [];
  if (configName === "bot.toml") {
    for (const section of ["Init", "Gitea"]) for (const [key, value] of Object.entries(configValues[section] || {})) {
      if (botLabels[key]) configField([section, key], value, botLabels[key], /passwd|token/.test(key));
    }
  } else if (configName === "plugins.toml") {
    for (const [name, table] of Object.entries(configValues)) configField([name, "enable"], table.enable ?? false, name);
  } else if (configName === "groups.toml") {
    for (const [group, table] of Object.entries(configValues)) {
      const heading = document.createElement("div"); heading.className = "wide heading";
      const title = document.createElement("h2"); title.textContent = "群 " + group;
      const remove = document.createElement("button"); remove.textContent = "删除群配置";
      remove.addEventListener("click", () => action(async () => {
        await syncConfigForm();
        confirmAction("删除群配置", "将从草稿中删除群 " + group + " 的配置，保存后才写入文件。", "", () => patchConfig([{path: [group], delete: true}]));
      }));
      heading.append(title, remove); $("config-form").append(heading);
      for (const [plugin, enabled] of Object.entries(table)) configField([group, plugin], enabled, plugin);
    }
    const controls = document.createElement("div"); controls.className = "field wide";
    const groupLabel = document.createElement("label"); groupLabel.htmlFor = "config-new-group"; groupLabel.textContent = "群号";
    const groupInput = document.createElement("input"); groupInput.id = "config-new-group"; groupInput.inputMode = "numeric";
    const pluginLabel = document.createElement("label"); pluginLabel.htmlFor = "config-new-plugin"; pluginLabel.textContent = "插件名（可留空创建群配置）";
    const pluginInput = document.createElement("input"); pluginInput.id = "config-new-plugin";
    const add = document.createElement("button"); add.textContent = "添加群 / 插件";
    add.addEventListener("click", () => action(async () => {
      const group = groupInput.value.trim(), plugin = pluginInput.value.trim();
      if (!/^\d+$/.test(group)) throw new Error("请输入数字群号。");
      await syncConfigForm();
      if (plugin) await patchConfig([{path: [group, plugin], value: true}]);
      else if (!configValues[group]) await patchConfig([{path: [group], value: {}}]);
    }));
    controls.append(groupLabel, groupInput, pluginLabel, pluginInput, add); $("config-form").append(controls);
  }
}
async function patchConfig(changes) {
  const data = await api(configPath("/patch"), "POST", {source: $("config-source").value, changes});
  $("config-source").value = data.source; configValues = data.values; renderConfigForm(); configState();
}
async function syncConfigForm() {
  if (configView !== "form") return;
  const changes = [];
  for (const {path, input, original, type} of configInputs) {
    let value = type === "boolean" ? input.checked : input.value;
    if (value === original) continue;
    if (type === "number") {
      if (!/^-?\d+$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error("请输入有效整数，草稿已保留。");
      value = Number(value);
    }
    changes.push({path, value});
  }
  if (changes.length) await patchConfig(changes);
}
function setConfigView(next) {
  configView = next; $("config-form").hidden = next !== "form"; $("config-text").hidden = next !== "text";
  $("config-form-tab").setAttribute("aria-pressed", String(next === "form")); $("config-text-tab").setAttribute("aria-pressed", String(next === "text"));
}
async function switchConfigView(next) {
  await syncConfigForm();
  if (next === "form") {
    const data = await api(configPath("/validate"), "POST", configBody());
    configValues = data.values; renderConfigForm();
  }
  setConfigView(next);
}
async function readConfig() {
  const data = await api(configPath());
  configVersion = data.version; configBaseline = data.source; configValues = data.values || {};
  $("config-source").value = data.source; $("config-file").value = configName;
  configInitialized = true;
  const hasForm = ["bot.toml", "plugins.toml", "groups.toml"].includes(configName);
  $("config-form-tab").hidden = !hasForm;
  renderConfigForm(); setConfigView(hasForm && !data.error ? "form" : "text");
  configState(); $("config-diff").textContent = "";
  notice(data.error || (!data.exists ? "文件尚不存在，可以填写 TOML 后保存创建。" : ""), Boolean(data.error));
  await configBackups();
}
async function configBackups() {
  const data = await api(configPath("/backups")); $("config-backups").replaceChildren();
  if (!data.backups.length) $("config-backups").textContent = "此文件暂无备份。";
  for (const backup of data.backups.slice(0, 20)) {
    const row = document.createElement("div"); row.className = "backup-row";
    const label = document.createElement("span"); label.textContent = backup.id;
    const button = document.createElement("button"); button.textContent = "预览恢复配置";
    button.addEventListener("click", () => action(async () => {
      if (configDirty()) throw new Error("请先保存或下载配置草稿，再恢复备份。");
      const endpoint = configPath("/backups/" + backup.id), revision = configVersion;
      const preview = await api(endpoint);
      confirmAction("恢复配置文件", "恢复前会备份当前文件；恢复后点击“重启 Bot”应用。", preview.diff, async () => {
        await api(endpoint + "/restore", "POST", {version: revision}); await readConfig(); notice("备份已恢复到磁盘；点击“重启 Bot”应用新配置。");
      });
    })); row.append(label, button); $("config-backups").append(row);
  }
}
async function initializeConfigs(capabilities) {
  $("compose-page").hidden = !capabilities.compose;
  $("config-restart-bot").hidden = !capabilities.bot_restart;
  if (configMode !== capabilities.mode || !configInitialized) {
    configMode = capabilities.mode;
    $("config-file").replaceChildren(...capabilities.configs.map((name) => { const option = document.createElement("option"); option.value = name; option.textContent = name; return option; }));
    $("compose-area").hidden = !capabilities.compose; $("config-area").hidden = capabilities.compose;
    await readConfig();
  }
}
$("config-file").addEventListener("change", () => {
  const next = $("config-file").value; $("config-file").value = configName;
  action(async () => {
    const change = async () => { configName = next; await readConfig(); };
    if (configDirty()) confirmAction("切换配置文件", "未保存的配置草稿会被丢弃，可以取消后先下载。", "", change); else await change();
  });
});
$("configs-page").addEventListener("click", () => action(async () => {
  await syncForm(); $("compose-area").hidden = true; $("config-area").hidden = false;
}));
$("compose-page").addEventListener("click", () => action(async () => {
  await syncConfigForm(); $("compose-area").hidden = false; $("config-area").hidden = true;
}));
$("config-source").addEventListener("input", configState);
$("config-form-tab").addEventListener("click", () => action(() => switchConfigView("form")));
$("config-text-tab").addEventListener("click", () => action(() => switchConfigView("text")));
$("config-save").addEventListener("click", () => action(async () => {
  await api(configPath(), "PUT", configBody()); await readConfig(); notice("配置已保存；点击“重启 Bot”应用新配置。");
}));
$("config-diff-panel").addEventListener("toggle", () => action(async () => {
  if (!$("config-diff-panel").open) return;
  const data = await api(configPath("/validate"), "POST", configBody());
  $("config-diff").textContent = data.diff || "没有配置差异。";
}));
$("config-reload").addEventListener("click", () => action(async () => {
  if (configDirty()) confirmAction("重新读取配置", "未保存的配置草稿会被替换，可先下载。", "", readConfig); else await readConfig();
}));
$("config-restart-bot").addEventListener("click", () => action(async () => {
  const data = await api("/api/bot/restart", "POST");
  notice(data.restarted ? "Bot 重启中，稍后将加载最新配置。" : "Bot 未在运行。");
}));
$("config-download").addEventListener("click", () => action(async () => {
  await syncConfigForm(); const url = URL.createObjectURL(new Blob([$("config-source").value], {type: "text/plain;charset=utf-8"}));
  const link = document.createElement("a"); link.href = url; link.download = configName; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}));
$("config-refresh-backups").addEventListener("click", () => action(configBackups));
