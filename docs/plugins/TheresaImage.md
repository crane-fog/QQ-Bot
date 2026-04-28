# TheresaImage

## 简介
对回复中的图片执行 AI 识图或图像问答的插件。

## 基本信息
- 插件名：`TheresaImage`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 消息需以回复 CQ 码开头
- 回复内容中需要紧跟 `Timage`
- `Timage` 后可以追加可选的文本提示词

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 从回复消息中提取被回复的消息 ID
- 调用 OneBot API 获取原消息和图片文件路径
- 使用文本提示和图片内容一起向 LLM 发起请求
- 以回复形式把识图结果发回群聊

## 外部依赖
- 环境变量：`MNAPI_KEY`
- 需要 OneBot 侧支持 `get_msg` 与 `get_image`

## 注意事项
- 标记为 `require_db=True`，即使代码主体不直接查库，也要求数据库已开启
- 被回复的原消息里需要能解析出图片 CQ 码，否则不会继续识图

## 相关代码
- `plugins/TheresaImage/TheresaImage.py`
