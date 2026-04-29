# TheresaGoodMorning

## 简介
AI 版早安/晚安插件，按人设生成回复；晚安分支还会把用户禁言到下一个早上 6 点。

## 基本信息
- 插件名：`TheresaGoodMorning`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- `Theresa 早安`
- `Theresa 晚安`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 对同一用户做 1 秒冷却控制
- 去掉 CQ 码后提取“早安/晚安”问题
- 使用 `persona.j2` 构造提示词并调用 LLM
- `Theresa 晚安` 分支会在回复后把用户禁言到下一个 6:00

## 外部依赖
- 环境变量：`MNAPI_KEY`
- 本地模板：`plugins/TheresaGoodMorning/persona.j2`

## 注意事项
- `Theresa 晚安` 会直接尝试禁言触发者到下一个 6:00
- 机器人需要在目标群具备禁言权限，否则晚安分支会失败并进入报错处理

## 相关代码
- `plugins/TheresaGoodMorning/TheresaGoodMorning.py`
- `plugins/TheresaGoodMorning/persona.j2`
