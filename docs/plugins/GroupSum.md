# GroupSum

## 简介

总结群聊消息插件。该插件可以从数据库中提取最近的消息记录，并利用大语言模型（LLM）进行摘要总结，提取核心话题和参与者。

## 基本信息

- 插件名：`GroupSum`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式

- 命令触发：`Summary <消息条数>`
    - 例如：`Summary 50` 表示总结最近的 50 条消息。
    - 受 `max_length` 配置限制，请求条数若超过限制则取限制值。

## 生效条件

- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- **需要数据库支持**（依赖 `MessageRecorder` 插件记录的消息）

## 配置项

在 `plugins.ini` 中的 `[GroupSum]` 段落配置：

- `enable`: 是否启用插件。
- `max_length`: 单次总结最大支持的消息条数（建议 1000 以内）。

## 执行逻辑

1. 提取用户输入的总结条数。
2. 从数据库 `messages` 表中获取该群最近的历史消息。
3. 处理消息中的回复（Reply）和图片（Image，虽然目前 `resolve_imgs` 默认设为 `False`）。
4. 使用系统人设（`persona.j2`）和提取的消息内容构造上下文。
5. 调用 LLM（模型：`deepseek-v4-pro`）生成 JSON 格式的回应。
6. 构建合并转发消息（Forward），包含总体描述和每个主题的详细列表（参与者、详情等）并发送。

## 外部依赖

- 需要 `MessageRecorder` 插件正常工作以提供历史消息。
- 依赖 `utils/AITools.py` 中的 `get_llm_response`。
- 本地模板：`plugins/GroupSum/persona.j2`

## 注意事项

- 仅支持对已存入数据库的消息进行总结。
- 输出结果通过合并转发消息展示，避免刷屏。

## 相关代码

- `plugins/GroupSum/GroupSum.py`
- `plugins/GroupSum/persona.j2`
