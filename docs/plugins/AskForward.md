# AskForward

## 简介
用于把提问群的消息转发到答疑群，并把答疑群中的回复转回原群，适合多群统一答疑场景。

## 基本信息
- 插件名：`AskForward`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- `#Q#` 开头的消息会被识别为提问
- 在答疑群中回复 bot 转发的消息会被识别为回答
- 提问群中的普通后续消息可能会被识别为追问
- 在答疑群中发送 `Broadcast <discussion_id>` 会把该讨论广播到目标群

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- `assistant_list` 和 `special_assistant_list` 中的成员不会进入“追问”转发分支

## 配置项
- `broadcast_target_group`：广播目标群
- `answer_group`：答疑群
- `ask_groups`：提问群列表
- `special_assistant_list`：额外视为助教的 QQ 列表

## 执行逻辑
- 为提问建立讨论 ID，并把用户近期相关消息一并转发到答疑群
- 在答疑群通过回复消息定位原讨论，再把回答发回来源群
- 对非助教用户的后续消息按时间窗口识别为追问，并继续转发
- 支持基于讨论 ID 的消息广播

## 外部依赖
- PostgreSQL

## 注意事项
- 强依赖数据库记录消息与讨论关系
- `ask_groups`、`answer_group`、`broadcast_target_group` 必须与实际群号一致
- `special_assistant_list` 为空字符串时会被直接按逗号切分并转整数，配置格式需要特别小心

## 相关代码
- `plugins/AskForward/AskForward.py`
