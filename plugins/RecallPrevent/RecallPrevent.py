import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.NoticeEventHandler import GroupRecallEvent
from src.Models import Message
from utils.CQType import At


class RecallPrevent(Plugins):
    """
    插件名：RecallPrevent \n
    插件类型：群聊撤回插件 \n
    插件功能：当有人在群聊撤回消息时，bot会自动发送撤回消息内容的消息 \n
    """

    def __init__(self, bot):
        super().__init__(bot)
        self.name = "RecallPrevent"
        self.type = "GroupRecall"
        self.author = "kiriko"
        self.introduction = """
                                撤回你的撤回
                                usage: auto
                            """
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )
        self.init_status()

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupRecallEvent, debug: bool):
        user_info = api.groupService.get_group_member_info(
            group_id=event.group_id, user_id=event.user_id
        ).get("data", {})
        print(user_info)
        if not self.config.get("for_administer", False):
            print(user_info.get("role"))
            if user_info.get("role") == "admin" or user_info.get("role") == "owner":
                return

        # 获取消息数据
        async with self.session_factory() as session:
            stmt = (
                select(Message.msg)
                .where(Message.group_id == event.group_id, Message.msg_id == event.message_id)
                .order_by(Message.id.desc())
                .limit(1)
            )
            result = await session.scalar(stmt)
            if not result:
                return

        card_cuts = user_info["card"].split("-")
        recalled_message = result

        # 提取配置
        for_everyone = self.config.get("for_everyone", False)
        ban = self.config.get("ban", False)
        ban_time = self.config.get("ban_time")
        ban_time_cuts = ban_time.split("-")
        min_ban_time = ban_time_cuts[0].split(":")
        max_ban_time = ban_time_cuts[1].split(":")
        duration = random.randint(
            int(min_ban_time[0]) * 3600 + int(min_ban_time[1]) * 60 + int(min_ban_time[2]),
            int(max_ban_time[0]) * 3600 + int(max_ban_time[1]) * 60 + int(max_ban_time[2]),
        )
        ignored_ids: list[int] = self.config.get("ignored_ids", [])

        # 过滤
        if event.user_id in ignored_ids:
            return
        if len(card_cuts) == 3:
            if card_cuts[1] == "助教":
                if not for_everyone:
                    return

        if event.user_id == event.operator_id:
            reply_message = f"{At(qq=event.user_id)} 撤回的消息是：{recalled_message}"
            api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)

            if ban:
                api.groupService.set_group_ban(
                    group_id=event.group_id, user_id=event.user_id, duration=duration
                )
        return
