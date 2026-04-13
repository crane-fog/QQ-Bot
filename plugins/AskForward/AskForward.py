from datetime import datetime, timedelta

from sqlalchemy import BigInteger, Column, DateTime, Integer, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from utils.CQHelper import CQHelper
from utils.CQType import CQMessage, Forward, Reply

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
                                usage: 提问：以 #Q# 开头\n回答：「回复」（引用）bot 转发的消息\n追问：发送不带 #Q# 的消息\n注意：如需额外发送图片或其他文件，请放在#Q#的消息之后发送
                            """
        self.init_status()
        self.session_factory: sessionmaker = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )
        self.special_assistant_list: set[int] = set()

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        broadcast_target_group: int = self.config.getint("broadcast_target_group")
        answer_group: int = self.config.getint("answer_group")
        ask_groups: list[int] = list(map(int, self.config.get("ask_groups").split(",")))
        self.special_assistant_list: set[int] = set(
            map(int, self.config.get("special_assistant_list", "").split(","))
        )

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
                        msg=msg[1],
                        sender_name=event.nickname,
                        uid=event.user_id,
                    )
                    ask_message = AskMessage(discussion_id=discussion_id, id_of_message=msg[0])
                    session.add(ask_message)
                await session.commit()

            self.api.groupService.send_group_forward_msg(
                group_id=answer_group, forward_message=forward_msg.message
            )
            await self.forward_message(
                event=event,
                target_group_id=answer_group,
                keep_card=True,
                keep_group_name=True,
                reply_id=None,
                discussion_id=discussion_id,
            )
        # 回答
        elif event.group_id == answer_group and event.message.startswith("[CQ:reply,"):
            id_data = await self.resolve_reply(event.message)
            discussion_id: str = id_data.split(" ", 1)[0]
            origin_message_sql_id: str = id_data.split(" ", 1)[1]
            async with self.session_factory() as session:
                if origin_message_sql_id == "None":
                    return
                else:
                    source_group_id, source_message_id = (
                        await session.execute(
                            select(Message.group_id, Message.msg_id).where(
                                Message.id == int(origin_message_sql_id)
                            )
                        )
                    ).first()
                if discussion_id != "None":
                    answer_message = AskMessage(
                        discussion_id=int(discussion_id), id_of_message=event.sql_id
                    )
                    session.add(answer_message)
                    await session.commit()
            await self.forward_message(
                event=event,
                target_group_id=source_group_id,
                keep_card=False,
                keep_group_name=False,
                reply_id=source_message_id,
                discussion_id=discussion_id,
            )
        # 追问
        elif event.group_id in ask_groups:
            if (
                event.user_id in self.bot.assistant_list
                or event.user_id in self.special_assistant_list
            ):
                return

            msgs = await self.find_message(
                sender_id=event.user_id, group_id=event.group_id, time=1440
            )
            if len(msgs) < 2:
                await self.forward_message(
                    event=event,
                    target_group_id=answer_group,
                    keep_card=True,
                    keep_group_name=True,
                )
            else:
                origin_message_sql_id = msgs[-2][0]
                async with self.session_factory() as session:
                    discussion_id = await session.scalar(
                        select(AskMessage.discussion_id).where(
                            AskMessage.id_of_message == origin_message_sql_id
                        )
                    )
                    if discussion_id is not None:
                        ask_message = AskMessage(
                            discussion_id=discussion_id, id_of_message=event.sql_id
                        )
                        session.add(ask_message)
                        await session.commit()

                await self.forward_message(
                    event=event,
                    target_group_id=answer_group,
                    keep_card=True,
                    keep_group_name=True,
                    reply_id=None,
                    discussion_id=discussion_id,
                )
        # 广播
        elif event.group_id == answer_group and event.message.startswith("Broadcast"):
            broadcast_msg: Forward = Forward()
            discussion_id = int(event.message.split(" ", 1)[1])
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Message.msg, Message.user_id, Message.user_card)
                    .join(AskMessage, Message.id == AskMessage.id_of_message)
                    .where(AskMessage.discussion_id == discussion_id)
                    .order_by(AskMessage.id_of_message.asc())
                )
                rows: list[tuple[str, int, str]] = result.all()
                for row in rows:
                    msg = remove_reply(clean_at(row[0], True))
                    broadcast_msg.add_node(
                        type="msg",
                        msg=msg,
                        sender_name=row[2],
                        uid=row[1],
                    )
            self.api.groupService.send_group_forward_msg(
                group_id=broadcast_target_group, forward_message=broadcast_msg.message
            )
        return

    # 寻找指定时间（1分钟）内发送的消息
    async def find_message(
        self, sender_id: int, group_id: int, time: int = 1, last_message_id: int = None
    ) -> list[tuple[int, str]]:
        async with self.session_factory() as session:
            start_time = datetime.now() - timedelta(minutes=time)
            result = await session.execute(
                select(Message.id, Message.msg)
                .where(
                    Message.user_id == sender_id,
                    Message.group_id == group_id,
                    Message.send_time >= start_time,
                    Message.id > last_message_id if last_message_id else True,
                )
                .order_by(Message.id.asc())
            )
            rows: list[tuple[int, str]] = result.all()
            return rows

    # 带补充信息的转发一条消息
    async def forward_message(
        self,
        event: GroupMessageEvent,
        target_group_id: int,
        keep_card: bool,
        keep_group_name: bool,
        reply_id: int | None = None,
        discussion_id: int | None = None,
    ) -> None:
        self.api.groupService.send_group_msg(
            group_id=target_group_id,
            message=f"{Reply(id=reply_id) if reply_id is not None else ''}#{discussion_id if discussion_id is not None else 'None'} {event.sql_id} from {event.group_name if keep_group_name else '答疑'}\n{(event.card + '\n') if keep_card else ''}{remove_reply(clean_at(event.message, True))}",
        )

    # 从回复消息中解析出被回复的消息的讨论 ID 和数据库消息 ID
    async def resolve_reply(self, message: str) -> str:
        async with self.session_factory() as session:
            cqs = CQHelper.loads_cq(message)
            for cq in cqs:
                if cq.cq_type == "reply":
                    try:
                        reply_id = int(cq.id)
                        result = await session.execute(
                            select(Message.msg)
                            .where(Message.msg_id == reply_id)
                            .order_by(Message.id.desc())
                        )
                        msg = result.scalars().one_or_none()
                        return msg.split("#", 1)[1].split(" from ", 1)[0]
                    except Exception:
                        return "None None"
        return "None None"


def clean_at(msg: str, move: bool = False) -> str:
    cqs: list[CQMessage] = CQHelper.loads_cq(msg)
    for cq in cqs:
        if cq.cq_type == "at":
            if cq.qq == "all":
                msg = msg.replace(f"{cq}", "" if move else "@全体成员")
            else:
                name = getattr(cq, "name", None)
                if name:
                    msg = msg.replace(f"{cq}", "" if move else f"@{name}")
                else:
                    msg = msg.replace(f"{cq}", "" if move else f"@{cq.qq}")
    return msg.strip()


def remove_reply(msg: str) -> str:
    cqs: list[CQMessage] = CQHelper.loads_cq(msg)
    for cq in cqs:
        if cq.cq_type == "reply":
            msg = msg.replace(f"{cq}", "")
    return msg.strip()
