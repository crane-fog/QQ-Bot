# TheresaWithdraw

## 简介
用于撤回指定回复消息的插件，主要用于配合“防撤回”场景做二次撤回。

## 基本信息
- 插件名：`TheresaWithdraw`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 回复某条消息并发送 `Twithdraw`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 仅 bot 主人、群管理员/群主、助教可用

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 只在消息中同时包含回复 CQ 码和 `Twithdraw` 时继续
- 校验调用者权限
- 删除被回复的目标消息
- 再删除本次触发命令消息

## 外部依赖
- 无

## 注意事项
- 当前实现最后仍会发送一条空字符串消息

## 相关代码
- `plugins/TheresaWithdraw/TheresaWithdraw.py`
