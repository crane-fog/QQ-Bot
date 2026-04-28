# TheresaMathAI

## 简介
数学问答插件，向远程大模型提问后把结果写成 Markdown 文件并上传到群文件。

## 基本信息
- 插件名：`TheresaMathAI`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`math ask <提问内容>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 对同一用户做 60 秒冷却控制
- 发送“思考中”提示
- 调用远程模型生成数学解答
- 将结果写入本地 Markdown 文件并上传到群文件

## 外部依赖
- 环境变量：`DPSK_KEY`
- 本地临时目录：`plugins/TheresaMathAI/temp/`
- 依赖群文件上传接口

## 注意事项
- 不是直接回文本，而是上传文件
- 仅对 `folder_ids` 字典里列出的群提供固定文件夹 ID
- 代码直接写入 `plugins/TheresaMathAI/temp/`，部署时需要确保该目录已存在且可写

## 相关代码
- `plugins/TheresaMathAI/TheresaMathAI.py`
