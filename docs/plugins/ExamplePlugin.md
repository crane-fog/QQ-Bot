# ExamplePlugin

## 简介
示例插件模板，用于说明插件应如何继承基类、定义入口和读取配置，不是面向生产使用的功能插件。

## 基本信息
- 插件名：`ExamplePlugin`
- 类型：`Group`
- 作者：`somebody`
- 文档由AI生成：`是`

## 触发方式
- 自动触发

## 生效条件
- 需要在 `plugins.ini` 中启用
- 不受 `groups.ini` 群启用控制
- 不要求数据库

## 配置项
- `some_config`：示例配置项
  说明：代码实际读取该配置，但当前 `configs/plugins.ini.template` 未提供这一项

## 执行逻辑
- 演示如何在 `main()` 中读取 `self.config`
- 把插件状态主动设置为 `error`
- 输出调试日志和错误日志

## 外部依赖
- 无

## 注意事项
- 这是示例插件，启用后不会提供正常业务功能
- 代码会主动把自身标记为错误状态

## 相关代码
- `plugins/ExamplePlugin/ExamplePlugin.py`
