# GiteaReply

## 简介
把 QQ 群消息回复到 Gitea issue：在白名单群发送 `#<issue编号> <内容>`，Bot 将其作为评论发表到 Gitea 对应 issue，并在群内回执评论链接。

## 基本信息
- 插件名：`GiteaReply`
- 类型：`Group`
- 作者：`oierxjn`
- 文档由AI生成：`是`

## 触发方式
- 群消息以 `#<issue编号>` 开头（消息首尾空白会被忽略），编号与内容之间的空格可有可无：`#7 内容` 或 `#7内容`
- 纯编号（如 `#7`）不触发；`#` 后不是数字不触发
- 注意 `#0731话题闲聊` 这类「#数字」开头的消息会被视为回复 issue #731

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制（即群白名单）
- 不要求数据库
- `bot.toml` 的 `[Gitea] api_token` 需要 `write:issue` 权限（未启用本插件时 token 只读即可）

## 配置项

`bot.toml`（`[Gitea]` 节，与 webhook 通知共享）：

```toml
[Gitea]
api_url = "https://gitea.example.com"
api_token = "<token，启用回帖需 write:issue 权限>"
```

`plugins.toml`：

```toml
[GiteaReply]
enable = false
# 回复的目标仓库（owner/repo，单仓库）
reply_repo = "owner/repo"
```

## 执行逻辑
- 回帖前先 GET 校验 issue 存在，编号无效时群内提示
- 把消息按 CQ 码拆分为文本/媒体段：图片、文件、视频作为 Gitea 评论附件上传，正文按出现顺序回填 `/attachments/...` 链接（图片内嵌渲染）；@人转 `@QQ号`、表情转 `[表情]`，其余 CQ 码不转发
- 评论正文带发送者群名片/昵称：`**来自 QQ 群反馈**（张三）：...`
- 附件上传后 PATCH 评论正文回填链接；单个媒体下载/上传失败只在对应位置标注占位文本并在回执中计数，不影响评论主体
- 成功后回执含 Gitea 评论链接

## 注意事项
- 评论正文按 Markdown 原样提交，未做转义
- 图片链接由 OneBot 实现（QQ CDN）提供，Bot 直接下载后上传，无需 Gitea 之外的凭据；下载仅允许腾讯 CDN 域名（`qpic.cn` / `qq.com` / `qq.com.cn` 后缀），其余 URL 一律拒绝
- 附件在评论中以绝对地址链接回填（`browser_download_url`），Gitea 部署在子路径时同样有效
- 引用回复（`[CQ:reply]`）暂不支持，带引用的消息以 CQ 码开头，不会触发插件
- 使用写权限 token，务必确保 `bot.toml` 不会被提交到公开仓库

## 相关代码
- `plugins/GiteaReply/GiteaReply.py`
- `src/gitea/GiteaApi.py`（Gitea REST 客户端）
- `tests/test_gitea_reply.py`
