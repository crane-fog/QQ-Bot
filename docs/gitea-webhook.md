# Gitea Webhook

## 简介

Gitea Webhook 是 QQ-Bot 中的一个系统级功能，用于监听 Gitea 仓库的 Webhook 事件，将 Push、Issue 创建/变更、评论等事件实时推送到指定 QQ 群。主要服务于高级语言程序设计课程的 Gitea 作业仓库，方便助教和学生及时感知仓库动态。

> **注意：** 这不是一个群聊插件。它不通过 `plugins.toml` / `groups.toml` 控制，而是在 `Bot.py` 启动时根据 `enable_webhook_handler` 配置条件性启动的独立 FastAPI 子服务。

---

## 架构与数据流

整个 Webhook 系统由 5 个核心模块组成，数据流如下：

```text
Gitea 仓库 ── POST /api/tjhlp ──► WebhookHandler (FastAPI)
                                      │
                         读取 X-Gitea-Event-Type 请求头
                                      │
                               parse_gitea_event()
                                      │
                               EventConfig 路由表
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
             forward=False                        forward=True
           (push / assign /                  (issues / issue_comment)
            label / milestone)                      │
                    │                   ┌───────────┴───────────┐
                    ▼                   ▼                       ▼
           GiteaEventFormatter    NotificationService    GiteaEventFormatter
           .plain_text()          发送混合消息 +          .issue_comment_forward()
                    │             下载 Markdown 图片       .issues_forward_plan()
                    ▼                   │                       │
           send_group_msg        send_group_msg         ForwardPlan 组装
                                        │                       │
                                  send_group_forward_msg  send_group_forward_msg
```

### 模块职责

| 模块 | 职责 |
|---|---|
| `WebhookHandler` | FastAPI 应用 + 端点路由。从请求头提取事件类型，调用 `parse_gitea_event()` 校验 payload，再委托 `NotificationService` 发送通知。 |
| `EventConfig` | 事件类型 → Pydantic 模型 + 通知模式的映射表（`EVENT_CONFIG` 字典）。 |
| `NotificationService` | 核心调度层。根据 `config.forward` 分发到纯文本或合并转发路径；负责调用 Gitea API 拉取历史评论、并发下载图片、组装并发送 QQ 消息。 |
| `GiteaEventFormatter` | 消息格式化层。将 Pydantic 事件模型转换为 QQ 可发送的文本或合并转发结构。 |
| `Models` | Pydantic v2 数据模型（`GiteaPushEvent` / `GiteaIssuesEvent` / `GiteaIssueCommentEvent` 及其子结构）。使用 `extra="ignore"` 保证向前兼容。 |

---

## 配置指南

所有配置集中在 `configs/bot.toml`。

### `[Init]` 节 — 总开关

```toml
[Init]
enable_webhook_handler = true
```

| 配置项 | 说明 | 必填 |
|---|---|---|
| `enable_webhook_handler` | 是否在 Bot 启动时创建 Webhook 子服务 | 是 |

> 设为 `true` 后，Bot 启动时会读取 `[Gitea]` 节中的配置并启动 Webhook 监听服务。

### `[Gitea]` 节 — 集成配置

```toml
[Gitea]
webhook_handler_address = "0.0.0.0:8000"
webhook_response_group = 123456789
api_url = "https://gitea.example.com"
api_token = "<your-token>"
dm_notify = false
dm_notify_exclude = []
```

| 配置项 | 说明 | 必填 |
|---|---|---|
| `webhook_handler_address` | 监听地址，格式 `IP:端口` | 是 |
| `webhook_response_group` | 通知发送目标 QQ 群号，同时作为私聊临时会话的来源群 | 是 |
| `api_url` | Gitea 对 Bot 可访问的基础地址；若部署在子路径，必须包含该子路径。尾部 `/` 会自动兼容，建议省略 | 是 |
| `api_token` | Gitea 个人访问令牌 | 是 |
| `dm_notify` | 是否开启 issue 新评论私聊提醒（临时会话），默认 `false` | 否 |
| `dm_notify_exclude` | 补充的不私聊提醒名单（Gitea 用户名/学号）；`assistant_group`（`[Init]` 节，助教群）的群成员会自动排除，无需在此重复 | 否 |
| `dm_notify_fallback_group` | 私聊通知失败时降级提示发送的群，缺省与 `webhook_response_group` 同群 | 否 |

`api_url` 同时用于调用 Gitea API，以及还原 Webhook Markdown 中 `/attachments/<uuid>` 这类根相对资源链接。因此它必须与用户浏览器访问 Gitea 时使用的外部基础地址一致：

```toml
# Gitea 部署在站点根路径
api_url = "https://gitea.example.com"

# Gitea 部署在子路径 /QA
api_url = "http://gitea.example.com/QA"
```

**Token 权限要求：** 至少需要 `read:repository` 和 `read:issue` 权限。Token 用于：
- 拉取 issue 的完整评论列表（构建合并转发消息时）
- 下载 issue 正文和评论中内嵌的图片

