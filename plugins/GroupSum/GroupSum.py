import json
import os
from datetime import timedelta, timezone

from jinja2 import Template
from sqlalchemy import BigInteger, Column, DateTime, Text, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.PrintLog import Log
from utils.AITools import encode_image, get_llm_response
from utils.CQHelper import CQHelper
from utils.CQType import Forward

Base = declarative_base()


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

    @property
    def formatted_time(self) -> str:
        return self.send_time.astimezone(timezone(timedelta(hours=8))).strftime("%H:%M")


class GroupSum(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "GroupSum"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                总结群聊消息
                                usage: Summary <消息条数>
                            """
        self.init_status()

        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

        with open(os.path.join(os.path.dirname(__file__), "prompt.j2"), encoding="utf-8") as f:
            self.persona_template = Template(f.read())

    @plugin_main(call_word=["Summary"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        self.max_length = self.config.getint("max_length")

        msg = event.message.strip().split(" ")
        if len(msg) != 2 or not msg[1].isdigit():
            return

        context_length = int(msg[1]) if int(msg[1]) <= self.max_length else self.max_length

        Log.debug(
            f"插件：{self.name}在群{event.group_id}触发，准备总结{context_length}条消息", debug
        )

        persona = self.persona_template.render(
            group_name=event.group_name,
        )

        context_messages = await self.load_context_from_db(
            event.group_id,
            context_length,
            resolve_imgs=False,
        )

        response = await get_llm_response(
            [
                {"role": "system", "content": persona},
                *context_messages,
            ],
            model="deepseek-v4-pro",
            use_tools=True,
            api=self.api,
            response_format={"type": "json_object"},
            insert_persona=True,
        )

        response_json: dict = json.loads(response)

        message = Forward()
        message.add_node(
            type="msg",
            msg=response_json.get("description", "没有总结内容。"),
        )
        for topic in response_json.get("topics", []):
            message.add_node(
                type="msg",
                msg=f"话题：{topic.get('topic', '无')}\n参与者：{', '.join(map(str, topic.get('contributors', ['无'])))}\n详情：{topic.get('detail', '无')}",
            )

        self.api.groupService.send_group_forward_msg(
            group_id=event.group_id, forward_message=message.message
        )
        Log.debug(f"插件：{self.name}在群{event.group_id}完成总结并发送消息", debug)
        return

    async def resolve_img(self, message: str) -> list[dict]:
        cqs = CQHelper.loads_cq(message)
        msgs = []
        for cq in cqs:
            if cq.cq_type == "image":
                msgs.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": encode_image(cq.path)},
                    }
                )
                message = message.replace(str(cq), "")
        if message.strip():
            msgs.insert(0, {"type": "text", "text": message.strip()})
        return msgs

    async def resolve_reply(self, session: AsyncSession, message: str) -> str:
        cqs = CQHelper.loads_cq(message)
        for cq in cqs:
            if cq.cq_type == "reply":
                reply_id = int(cq.id)
                result = await session.execute(
                    select(Message).where(Message.msg_id == reply_id).order_by(desc(Message.id))
                )
                row = result.scalars().first()
                if row is not None:
                    msg = str(cq)
                    cq.content = row.msg
                    cq.from_nickname = row.user_nickname
                    cq.from_card = row.user_card
                    message = message.replace(msg, str(cq))
        return message

    async def load_context_from_db(
        self,
        group_id: int,
        context_length: int,
        resolve_imgs: bool = False,
    ) -> list:
        context = []
        async with self.session_factory() as session:
            stmt = (
                select(Message)
                .where(Message.group_id == group_id)
                .order_by(desc(Message.id))
                .limit(context_length)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for row in reversed(rows):
                if row.user_id == self.bot.bot_id:
                    context.append(
                        {
                            "role": "assistant",
                            "content": row.msg,
                        }
                    )
                else:
                    msg = await self.resolve_reply(session, row.msg)
                    if resolve_imgs:
                        img_msgs = await self.resolve_img(row.msg)
                        img_msgs.insert(
                            0,
                            {
                                "type": "text",
                                "text": f"{row.formatted_time}\n{row.user_nickname}(群名片：{row.user_card}，id：{row.user_id})说：",
                            },
                        )
                        context.extend(
                            [
                                {
                                    "role": "user",
                                    "content": img_msgs,
                                    "name": str(row.user_id),
                                }
                            ]
                        )
                    else:
                        context.append(
                            {
                                "role": "user",
                                "content": f"{row.formatted_time}\n{row.user_nickname}(群名片：{row.user_card}，id：{row.user_id})说：\n{msg}",
                                "name": str(row.user_id),
                            }
                        )
        return context
