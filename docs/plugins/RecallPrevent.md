# RecallPrevent

## 简介
记录群消息并在消息被撤回后重新发出内容，可选附带禁言。

## 基本信息
- 插件名：`RecallPrevent`
- 类型：`GroupRecall`
- 作者：`kiriko`
- 文档由AI生成：`是`

## 触发方式
- 平时自动记录消息
- 群撤回事件触发回放逻辑

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- `host`：Redis 主机
- `port`：Redis 端口
- `db`：Redis 数据库编号
- `for_administer`：是否记录管理员/群主的消息
- `for_everyone`：是否对助教等成员同样执行回放逻辑
- `ban`：是否禁言撤回者
- `ban_time`：禁言时间区间
- `ignored_ids`：忽略的用户 QQ 列表

配置示例：

```toml
[RecallPrevent]
enable = false
ban = true
for_everyone = true
for_administer = false
ignored_ids = [123,456]
ban_time = "00:00:00-00:05:00"
host = "localhost"
port = 6379
db = 0
```

## 执行逻辑
- 普通群消息事件中，把消息内容写入 Redis，TTL 为 180 秒
- 撤回事件中按消息 ID 取回原内容
- 满足条件时把撤回内容重新发回群里
- 可按配置随机时长禁言撤回者

## 外部依赖
- Redis

## 注意事项
- 只有 Redis 里仍保留消息时才能回放
- 实际上需要同时能收到普通消息事件和撤回事件

## 相关代码
- `plugins/RecallPrevent/RecallPrevent.py`
