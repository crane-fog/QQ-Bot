# A_music

## 简介
网易云听歌插件，支持按歌曲 ID 下载发送，也支持按关键词搜索歌曲。

## 基本信息
- 插件名：`A_music`
- 类型：`Group`
- 作者：`cojitaZ`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`/music ...`
- `/music <数字>`：按歌曲 ID 下载并发送
- `/music <关键词>`：返回搜索结果

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 解析 `/music` 后的参数
- 纯数字参数走下载分支，下载音乐后发送群语音
- 非数字参数走搜索分支，返回前 5 个搜索结果

## 外部依赖
- 网易云相关远程接口
- 本地文件：`plugins/A_music/cookies.json`
- 本地目录：`plugins/A_music/music/`

## 注意事项
- 搜索与下载依赖 `cookies.json` 中的网易云登录态
- 下载后的音频会缓存在插件目录下

## 相关代码
- `plugins/A_music/A_music.py`
- `plugins/A_music/music_api.py`
