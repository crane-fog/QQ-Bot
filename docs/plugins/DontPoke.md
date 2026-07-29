# DontPoke

## 简介
戳一戳回复插件，当群成员戳机器人时自动回复，并有一定概率反戳。

## 基本信息
- 插件名：`DontPoke`
- 类型：`Poke`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 群里对机器人执行戳一戳

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- `cooldown_time`：同一用户再次触发前的冷却秒数
- `repoke_frequency`：反戳概率，按 0-99 随机值比较
- `special_ids`：特殊用户 QQ 列表，戳机器人时回复专属表情
- `ban_time`：代码中保留了注释逻辑，但当前未实际使用

配置示例：

```toml
[DontPoke]
enable = false
repoke_frequency = 50
ban_time = "00:00:00-24:00:00"
cooldown_time = 60
special_ids = [123,456]
```

## 执行逻辑
- 仅在目标为机器人自己时继续处理
- 对同一用户做冷却控制
- 根据用户身份生成不同回复文本
- 按概率执行反戳

## 外部依赖
- 无

## 注意事项
- 虽然模板中有 `ban_time`，当前版本并未真的执行禁言逻辑

## 相关代码
- `plugins/DontPoke/DontPoke.py`
