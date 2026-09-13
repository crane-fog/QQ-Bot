import re

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.gitea.GiteaApi import GiteaApi, GiteaApiError
from src.PrintLog import Log

# #<issue编号> <内容>，要求编号后有空格且内容非空，避免群里的 #话题# 式闲聊误触
REPLY_PATTERN = re.compile(r"^#(?P<number>\d+)\s+(?P<body>\S.*)$", re.DOTALL)


class GiteaReply(Plugins):
    def __init__(self, bot):
        super().__init__(bot)
        self.name = "GiteaReply"
        self.type = "Group"
        self.author = "oierxjn"
        self.introduction = """
                                把 QQ 群消息回复到 Gitea issue
                                usage: #<issue编号> <内容>
                            """
        self.repo = str(self.bot.bot_config.get("Gitea", {}).get("reply_repo", "")).strip()
        if not self.repo:
            Log.error("GiteaReply 插件未配置 [Gitea] reply_repo，收到回帖请求时将被忽略")
        self.gitea = GiteaApi(self.bot.gitea_api_url, self.bot.gitea_api_token)
        self.init_status()

    @plugin_main(call_word=["#"])
    async def main(self, event: GroupMessageEvent, debug: bool):
        match = REPLY_PATTERN.match(event.message.strip())
        if not match or not self.repo:
            return

        number = int(match["number"])
        sender = event.card or event.nickname or str(event.user_id)
        comment_body = f"**来自 QQ 群反馈**（{sender}）：\n\n{match['body'].strip()}"

        try:
            issue = await self.gitea.get_issue(self.repo, number)
            comment = await self.gitea.create_issue_comment(self.repo, number, comment_body)
        except GiteaApiError as e:
            hint = (
                f"issue #{number} 不存在，请确认编号" if e.status_code == 404 else f"回复失败：{e}"
            )
            await api.asyncService.send_group_msg(
                group_id=event.group_id, message=f"[Gitea] {hint}"
            )
            return

        Log.info(f"GiteaReply 已回复 issue #{number}（群{event.group_id}，{sender}）")
        await api.asyncService.send_group_msg(
            group_id=event.group_id,
            message=f"[Gitea] 已回复 issue #{number}「{issue.title}」\n{comment.html_url}",
        )
