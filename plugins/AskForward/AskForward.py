import re
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, Column, DateTime, Integer, Text, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from utils.CQHelper import CQHelper
from utils.CQType import Forward, Reply

Base = declarative_base()


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discussion_id = Column(Integer, nullable=False)
    id_of_message = Column(BigInteger, nullable=False, unique=True)


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


class AskForward(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "AskForward"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                转发高程班级群消息至答疑群，转发回答
                                usage: 提问：以 #Q# 开头\n回答/追问：「回复」（引用）bot 转发的消息\n注意：bot 仅抓取触发「前」 1 分钟内的内容，请先发送图片（如需要），最后再发送带有 #Q# 或「回复」的消息（或者将图文放在一条消息中发送），以免漏转。
                            """
        self.init_status()
        self.session_factory: sessionmaker = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        broadcast_target_group: int = self.config.getint("broadcast_target_group")
        answer_group: int = self.config.getint("answer_group")
        ask_groups: list[int] = list(map(int, self.config.get("ask_groups").split(",")))

        check_message = event.message.strip()
        while check_message.startswith("[CQ:image,"):
            check_message = check_message.split("]", 1)[1].strip()

        # 提问
        if event.group_id in ask_groups and check_message.startswith("#Q#"):
            async with self.session_factory() as session:
                discussion_id = (
                    await session.execute(select(func.max(AskMessage.discussion_id)))
                ).scalar() + 1
                ask_message = AskMessage(discussion_id=discussion_id, id_of_message=event.sql_id)
                session.add(ask_message)
                await session.commit()

            msgs = await self.find_message(sender_id=event.user_id, group_id=event.group_id)
            forward_msg: Forward = Forward()
            async with self.session_factory() as session:
                for msg in msgs[:-1]:
                    forward_msg.add_node(
                        type="msg",
                        msg=msg.msg,
                        sender_name=msg.user_nickname,
                        uid=msg.user_id,
                    )
                    ask_message = AskMessage(discussion_id=discussion_id, id_of_message=msg.id)
                    session.add(ask_message)
                await session.commit()

            self.api.groupService.send_group_forward_msg(
                group_id=answer_group, forward_message=forward_msg.message
            )
            self.api.groupService.send_group_msg(
                group_id=answer_group,
                message=f"#{discussion_id} {event.sql_id} from {event.group_name}\n{event.card}\n{event.message}",
            )
        # 回答
        elif event.group_id == answer_group and event.message.startswith("[CQ:reply,"):
            async with self.session_factory() as session:
                cqs = CQHelper.loads_cq(event.message)
                for cq in cqs:
                    if cq.cq_type == "reply":
                        try:
                            reply_id = int(cq.id)
                            result = await session.execute(
                                select(Message).where(Message.msg_id == reply_id)
                            )
                            row = result.scalars().one_or_none()
                            id_data = row.msg.split("#", 1)[1].split(" from ", 1)[0]
                        except Exception:
                            return

                discussion_id = int(id_data.split(" ", 1)[0])
                origin_message_id = int(id_data.split(" ", 1)[1])

                source_group_id = await session.scalar(
                    select(Message.group_id)
                    .join(AskMessage, Message.id == AskMessage.id_of_message)
                    .where(AskMessage.discussion_id == discussion_id)
                    .order_by(AskMessage.id_of_message.asc())
                    .limit(1)
                )
                source_message_id = await session.scalar(
                    select(Message.msg_id)
                    .where(Message.id == origin_message_id, Message.group_id == source_group_id)
                    .order_by(Message.id.desc())
                )

                answer_message = AskMessage(discussion_id=discussion_id, id_of_message=event.sql_id)
                session.add(answer_message)
                await session.commit()

            self.api.groupService.send_group_msg(
                group_id=source_group_id,
                message=f"{Reply(id=source_message_id)}#{discussion_id} {event.sql_id}\n{clean_at(event.message.split(']', 1)[1], True)}",
            )
        # 追问
        elif event.group_id in ask_groups and event.message.startswith("[CQ:reply,"):
            async with self.session_factory() as session:
                cqs = CQHelper.loads_cq(event.message)
                for cq in cqs:
                    if cq.cq_type == "reply":
                        try:
                            reply_id = int(cq.id)
                            result = await session.execute(
                                select(Message).where(Message.msg_id == reply_id)
                            )
                            row = result.scalars().one_or_none()
                            if row.user_id != self.bot.bot_id:
                                return
                            id_data = row.msg.split("#", 1)[1].split("\n", 1)[0]
                        except Exception:
                            self.api.groupService.send_group_msg(
                                group_id=answer_group,
                                message=f"未归类消息 from {event.group_name}\n{event.card}",
                            )
                            self.api.groupService.send_group_msg(
                                group_id=answer_group,
                                message=event.message.split("]", 1)[1].strip(),
                            )
                            return

                discussion_id = int(id_data.split(" ", 1)[0])
                origin_message_id = int(id_data.split(" ", 1)[1])

                source_message_id = await session.scalar(
                    select(Message.msg_id)
                    .where(Message.id == origin_message_id)
                    .order_by(Message.id.desc())
                )

                ask_message = AskMessage(discussion_id=discussion_id, id_of_message=event.sql_id)
                session.add(ask_message)
                await session.commit()

            msgs = await self.find_message(
                sender_id=event.user_id, group_id=event.group_id, last_message_id=origin_message_id
            )
            forward_msg: Forward = Forward()
            async with self.session_factory() as session:
                for msg in msgs[:-1]:
                    forward_msg.add_node(
                        type="msg",
                        msg=msg.msg,
                        sender_name=msg.user_nickname,
                        uid=msg.user_id,
                    )
                    stmt = (
                        insert(AskMessage)
                        .values(discussion_id=discussion_id, id_of_message=msg.id)
                        .on_conflict_do_nothing()
                    )
                    await session.execute(stmt)
                await session.commit()

            self.api.groupService.send_group_forward_msg(
                group_id=answer_group, forward_message=forward_msg.message
            )
            self.api.groupService.send_group_msg(
                group_id=answer_group,
                message=f"{Reply(id=source_message_id)}#{discussion_id} {event.sql_id} from {event.group_name}\n{event.card}\n{clean_at(event.message.split(']', 1)[1], True)}",
            )
        # 广播
        elif event.group_id == answer_group and event.message.startswith("Broadcast"):
            broadcast_msg: Forward = Forward()
            discussion_id = int(event.message.split(" ", 1)[1])
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Message)
                    .join(AskMessage, Message.id == AskMessage.id_of_message)
                    .where(AskMessage.discussion_id == discussion_id)
                    .order_by(AskMessage.id_of_message.asc())
                )
                rows: list[Message] = result.scalars().all()
                for row in rows:
                    msg = row.msg.split("]", 1)[1] if row.msg.startswith("[CQ:reply,") else row.msg
                    msg = clean_at(msg, True)

                    broadcast_msg.add_node(
                        type="msg",
                        msg=msg,
                        sender_name=row.user_card,
                        uid=row.user_id,
                    )
            self.api.groupService.send_group_forward_msg(
                group_id=broadcast_target_group, forward_message=broadcast_msg.message
            )
        # fallback
        elif event.group_id in ask_groups and event.user_id not in self.bot.assistant_list:
            self.api.groupService.send_group_msg(
                group_id=answer_group,
                message=f"未归类消息 from {event.group_name}\n{event.card}",
            )
            self.api.groupService.send_group_msg(
                group_id=answer_group,
                message=event.message,
            )
        return

    async def find_message(
        self, sender_id: int, group_id: int, time: int = 1, last_message_id: int = None
    ) -> list[Message]:
        """
        寻找指定时间（1分钟）内发送的消息
        """
        async with self.session_factory() as session:
            start_time = datetime.now() - timedelta(minutes=time)
            result = await session.execute(
                select(Message)
                .where(
                    Message.user_id == sender_id,
                    Message.group_id == group_id,
                    Message.send_time >= start_time,
                    Message.id > last_message_id if last_message_id else True,
                )
                .order_by(Message.send_time.asc())
            )
            rows = result.scalars().all()
            return rows


def clean_at(msg: str, move: bool = False) -> str:
    pattern = r"\[CQ:at,[^\]]*name=([^,\]]+)[^\]]*\]"
    if move:
        return re.sub(pattern, r"", msg).strip()
    else:
        return re.sub(pattern, r"@\1", msg)
