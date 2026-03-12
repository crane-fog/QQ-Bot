import base64
import os
import re

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.PrintLog import Log
from utils.AITools import get_gemini_response
from utils.CQHelper import CQHelper
from utils.CQType import At, Reply


class TheresaImage(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaImage"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                AI 识图
                                usage: <回复图片消息>Timage (<文本>)
                            """
        self.init_status()

    @plugin_main(call_word=["[CQ:reply,"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        try:
            pattern = r"id=(-?\d+).*?\]Timage(.*)"
            match = re.search(pattern, event.message)
            if match:
                msg_id = match.group(1)
                prompt = match.group(2).strip()
                msg_str = (
                    self.api.messageService.get_msg(message_id=msg_id).get("data").get("message")
                )
                image_path = self.get_image_filename_from_msg(msg_str)
                if image_path:
                    response = await get_gemini_response(
                        messages=[
                            {
                                "role": "system",
                                "content": "尽可能简短、直接地回答用户的问题，不得输出markdown格式。",
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": encode_image(image_path)},
                                    },
                                ],
                            },
                        ]
                    )
                    reply_message = Reply(id=event.message_id) + response
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message=reply_message
                    )
                    Log.debug(
                        f"插件：{self.name}运行正确，成功回答用户{event.user_id}的问题{prompt}",
                        debug,
                    )
        except Exception as e:
            Log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}",
            )
        return

    def get_image_filename_from_msg(self, msg: str) -> str | None:
        result = CQHelper.load_cq(msg)
        if result is not None:
            return self.api.messageService.get_image(file_name=result.file).get("data").get("file")
        return None


def encode_image(image_path: str) -> str:
    extension = os.path.splitext(image_path)[1].lower().replace(".", "")
    mime_type = (
        f"image/{extension}" if extension in ["png", "jpeg", "jpg", "webp", "gif"] else "image/jpeg"
    )
    with open(image_path, "rb") as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"
