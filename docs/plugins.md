# 插件总览

本文档为 QQ-Bot 插件的总览，包括插件的类型、用途、触发方式等。

|类型|说明|
|---|---|
|`Group`|群消息插件。主要处理普通群聊消息，既可能是命令触发，也可能是自动响应群消息。|
|`GroupRequest`|群请求插件。处理入群申请等群请求事件。|
|`GroupRecall`|群撤回插件。处理群消息撤回相关事件，通常需要配合消息记录使用。|
|`Poke`|戳一戳插件。处理群里的戳一戳事件。|
|`Record`|记录型插件。主要用于记录消息或为其他插件提供上下文数据，不直接面向普通交互。|


**由于开发精力有限，只会有部分插件的文档会经过人工审核，剩下的插件文档会由 AI 生成。**


## 总览表

| 插件名 | 类型 | 用途 | 触发方式 | 文档由AI生成 |
| --- | --- | --- | --- | --- |
| [`AI`](plugins/AI.md) | `Group` | 简短问答插件，使用 Gemini 模型回答问题。 | 命令触发：`monika ask <提问内容>` | 是 |
| [`AskForward`](plugins/AskForward.md) | `Group` | 将提问群消息转发到答疑群，并支持回复回传。 | 自动触发：`#Q#` 提问、回复转发消息回答、普通消息追问 | 是 |
| [`A_music`](plugins/A_music.md) | `Group` | 搜索网易云音乐并发送语音或文件。 | 命令触发：`/music ...` | 是 |
| [`A_Pixiv`](plugins/A_Pixiv.md) | `Group` | 根据作品 ID 获取 Pixiv 图片，并支持清理发送结果。 | 命令触发：`pid...`、`p_clean` | 是 |
| [`DataImport`](plugins/DataImport.md) | `Group` | 导入成绩、行数或学生列表等数据到数据库。 | 命令触发：`DataImport ...` | 是 |
| [`DontPoke`](plugins/DontPoke.md) | `Poke` | 对戳一戳事件作出回复，有概率反戳。 | 戳一戳触发 | 是 |
| [`EmojiLike`](plugins/EmojiLike.md) | `Group` | 自动给消息添加表情回应。 | 自动触发 | 是 |
| [`ExamplePlugin`](plugins/ExamplePlugin.md) | `Group` | 插件模板示例，用于演示插件基本结构。 | 自动触发 | 是 |
| [`GetStuId`](plugins/GetStuId.md) | `Group` | 获取指定群成员 QQ 号和学号映射并写入数据库。 | 命令触发：`GetStuId <群号>` | 是 |
| [`GroupApprove`](plugins/GroupApprove.md) | `GroupRequest` | 自动处理入群申请。 | 群请求事件触发 | 是 |
| [`GroupSum`](plugins/GroupSum.md) | `Group` | 总结群聊消息，通过 LLM 生成摘要和话题分析。 | 命令触发：`Summary <消息条数>` | 是 |
| [`I_like_you`](plugins/I_like_you.md) | `Group` | 根据固定台词发送本地语音。 | 命令触发：`我喜欢你`、`我不喜欢你` | 是 |
| [`LineCount`](plugins/LineCount.md) | `Group` | 查询用户代码行数相关信息。 | 命令触发：`Theresa linecount` | 是 |
| [`MessageRecorder`](plugins/MessageRecorder.md) | `Record` | 记录群消息到数据库，为上下文类插件提供数据。 | 自动触发 | 是 |
| [`MoeGoe`](plugins/MoeGoe.md) | `Group` | 调用语音合成服务生成并发送语音。 | 命令触发：`moegoe ema/sheri zh/ja <文本>` | 是 |
| [`QiuDao`](plugins/QiuDao.md) | `Group` | 根据数据库中的记录响应“求刀/公开成绩”类指令。 | 命令触发：`Theresa 求刀`、`Theresa 公开我的期末成绩吧` | 是 |
| [`RecallPrevent`](plugins/RecallPrevent.md) | `GroupRecall` | 记录消息并在用户撤回后把内容重新发出来。 | 自动触发；撤回事件触发 | 是 |
| [`Repeater`](plugins/Repeater.md) | `Group` | 检测复读并按配置撤回或禁言。 | 自动触发 | 是 |
| [`TheresaAI`](plugins/TheresaAI.md) | `Group` | 以 Theresa 人设进行群聊问答。 | 命令触发：`Theresa ask <提问内容>` | 是 |
| [`TheresaBan`](plugins/TheresaBan.md) | `Group` | 对群成员执行禁言。 | 命令触发：`Theresa ban <@> <禁言秒数>` | 是 |
| [`Theresac`](plugins/Theresac.md) | `Group` | 执行系统命令，仅允许 bot 主人使用。 | 命令触发：`Theresac <命令>` | 是 |
| [`TheresaCard`](plugins/TheresaCard.md) | `Group` | 处理群名片检查、清理或调试相关操作。 | 命令触发：`Theresa card ...` | 是 |
| [`TheresaCardBatch`](plugins/TheresaCardBatch.md) | `Group` | 对多个目标群批量执行群名片相关操作。 | 命令触发：`Theresa card ...` | 是 |
| [`TheresaChat`](plugins/TheresaChat.md) | `Group` | 结合数据库上下文自动聊天，并可能发送表情图片。 | 自动触发 | 是 |
| [`TheresaDora`](plugins/TheresaDora.md) | `Group` | 生成哆啦 A 梦大叫风格图片。 | 命令触发：`Dora <内容>` | 是 |
| [`TheresaGoodMorning`](plugins/TheresaGoodMorning.md) | `Group` | 响应早安/晚安问候。 | 命令触发：`Theresa 早安`、`Theresa 晚安` | 是 |
| [`TheresaHelp`](plugins/TheresaHelp.md) | `Group` | 列出当前群启用的插件及其说明。 | 命令触发：`Theresa help`、`Theresa help <插件名>` | 是 |
| [`TheresaImage`](plugins/TheresaImage.md) | `Group` | 对回复的图片消息进行 AI 识图。 | 回复消息触发：`<回复图片消息>Timage (<文本>)` | 是 |
| [`TheresaMathAI`](plugins/TheresaMathAI.md) | `Group` | 处理偏数学类问题，并可返回文件。 | 命令触发：`math ask <提问内容>` | 是 |
| [`TheresaWithdraw`](plugins/TheresaWithdraw.md) | `Group` | 撤回被回复的消息。 | 回复消息触发：`<回复消息>Twithdraw` | 是 |
