import os
import time

import requests

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log

log = Log()


class MoeGoe(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "MoeGoe"
        self.type = "Group"
        self.author = "just monika & Heai"
        self.introduction = """
                                语音合成，樱羽艾玛/橘雪莉，中/日
                                usage: moegoe ema/sheri zh/ja <文本>
                            """
        self.init_status()

    @plugin_main(call_word=["moegoe"])
    async def main(self, event: GroupMessageEventHandler, debug):
        msg_parts = event.message.split(" ", maxsplit=3)
        if len(msg_parts) < 4:
            self.api.groupService.send_group_msg(
                group_id=event.group_id, message="usage: moegoe ema/sheri zh/ja <文本>"
            )
            return

        chara = msg_parts[1].upper()
        lang = msg_parts[2].upper()
        prompt = msg_parts[3]
        if (lang not in ["ZH", "JA"]) or (chara not in ["EMA", "SHERI"]):
            self.api.groupService.send_group_msg(
                group_id=event.group_id, message="usage: moegoe ema/sheri zh/ja <文本>"
            )
            return
        if len(prompt) > 200:
            self.api.groupService.send_group_msg(
                group_id=event.group_id, message="文本过长，请限制在200字以内"
            )
            return

        filename = f"{os.path.dirname(os.path.abspath(__file__))}/temp/{int(time.time())}{event.user_id}.wav"
        self.get_api_response(prompt, filename, lang, chara)
        self.api.groupService.send_group_record_msg(group_id=event.group_id, file_path=filename)

        return

    def get_api_response(self, prompt, filename, lang, chara):
        url = self.config.get("url")
        payload = {"text": prompt, "lang": lang, "chara": chara}
        response = requests.post(url, json=payload)
        with open(filename, "wb") as f:
            f.write(response.content)
