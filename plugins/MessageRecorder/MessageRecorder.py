from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.event_handler.SendEventHandler import SendEvent
from src.Models import Message
from utils.CQHelper import CQHelper


class MessageRecorder(Plugins):
    def __init__(self, bot):
        super().__init__(bot)
        self.name = "MessageRecorder"
        self.type = "Record"
        self.author = "Heai"
        self.introduction = """
                                记录群聊消息到数据库
                                usage: auto
                            """
        self.init_status()
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    async def resolve_msg(self, message: str) -> str:
        cqs = CQHelper.loads_cq(message)
        for cq in cqs:
            if cq.cq_type == "image":
                msg = str(cq)
                cq.path = await api.asyncMessageService.get_image(cq.file)
                del cq.url
                if cq.path is not None:
                    message = message.replace(msg, str(cq))

        return message

    @plugin_main(check_call_word=False, check_group=False, require_db=True)
    async def main(self, event: GroupMessageEvent | SendEvent, debug: bool):

        if isinstance(event, SendEvent) and event.message_type != "group":
            return

        async with self.session_factory() as session:
            resolved_message = await self.resolve_msg(event.message.replace("&amp;", "&"))
            new_msg = Message(
                user_id=event.user_id,
                group_id=event.group_id,
                msg=resolved_message,
                msg_id=event.message_id,
                user_nickname=event.nickname,
                user_card=event.card,
            )
            session.add(new_msg)
            await session.flush()
            event.sql_id = new_msg.id
            await session.commit()