> 如果 Token 权限不足或过期，图片将无法显示（会被替换为 `[图片下载失败]` 占位文本），纯文本通知仍可正常工作。
>
> 若启用 [GiteaReply 插件](plugins/GiteaReply.md)，Token 还需要 `write:issue` 权限（用于发表评论）。

---

## 从 QQ 群回复 Issue

见 [GiteaReply 插件文档](plugins/GiteaReply.md)。

---

## Issue 新评论私聊提醒

`dm_notify = true` 时，issue / PR 收到**新评论**（`issue_comment` 且 `action=created`）后，Bot 会通过 QQ 临时会话私聊 issue 作者与被指派人（无需好友，前提是与 Bot 同在 `webhook_response_group`）；评论者本人不提醒。

- **用户映射：** Gitea 用户名即学号，经数据库 `stu_qq_id_map` 表（由 `GetStuId` 插件从群卡片导入）换算 QQ 号。
- **助教排除：** `assistant_group`（`[Init]` 节，助教群）的群成员自动不私聊（成员列表带 10 分钟缓存，不视为通知失败）；`dm_notify_exclude` 可作为补充名单。
- **降级：** 查不到 QQ 映射、未启用数据库或私聊发送失败时，在 `dm_notify_fallback_group`（缺省为 `webhook_response_group`）群内 @（已知 QQ）并列出未绑定学号的用户。
- **触发条件：** 仅 `action=created`；编辑/删除评论不提醒。该功能独立于群通知模式（`forward` 开或关均可）。
- **前置：** `database_enable = true` 且已导入学号映射；LLBot 需允许向非好友发送群临时会话消息。

---

## Gitea 端 Webhook 配置

在 Gitea 仓库中配置 Webhook，使其将事件推送到 Bot：

1. 进入目标仓库页面，点击 **Settings** → **Webhooks** → **Add Webhook**，选择 **Gitea** 类型。
2. 填写以下字段：

   | 字段 | 值 |
   |---|---|
   | Target URL | `http://<Bot 服务器 地址>:<webhook_handler_address 端口>/api/tjhlp` |
   | HTTP Method | POST |
   | POST Content Type | application/json |
   | Secret | 可留空（当前代码未校验 Secret） |

3. **触发事件**：勾选以下三项：
   - **Push** — 代码推送事件
   - **Issues** — Issue 创建/关闭/重开/指派/标签/里程碑等
   - **Issue Comments** — Issue 及 Pull Request 评论

4. 点击 **Add Webhook** 保存。

5. 验证：在 Webhook 列表中找到刚创建的条目，点击 **Test Delivery**，Bot 所在群应收到一条测试通知。

> **网络可达性：** 确保 Gitea 服务器能访问 Bot 的 `webhook_handler_address`。如果 Bot 部署在内网，可能需要配置反向代理或内网穿透。

> 需要确保 Gitea 服务的 allowlist 中配置了 Bot 服务器的地址，否则 Webhook 事件将无法被发送。

---

## 支持的事件类型

以下 6 种事件类型被 `EventConfig.EVENT_CONFIG` 注册并处理：

| 事件类型 | Pydantic 模型 | 通知模式 | 触发场景 |
|---|---|---|---|
| `push` | `GiteaPushEvent` | 纯文本 | 代码推送到仓库 |
| `issues` | `GiteaIssuesEvent` | 纯文本 + 合并转发 | Issue 的 opened / closed / reopened / edited |
| `issue_assign` | `GiteaIssuesEvent` | 纯文本 | Issue 指派人变更 |
| `issue_label` | `GiteaIssuesEvent` | 纯文本 | Issue 标签增减 |
| `issue_milestone` | `GiteaIssuesEvent` | 纯文本 | Issue 里程碑变更 |
| `issue_comment` | `GiteaIssueCommentEvent` | 混合消息 + 合并转发 | Issue / PR 新增评论（含图片和附件） |

**两种通知模式：**

- **纯文本**（`forward=False`）：发送一条普通群消息。
- **合并转发**（`forward=True`）：额外发送一条 QQ 合并转发消息，包含完整上下文（Issue 正文 + 所有历史评论 + 图片 + 附件），按时间线排列。

---

## 通知格式示例

### Push 事件

```
[Gitea] push on branch main (3 commits) in crane-fog/QQ-Bot

- 22795fc: ci: format

https://gitea.example.com/crane-fog/QQ-Bot/compare/abc123...def456
```

### Issue 事件（纯文本）

```
[Gitea] issues on issue #42 opened in crane-fog/QQ-Bot
登录页面样式错乱
alice
-----
描述：
在 Chrome 124 下，登录按钮偏移到页面左侧……
附件: screenshot.png (245.6 KB) https://gitea.example.com/.../screenshot.png

https://gitea.example.com/crane-fog/QQ-Bot/issues/42
```

正文超过 500 字符时自动截断，末尾追加 `...`。正文内容前会插入作者块：首行作者名，第二行按名字的显示宽度画分隔线（CJK 字符按双宽计，最长 30 列）。

