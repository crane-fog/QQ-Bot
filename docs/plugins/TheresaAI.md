# TheresaAI

## 简介
以 Theresa 人设进行群聊问答的 AI 插件。

## 基本信息
- 插件名：`TheresaAI`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresa ask <提问内容>`

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 对同一用户做 1 秒冷却控制
- 去掉 CQ 码后提取提问内容
- 使用 `prompt.j2` 生成系统提示词
- 通过 `self.bot.ai.generate("Theresa_simple", ...)` 调用远程 LLM 生成回答，并以回复消息形式发回群聊

## 外部依赖
- AI 服务配置：`configs/ai.toml` 中的 `[profile.Theresa_simple]` 及其引用的 `[provider.*]` 服务商（由 `src/AIService.py` 读取）
- 本地模板：`plugins/TheresaAI/prompt.j2`

## 注意事项
- 依赖外部 LLM 接口
- 模板中会读取 `owner_id`、时间和群名

## 相关代码
- `plugins/TheresaAI/TheresaAI.py`
- `plugins/TheresaAI/prompt.j2`
- `src/AIService.py`
