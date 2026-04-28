# MoeGoe

## 简介
语音合成插件，调用外部 TTS 服务生成角色语音并发送到群里。

## 基本信息
- 插件名：`MoeGoe`
- 类型：`Group`
- 作者：`just monika & Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`moegoe ema/sheri zh/ja <文本>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- `url`：语音合成服务地址

## 执行逻辑
- 校验角色、语言和文本长度
- 调用配置的 HTTP 接口生成语音文件
- 把返回内容保存为本地 `.wav`
- 以群语音消息发送

## 外部依赖
- 外部 HTTP TTS 服务
- 本地临时目录：`plugins/MoeGoe/temp/`

## 注意事项
- 文本长度限制为 200 字
- 依赖外部服务返回可直接保存的音频二进制
- 代码直接写入 `plugins/MoeGoe/temp/`，部署时需要确保该目录已存在且可写

## 相关代码
- `plugins/MoeGoe/MoeGoe.py`
