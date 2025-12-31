from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
import time
import requests
import os

log = Log()


class MoeGoe(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "MoeGoe"
        self.type = "Group"
        self.author = "just monika & Heai"
        self.introduction = """
                                艾玛语音合成
                                usage: ema zh/ja <文本>
                            """
        self.base_url = "http://localhost:5000/tts"  # API基础URL
        self.init_status()

    @plugin_main(call_word=["ema"])
    async def main(self, event: GroupMessageEventHandler, debug):
        msg_parts = event.message.split(" ", maxsplit=2)
        if len(msg_parts) < 3:
            self.api.groupService.send_group_msg(group_id=event.group_id, message="usage: ema zh/ja <文本>")
            return

        lang = msg_parts[1].upper()
        prompt = " ".join(msg_parts[2:])
        if lang not in ["ZH", "JA"]:
            self.api.groupService.send_group_msg(group_id=event.group_id, message="usage: ema zh/ja <文本>")
            return
        if len(prompt) > 100:
            self.api.groupService.send_group_msg(group_id=event.group_id, message="文本过长，请限制在100字以内")
            return

        filename = f"{os.path.dirname(os.path.abspath(__file__))}/temp/{int(time.time())}{event.user_id}.wav"
        self.get_api_response(prompt, filename, lang)
        self.api.groupService.send_group_record_msg(group_id=event.group_id, file_path=filename)

        return

    def get_api_response(self, prompt, filename, lang):
        url = self.base_url
        payload = {"text": prompt, "lang": lang, "speaker_id": 0}
        response = requests.post(url, json=payload)
        with open(filename, "wb") as f:
            f.write(response.content)
