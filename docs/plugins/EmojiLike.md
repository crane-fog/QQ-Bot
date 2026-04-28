# EmojiLike

## 简介
自动给群消息添加随机表情回应的插件。

## 基本信息
- 插件名：`EmojiLike`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 自动触发

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- `ignored_ids`：忽略的用户 QQ 列表
- `frequency`：触发表情回应的概率阈值

## 执行逻辑
- 跳过 `ignored_ids` 中的用户
- 按概率随机选择一个表情 ID
- 调用 `set_msg_emoji_like` 给当前消息贴表情

## 外部依赖
- 无

## 注意事项
- 依赖 OneBot 侧支持 `set_msg_emoji_like`

## 相关代码
- `plugins/EmojiLike/EmojiLike.py`
