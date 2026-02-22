import re

from sqlalchemy import BigInteger, Column, DateTime, Text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.event_handler.SendEventHandler import SendEvent
from src.PrintLog import Log
from utils.CQHelper import CQHelper

log = Log()
Base = declarative_base()

PATTERN = re.compile(r"\[CQ:reply,id=(-?\d+)\]")


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    group_id = Column(BigInteger, nullable=False)
    msg = Column(Text, nullable=False)
    send_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    msg_id = Column(BigInteger, nullable=False, default=0)
    user_nickname = Column(Text, nullable=False, default=" ")
    user_card = Column(Text, nullable=False, default=" ")


class MessageRecorder(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
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

    def resolve_msg(self, message: str) -> str:
        cqs = CQHelper.loads_cq(message)
        for cq in cqs:
            if cq.cq_type == "image":
                msg = str(cq)
                cq.path = (
                    self.api.MessageService.get_image(self, cq.file)
                    .get("data", {})
                    .get("file", None)
                )
                del cq.url
                if cq.path is not None:
                    message = message.replace(msg, str(cq))

        return message

    @plugin_main(check_call_word=False, check_group=False, require_db=True)
    async def main(self, event: GroupMessageEvent | SendEvent, debug):

        if isinstance(event, SendEvent) and event.message_type != "group":
            return

        async with self.session_factory() as session:
            async with session.begin():
                resolved_message = self.resolve_msg(event.message.replace("&amp;", "&"))
                new_msg = Message(
                    user_id=event.user_id,
                    group_id=event.group_id,
                    msg=resolved_message,
                    msg_id=event.message_id,
                    user_nickname=event.nickname,
                    user_card=event.card,
                )
                session.add(new_msg)