### Issue Comment 事件

发送**两条**消息：

1. **混合消息**（文本 + 图片）：当前评论的作者块、正文、内嵌图片、附件链接。
2. **合并转发消息**：完整的时间线视图——
   - 第 1 条：Issue 标题和作者
   - 第 2 条：Issue 正文（节点昵称与内容首行均为 issue 作者）
   - 第 3 ~ N+2 条：每条历史评论（含图片），节点昵称与内容首行均为该评论作者，按时间正序排列
   - 最后一条：Issue URL

图片通过 Gitea API 鉴权下载到本地临时目录，以 `file://` 路径注入合并转发。发送完成后自动清理临时目录。单张图片下载失败不阻塞整体发送，对应位置显示 `[图片下载失败]`。

正文中的图片支持两种写法：markdown 的 `![alt](url)`，以及 Gitea 编辑器粘贴生成的 `<img width="..." alt="..." src="attachments/...">` 标签（`src` 不带前导斜杠时按站点根解析，兼容子路径部署）。

---

## 测试

### 单元测试

```bash
uv run pytest tests/test_gitea_webhook.py -v
uv run pytest tests/test_gitea_notification.py -v
uv run pytest tests/test_gitea_images.py -v
uv run pytest tests/test_gitea_reply.py -v
```

测试文件覆盖：
- `test_gitea_webhook.py`：端到端事件解析与路由（push / issues / issue_comment / issue_assign / issue_label）
- `test_gitea_notification.py`：通知发送逻辑（纯文本 / 合并转发 / 异常处理）
- `test_gitea_images.py`：图片下载与合并转发组装
- `test_gitea_reply.py`：GiteaApi 客户端与 GiteaReply 回帖插件（触发解析 / 回执 / 错误提示）

### 手动模拟

用 curl 直接向 Webhook 端点发送请求：

```bash
curl -X POST http://localhost:8000/api/tjhlp \
  -H "Content-Type: application/json" \
  -H "X-Gitea-Event-Type: push" \
  -d '{
    "ref": "refs/heads/main",
    "before": "0000000000000000000000000000000000000000",
    "after": "abc123def456789012345678901234567890abcd",
    "compare_url": "https://gitea.example.com/user/repo/compare/000...abc",
    "commits": [],
    "total_commits": 0,
    "head_commit": null,
    "repository": {
      "id": 1,
      "name": "repo",
      "full_name": "user/repo",
      "html_url": "https://gitea.example.com/user/repo",
      "owner": { "id": 1, "login": "user", "full_name": "", "avatar_url": "" }
    },
    "pusher": { "id": 1, "login": "user", "full_name": "", "avatar_url": "" },
    "sender": { "id": 1, "login": "user", "full_name": "", "avatar_url": "" }
  }'
```

---

## 排障指南

| 现象 | 可能原因 | 排查方向 |
|---|---|---|
| 启动日志无 Webhook Handler 信息 | `enable_webhook_handler` 为 `false` | 检查 `bot.toml`，设为 `true` |
| 启动后端口不通 | 防火墙 / 云安全组未放行 | `telnet <Bot IP> <端口>` 验证 |
| Gitea Test Delivery 返回 422 | 事件类型不在 `EVENT_CONFIG` 中 | 检查 `X-Gitea-Event-Type` 请求头是否为 6 种支持类型之一 |
| Gitea Test Delivery 返回 200 但群内无消息 | `webhook_response_group` 填写错误或 Bot 未加入该群 | 确认群号正确，Bot 在群内 |
| 通知中图片显示为 `[图片下载失败]` | Token 无权限/过期，或子路径部署时 `api_url` 未包含子路径 | 检查 `[Gitea] api_token` 权限（含 `read:repository`）；再确认 `api_url` 是外部基础地址，例如 `http://host/QA` 而不是 `http://host` |
| 合并转发消息发送失败 | 历史评论数过多导致消息超长 | 当前版本未做截断，暂时减少评论数或关闭 `forward` |
| 日志出现 `发送 Gitea webhook 通知失败` | Gitea API 不可达 / Token 无效 / 网络超时 | 检查 `api_url` 可达性，确认 Token 未过期 |

---

## 注意事项

- **端口冲突：** `webhook_handler_address` 的端口不要与 LLBot 的 HTTP 服务端口或 Bot 的 `server_address` / `client_address` 端口冲突。
- **Token 安全：** `api_token` 存储在 `bot.toml` 明文，未启用 GiteaReply 时建议使用只读权限的 Token；启用后 Token 需要 issue 写权限，务必确保 `bot.toml` 不会被提交到公开仓库，并限定插件生效群（`groups.toml`）以缩小可回帖人群。
- **图片存储：** 图片下载到系统临时目录（`tempfile.mkdtemp`），发送后自动清理。如果 Bot 进程异常退出，残留的 `gitea_img_*` 目录需手动清理。
- **PR 评论支持：** `issue_comment` 事件同时覆盖 Issue 和 Pull Request 的评论（由 `is_pull` 字段区分）。

---
