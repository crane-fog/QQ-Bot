# TheresaChat

## 简介
基于数据库消息上下文的自动聊天插件，必要时还会选择表情图片发送。

## 基本信息
- 插件名：`TheresaChat`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 自动触发
- `owner_id` 还可发送 `chat stop <秒数>` 暂停当前群回复

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 要求 `bot.toml` 中 `database_enable = true`
- `chat stop` 仅 bot 主人可用

## 配置项
- `context_length`：普通回复读取的上下文消息条数
- `extra_context`：上下文优化时额外多读的消息条数
- `context_length_for_face`：表情图片选择时读取的上下文消息条数

配置示例：

```toml
[TheresaChat]
enable = false
context_length = 200
extra_context = 100
context_length_for_face = 20
```

## 执行逻辑
- 从数据库读取消息上下文
- 根据消息内容与随机概率决定是否回复
- 普通回复走文本模型；少量情况下走表情图片选择逻辑
- 对图片消息与引用消息做额外解析

## 外部依赖
- PostgreSQL
- `configs/ai.toml`：`[profile.chat]`（普通回复）、`[profile.chat_face]`（表情选择）及其引用的 `[provider.*]`
- 本地模板：`prompt.j2`、`persona_face.j2`
- 本地素材目录：`plugins/TheresaChat/faces/`

## 注意事项
- 依赖 `MessageRecorder` 先把消息写入数据库，否则上下文不足
- 这是自动回复插件，首次启用时要注意刷屏风险

## 相关代码
- `plugins/TheresaChat/TheresaChat.py`
- `plugins/TheresaChat/prompt.j2`
- `plugins/TheresaChat/persona_face.j2`
- `src/AIService.py`
