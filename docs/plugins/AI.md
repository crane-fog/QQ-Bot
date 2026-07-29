# AI

## 简介
群聊问答插件，通过 `configs/ai.toml` 中配置的 AI 服务（`default` profile）回答用户问题，回复风格偏简短直接。

## 基本信息
- 插件名：`AI`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`monika ask <提问内容>`
- 纯命令 `monika ask` 会返回提示信息

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 校验命令格式并做 1 秒冷却限制
- 去掉消息中的 CQ 码后提取问题
- 调用 `self.bot.ai.generate("default", messages)` 向远程模型提问
- 以回复消息的形式把答案发回群聊

## 外部依赖
- `configs/ai.toml`：需要配置 `[profile.default]` 及其引用的 `[provider.*]`（含 `base_url`、`api_key`）
- OpenAI 兼容的远程 LLM 接口

## 注意事项
- 当前实现使用 `self.bot.bot_name` 参与问题截取，命令前缀仍写死为 `monika ask`
- 依赖外部 LLM 接口，未配置 profile 或 provider 时会提示“AI 服务配置有误”，请求失败时提示“AI 服务暂时不可用”

## 相关代码
- `plugins/AI/AI.py`
- `src/AIService.py`
