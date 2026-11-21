"use strict";

// 面板设置页：绑定地址/端口的读取、保存与重载。依赖 common.js 的 $/api/action/notice。

let panelEditable = true;

function panelState(text) {
  $("panel-state").textContent = text;
}

async function loadPanelSettings() {
  const data = await api("/api/panel/settings");
  $("panel-host").value = data.panel_host;
  $("panel-port").value = data.panel_port;
  panelEditable = data.editable;
  $("panel-readonly").hidden = panelEditable;
  $("panel-host").disabled = !panelEditable;
  $("panel-port").disabled = !panelEditable;
  $("panel-save").disabled = !panelEditable;
  panelState(panelEditable ? "已加载" : "只读（容器部署）");
  $("panel-hint").textContent = panelEditable
    ? "保存只写入配置；点击“重载面板”后守护进程会以新绑定重启面板，Bot 保持运行。"
    : "容器内改绑定无意义，请在宿主机调整端口映射。";
}

function validatePanelBind() {
  const host = $("panel-host").value.trim();
  const port = Number($("panel-port").value);
  // 与后端一致的 IP 校验（IPv4/IPv6）。
  const ipv4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
  const match = host.match(ipv4);
  const validV4 = match && match.slice(1).every((part) => Number(part) <= 255);
  const validV6 = host.includes(":") && /^[0-9a-fA-F:]+$/.test(host);
  if (!validV4 && !validV6) {
    throw new Error("绑定地址必须是合法 IP（例如 127.0.0.1 或 0.0.0.0）。");
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("端口必须是 1 到 65535 的整数。");
  }
  return { panel_host: host, panel_port: port };
}

$("panel-page").addEventListener("click", () =>
  action(async () => {
    $("compose-area").hidden = true;
    $("config-area").hidden = true;
    $("panel-area").hidden = false;
    await loadPanelSettings();
  })
);

$("panel-save").addEventListener("click", () =>
  action(async () => {
    const body = validatePanelBind();
    await api("/api/panel/settings", "PUT", body);
    panelState("已保存，待重载");
    notice("面板设置已保存；点击“重载面板”应用新绑定。");
  })
);

$("panel-reload").addEventListener("click", () =>
  action(async () => {
    panelState("重载中…");
    notice("正在重载面板，请稍候…");
    try {
      await api("/api/panel/reload", "POST");
    } catch (error) {
      // 重载会断开当前连接，请求可能失败但守护进程仍在重启面板。
      notice("重载请求已发出，面板正在以新绑定重启…");
    }
    await waitPanelBack();
  })
);

async function waitPanelBack() {
  // 面板重启后轮询会话接口，恢复后提示新地址并刷新。
  const host = $("panel-host").value.trim();
  const port = Number($("panel-port").value);
  const target = `${location.protocol}//${host}:${port}`;
  for (let i = 0; i < 60; i++) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    try {
      const response = await fetch("/api/session", { credentials: "same-origin" });
      if (response.ok || response.status === 401) {
        panelState("已重载");
        notice(`面板已重载。若绑定已变更，请改用新地址访问：${target}`);
        return;
      }
    } catch {
      // 面板尚未恢复，继续等待。
    }
  }
  panelState("重载超时");
  notice("面板重载后未恢复响应，请检查守护进程日志或新绑定是否可达。", true);
}
