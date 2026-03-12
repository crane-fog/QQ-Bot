import datetime
import json
import os
import random
import time
from collections import deque

from jinja2 import Template
from sqlalchemy import BigInteger, Column, DateTime, Text, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.AITools import get_dpsk_response
from utils.CQHelper import CQHelper
from utils.CQType import CQMessage

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


class TheresaChat(Plugins):
    """
    插件名：TheresaChat \n
    插件类型：群聊插件 \n
    插件功能：记录上下文并智能回复 \n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaChat"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                聊天插件
                                usage: auto
                            """
        self.init_status()

        # 冷却时间，防止刷屏
        self.group_cooldown = {}
        self.cooldown_time = 5

        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

        # 滑动窗口记录最近发送的表情id，用于降低重复度
        self.recent_faces = deque(maxlen=10)

        with open(os.path.join(os.path.dirname(__file__), "persona.j2"), encoding="utf-8") as f:
            self.persona_template = Template(f.read())
        with open(
            os.path.join(os.path.dirname(__file__), "persona_face.j2"), encoding="utf-8"
        ) as f:
            self.persona_face_template = Template(f.read())

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupMessageEventHandler, debug: bool):
        # 从数据库读取的上下文消息条数
        self.context_length = self.config.getint("context_length")
        self.context_length_for_face = self.config.getint("context_length_for_face")

        message = event.message
        group_id = event.group_id
        face_flag = False

        clean_message = message.strip()
        if not clean_message:
            return  # 忽略空消息

        if event.user_id == self.bot.owner_id and clean_message.startswith("chat stop"):
            sleep_time = int(clean_message.split(" ")[2])
            self.group_cooldown[group_id] = time.time() + sleep_time  # 停止回复指定时间
            return

        # 冷却检查
        current_time = time.time()
        last_reply_time = self.group_cooldown.get(group_id, 0)
        if current_time - last_reply_time < self.cooldown_time:
            return

        r = random.random()
        if (("牢普" in clean_message) or ("普瑞赛斯" in clean_message)) and r > 0.9:
            msg_list = [
                "我一直都看着你…永远…………👁️",
                "这里万籁俱寂……太安静了……别留下我……",
                "…博士，不准忘记我。",
                "深陷长梦的混沌之时，你会想起——",
                "我们的呼吸▮▮▮温暖▮▮▮▮▮▮▮▮双手",
                "PRTS Runtime Error 0x5343: Debug Assertion Failed at File: /src/arknights/battle/scene/scene_main.cpp, Line: 2432",
            ]
            msg = random.choice(msg_list)
            await self.save_bot_reply_to_db(group_id, msg)
            self.api.groupService.send_group_msg(group_id=group_id, message=msg)
            Log.debug(
                f'插件：{self.name}在群{group_id}被消息"{message}"触发，发送特殊回复',
                debug,
            )
            return

        if ("小特" not in clean_message) or ("Theresa" in clean_message):
            if r < 0.01:
                face_flag = True
            else:
                return

        Log.debug(f'插件：{self.name}在群{group_id}被消息"{message}"触发，准备获取回复', debug)

        if face_flag:
            context_messages = await self.load_context_from_db(
                group_id, self.context_length_for_face
            )
            image_id = self.get_dpsk_response_for_face(context_messages)
            if image_id != 0:
                image_name = f"{os.path.dirname(os.path.abspath(__file__))}/faces/{image_id}.png"
                msg = CQMessage()
                msg.cq_type = "image"
                msg.subType = "1"
                msg.file = f"file://{image_name}"
                self.api.groupService.send_group_msg(group_id=group_id, message=str(msg))
        else:
            persona = self.persona_template.render(
                owner_id=self.bot.owner_id,
                current_time=datetime.datetime.now().time(),
                group_name=event.group_name,
            )

            context_messages = await self.load_context_from_db(group_id, self.context_length)
            response = get_dpsk_response(
                [
                    {"role": "system", "content": persona},
                    *context_messages,
                ],
                temperature=1.5,
            )
            if "[NO REPLY]" not in response:
                # 更新冷却时间
                self.group_cooldown[group_id] = time.time()
                self.api.groupService.send_group_msg(group_id=group_id, message=response)

    async def resolve_msg(self, session: AsyncSession, message: str) -> str:
        cqs = CQHelper.loads_cq(message)
        for cq in cqs:
            if cq.cq_type == "reply":
                reply_id = int(cq.id)
                result = await session.execute(select(Message).where(Message.msg_id == reply_id))
                row = result.scalars().one_or_none()
                if row is not None:
                    msg = str(cq)
                    cq.content = row.msg
                    cq.from_nickname = row.user_nickname
                    cq.from_card = row.user_card
                    message = message.replace(msg, str(cq))
        return message

    async def load_context_from_db(self, group_id: int, context_length: int) -> list:
        context = []
        async with self.session_factory() as session:
            stmt = (
                select(Message)
                .where(Message.group_id == group_id)
                .order_by(desc(Message.send_time))
                .limit(context_length)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for row in reversed(rows):
                if row.user_id == 0:
                    context.append(
                        {
                            "role": "assistant",
                            "content": row.msg,
                        }
                    )
                else:
                    msg = await self.resolve_msg(session, row.msg)
                    context.append(
                        {
                            "role": "user",
                            "content": f"{row.user_nickname}(群名片：{row.user_card})说：{msg}",
                        }
                    )
        return context

    def get_dpsk_response_for_face(self, context_messages) -> int:
        persona = self.persona_face_template.render(recent_faces=self.recent_faces)
        # 你现在在一个群聊中，你根据以下的上下文准备回复一条消息，这条消息的内容是
        # \"\"\"
        # {msg_to_send}
        # \"\"\"
        # 你必须选择一张图片来辅助你的回复，这张图片必须与你的回复内容高度相关，并且能够增强你回复的表达效果。你可以选用的图片id及其描述如下：

        messages = [{"role": "system", "content": persona}]
        messages.extend(context_messages)

        response = get_dpsk_response(
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        try:
            image_id = json.loads(response).get("image_id")
            if image_id and image_id != 0 and image_id != 36 and image_id != 42:
                self.recent_faces.append(image_id)
                return image_id
            else:
                return 0
        except Exception:
            return 0
