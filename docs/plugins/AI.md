# AI

## 简介
群聊问答插件，使用 Gemini 模型回答用户问题，回复风格偏简短直接。

## 基本信息
- 插件名：`AI`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`monika ask <提问内容>`
- 纯命令 `monika ask` 会返回提示信息

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 校验命令格式并做 1 秒冷却限制
- 去掉消息中的 CQ 码后提取问题
- 调用 `get_llm_response(...)` 向远程模型提问
- 以回复消息的形式把答案发回群聊

## 外部依赖
- 环境变量：`MNAPI_KEY`
- 远程接口：`https://api.mnapi.com/v1`

## 注意事项
- 当前实现使用 `self.bot.bot_name` 参与问题截取，命令前缀仍写死为 `monika ask`
- 依赖外部 LLM 接口，未配置密钥时会在运行时报错

## 相关代码
- `plugins/AI/AI.py`
- `utils/AITools.py`
