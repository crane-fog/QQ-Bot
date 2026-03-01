import datetime
import os
import re
import time

from jinja2 import Template

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.AITools import get_gemini_response
from utils.CQType import At, Reply

log = Log()


class TheresaGoodMorning(Plugins):
    """
    插件名：TheresaGoodMorning \n
    插件类型：群聊插件 \n
    插件功能：AI版本早安晚安\n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaGoodMorning"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                早安/晚安小特
                                usage: Theresa 早安/晚安
                            """
        self.init_status()

        self.user_cooldown = {}  # 用户冷却时间记录字典
        self.cooldown_time = 1  # 冷却时间（秒）

        with open(os.path.join(os.path.dirname(__file__), "persona.j2"), encoding="utf-8") as f:
            self.persona_template = Template(f.read())

    @plugin_main(call_word=["Theresa 晚安", "Theresa 早安"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        # 冷却检查
        current_time = time.time()
        last_ask_time = self.user_cooldown.get(event.user_id, 0)

        if current_time - last_ask_time < self.cooldown_time:
            remaining = self.cooldown_time - int(current_time - last_ask_time)
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 提问太快啦，请等待{remaining}秒后再问哦~",
            )
            return

        try:
            # 更新用户最后提问时间
            self.user_cooldown[event.user_id] = current_time

            # 提取问题内容
            # 删除CQ码
            question = re.sub(r"\[.*?\]", "", message[len("Theresa ") :]).strip()

            log.debug(
                f"插件：{self.name}运行正确，用户{event.user_id}提出问题{question}",
                debug,
            )

            persona = self.persona_template.render(
                current_time=datetime.datetime.now().time(),
                group_name=event.group_name,
            )

            question = f"提问者：{event.nickname}(群名片：{event.card})\n问题内容：{question}"

            # 获取大模型回复
            response = get_gemini_response(
                [
                    {"role": "system", "content": persona},
                    {"role": "user", "content": question},
                ]
            )

            # 发送回复到群聊
            reply_message = Reply(id=event.message_id) + response
            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            if message.startswith("Theresa 晚安"):
                self.api.groupService.set_group_ban(
                    group_id=event.group_id,
                    user_id=event.user_id,
                    duration=self.get_seconds_to_next_6am(),
                )

            log.debug(f"插件：{self.name}运行正确，成功回答用户{event.user_id}的问题", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}",
            )

    @classmethod
    def get_seconds_to_next_6am(cls):
        # 如果未提供当前时间，则使用当前系统时间
        current_time = datetime.datetime.now()
        current_time_only = current_time.time()  # 获取时间部分

        # 创建时间对象：午夜 00:00:00 和早上 06:00:00
        midnight = datetime.time(0, 0, 0)
        six_am = datetime.time(6, 0, 0)

        today = current_time.date()  # 获取当前日期

        # 判断当前时间是否在 0:00 AM 到 6:00 AM 之间
        if midnight <= current_time_only < six_am:
            target_6am = datetime.datetime.combine(today, six_am)
        else:
            next_day = today + datetime.timedelta(days=1)
            target_6am = datetime.datetime.combine(next_day, six_am)

        # 返回当前时间到目标 6:00 AM 的秒数差
        return int((target_6am - current_time).total_seconds())
