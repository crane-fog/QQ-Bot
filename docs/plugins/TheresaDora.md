# TheresaDora

## 简介
根据输入内容生成哆啦 A 梦大叫风格图片并发送。

## 基本信息
- 插件名：`TheresaDora`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Dora <内容>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 读取命令后的文本，自动在结尾加感叹号
- 在底图上排版文本并生成图片
- 发送生成后的群图片

## 外部依赖
- 本地底图：`plugins/TheresaDora/base.jpg`
- 本地临时目录：`plugins/TheresaDora/temp/`
- 图片处理依赖：`Pillow`、`Pilmoji`

## 注意事项
- 依赖运行环境中可用的字体路径，否则会退回默认字体
- 代码直接写入 `plugins/TheresaDora/temp/`，部署时需要确保该目录已存在且可写

## 相关代码
- `plugins/TheresaDora/TheresaDora.py`
