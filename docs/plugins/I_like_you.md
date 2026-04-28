# I_like_you

## 简介
根据固定台词发送本地语音的轻量娱乐插件。

## 基本信息
- 插件名：`I_like_you`
- 类型：`Group`
- 作者：`cojitaZ`
- 文档由AI生成：`是`

## 触发方式
- 发送 `我喜欢你`
- 发送 `我不喜欢你`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 检测消息中是否包含固定台词
- 选择对应的本地音频文件并发送为群语音

## 外部依赖
- 本地音频文件：
  - `plugins/I_like_you/我喜欢你_你喜欢我.wav`
  - `plugins/I_like_you/我不喜欢你.wav`

## 注意事项
- 如果监听端不支持本地语音发送，这个插件无法正常工作

## 相关代码
- `plugins/I_like_you/I_like_you.py`
