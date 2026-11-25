import os
from asyncio import Lock
from contextlib import nullcontext

from google.genai import types
from google.genai.errors import APIError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.agent.AIService import ai
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.Models import Message
from src.PrintLog import Log
from utils.AIUtils import encode_image
from utils.CQHelper import CQHelper
from utils.CQType import Reply


class GenImage(Plugins):
    def __init__(self, bot):
        super().__init__(bot)
        self.name = "GenImage"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                文生图、图生图\n参考图需以回复消息的形式引用
                                usage: GenImage <生图描述>
                            """
        self.init_status()
        self.lock = Lock()
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    @plugin_main(call_word=["[CQ:reply,", "GenImage"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        prompt: types.ContentListUnionDict = [{"role": "user", "parts": []}]

        if event.message.startswith("[CQ:reply,"):
            if "GenImage" not in event.message:
                return

            reply_id = int(event.message.split("]")[0].split("[CQ:reply,id=")[1])
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Message).where(Message.msg_id == reply_id).order_by(desc(Message.id))
                )
                row = result.scalars().first()
                replied_msg = row.msg if row is not None else ""
            cqs = CQHelper.loads_cq(replied_msg)
            for cq in cqs:
                if cq.cq_type == "image":
                    data, mime_type = encode_image(cq.path, get_byte=True)
                    prompt[0]["parts"].append(
                        {"inline_data": {"mime_type": mime_type, "data": data}}
                    )
        text = event.message.split("GenImage", 1)[1].strip()
        Log.debug(f"插件：{self.name}在群{event.group_id}触发，prompt: {text}", debug)
        prompt[0]["parts"].append({"text": text})

        try:
            lock_ctx = self.lock if self.config.get("lock_enable", True) else nullcontext()
            async with lock_ctx:
                resp = await ai.generate_image(
                    profile_name="image_gen",
                    messages=prompt,
                    system_prompt="在没有参考图地生成特定形象的角色图片前，你应进行网络搜索来确认形象",
                )
        except APIError as e:
            Log.error(f"插件：{self.name}在群{event.group_id}生成图片失败: {e}")
            if e.code == 429:
                msg = "上游 API 流控，请稍后重试"
            else:
                msg = f"{e}"
            await api.asyncGroupService.send_group_msg(
                group_id=event.group_id,
                message=f"{Reply(id=event.message_id)}生成图片失败: {msg}",
            )
            return

        if resp is None:
            Log.error(f"插件：{self.name}在群{event.group_id}生成图片失败: 未收到有效响应")
            await api.asyncGroupService.send_group_msg(
                group_id=event.group_id,
                message=f"{Reply(id=event.message_id)}生成图片失败: 未收到有效响应，上游拦截",
            )
            return

        path = f"{os.path.dirname(os.path.abspath(__file__))}/temp/{event.user_id}_{event.message_id}.{resp.mime_type.split('/')[-1]}"
        with open(path, "wb") as f:
            f.write(resp.data)
        await api.asyncGroupService.send_group_msg(
            group_id=event.group_id, message=f"{Reply(id=event.message_id)}{resp.text}"
        )
        await api.asyncGroupService.send_group_img(group_id=event.group_id, image_path=path)
        return
