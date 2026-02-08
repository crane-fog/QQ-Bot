import re

from sqlalchemy import BigInteger, Column, DateTime, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Logging.PrintLog import Log
from Plugins import Plugins, plugin_main

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
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                记录群聊消息到数据库
                                usage: auto
                            """
        self.init_status()

    async def resolve_replies(self, session: AsyncSession, message: str) -> str:
        matches = list(PATTERN.finditer(message))
        if not matches:
            return message

        for match in reversed(matches):
            reply_id = int(match.group(1))
            result = await session.execute(select(Message).where(Message.msg_id == reply_id))
            row = result.scalars().one_or_none()
            if row is not None:
                replacement = f'[CQ:reply,id={reply_id},content="{row.msg}",from_nickname="{row.user_nickname}",from_card="{row.user_card}"]'
                message = message[: match.start()] + replacement + message[match.end() :]

        return message

    @plugin_main(check_call_word=False, check_group=False, require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        async_sessions = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )
        async with async_sessions() as session:
            async with session.begin():
                resolved_message = await self.resolve_replies(session, event.message)
                new_msg = Message(
                    user_id=event.user_id,
                    group_id=event.group_id,
                    msg=resolved_message,
                    msg_id=event.message_id,
                    user_nickname=event.nickname,
                    user_card=event.card,
                )
                session.add(new_msg)
