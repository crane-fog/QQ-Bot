"use strict";

// 共享工具：deployment.js 与 configs.js 复用，需在两者之前加载。

const $ = (id) => document.getElementById(id);

function notice(text, error = false) {
  $("notice").textContent = text;
  $("notice").classList.toggle("error", error);
}

async function api(path, method = "GET", body) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login") showLogin();
    throw new Error(data.error?.message || "请求失败，请检查输入或连接。");
  }
  return data;
}

let pending = false;

async function action(fn) {
  if (pending) return;
  pending = true;
  updateState();
  try {
    await fn();
  } catch (error) {
    notice(error.message, true);
  } finally {
    pending = false;
    updateState();
  }
}

function confirmAction(title, message, diff, callback) {
  $("confirm-title").textContent = title;
  $("confirm-message").textContent = message;
  $("confirm-diff").textContent = diff || "没有配置差异。";
  $("confirm-action").onclick = () => {
    $("confirm-dialog").close();
    action(callback);
  };
  $("confirm-dialog").showModal();
}

function downloadText(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// 两处备份列表共用的渲染骨架：最多展示 20 条，预览后弹确认框再执行恢复。
function renderBackupRows(container, backups, emptyText, options) {
  container.replaceChildren();
  if (!backups.length) {
    container.textContent = emptyText;
    return;
  }
  for (const backup of backups.slice(0, 20)) {
    const row = document.createElement("div");
    row.className = "backup-row";
    const label = document.createElement("span");
    label.textContent = backup.id;
    const button = document.createElement("button");
    button.textContent = options.buttonText;
    button.addEventListener("click", () =>
      action(async () => {
        if (options.isDirty()) throw new Error(options.dirtyMessage);
        const preview = await api(options.previewUrl(backup.id));
        confirmAction(options.confirmTitle, options.confirmMessage, preview.diff, async () => {
          await options.restore(backup.id);
          await options.refresh();
          notice(options.restoredMessage);
        });
      })
    );
    row.append(label, button);
    container.append(row);
  }
}
