# Theresac

## 简介
执行系统命令的高风险插件，命令会直接在运行 bot 的机器上执行。

## 基本信息
- 插件名：`Theresac`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresac <命令>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 不受 `groups.ini` 群启用控制
- 不要求数据库
- 仅 `owner_id` 可用

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 截取命令字符串
- 使用 `create_subprocess_shell(...)` 在系统 shell 中执行
- 收集 `stdout` 和 `stderr`
- 把执行结果发回群里

## 外部依赖
- 运行 bot 的操作系统 shell 环境

## 注意事项
- 高风险插件，具有直接执行系统命令的能力
- 建议仅在受控环境中临时启用

## 相关代码
- `plugins/Theresac/Theresac.py`
