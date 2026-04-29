# MessageRecorder

## 简介
记录群消息到数据库的基础插件，主要为 `TheresaChat`、`AskForward` 等依赖上下文的插件提供数据。

## 基本信息
- 插件名：`MessageRecorder`
- 类型：`Record`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 自动触发

## 生效条件
- 需要在 `plugins.ini` 中启用
- 不受 `groups.ini` 群启用控制
- 要求 `database_enable = True`

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 处理群消息事件和发送事件
- 如果消息中包含图片 CQ 码，会调用 OneBot API 解析出图片本地路径
- 将消息、用户、群号、消息 ID 等信息写入数据库

## 外部依赖
- PostgreSQL
- 需要 OneBot 侧支持 `get_image`

## 注意事项
- `check_group=False`，只要插件被加载就会记录所有群消息

## 相关代码
- `plugins/MessageRecorder/MessageRecorder.py`
