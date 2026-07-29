# Configset

## 简介
插件状态管理插件，用于按群开启或关闭指定插件，仅限所有者使用。

## 基本信息
- 插件名：`Configset`
- 类型：`Group`
- 作者：`cojitaZ`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`/open <插件名> (<群号，可多个，空格分隔>)`
- 触发命令：`/close <插件名> (<群号，可多个，空格分隔>)`
- 不加群号时默认作用于当前群

## 生效条件
- 需要在 `plugins.toml` 中启用
- 不受 `groups.toml` 群启用控制（`check_group=False`）
- 不要求数据库
- 仅 `owner_id` 可用

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 校验发送者是否为机器人所有者，否则直接忽略
- 解析插件名和目标群号列表
- `/open` 调用 `self.bot.modify_plugin(..., enable=True)` 开启插件
- `/close` 调用 `self.bot.modify_plugin(..., enable=False)` 关闭插件
- 把执行结果以消息形式发回群聊

## 外部依赖
- 无

## 注意事项
- `TheresaHelp` 和 `Configset` 自身不允许通过 `/close` 关闭
- 只传命令不传插件名时会回复「未选择插件」

## 相关代码
- `plugins/Configset/Configset.py`
