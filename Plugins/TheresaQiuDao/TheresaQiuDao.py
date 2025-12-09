from CQMessage.CQType import At, Face
from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Logging.PrintLog import Log
from Plugins import Plugins
import random

log = Log()


class TheresaQiuDao(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaQiuDao"  # 插件的名字（一定要和类的名字完全一致（主要是我能力有限，否则会报错））
        self.type = "Group"  # 插件的类型（这个插件是在哪种消息类型中触发的）
        self.author = "Heai"  # 插件开发作者（不用留真名，但是当插件报错的时候需要根据这个名字找到对应的人来修）
        self.introduction = """
                                根据高程期末考试成绩(x)随机成绩(√)发送对应的表情
                            """
        self.init_status()

    async def main(self, event: GroupMessageEvent, debug):
        enable = self.config.get("enable")
        if not enable:
            self.set_status("disable")
            return

        if self.status != "error":
            self.set_status("running")

        group_id = event.group_id
        effected_group_id: list = self.config.get("effected_group")
        if group_id not in effected_group_id:
            return

        message: str = event.message
        command_list = message.split(" ")
        len_of_command = len(command_list)
        if command_list[0] != self.bot.bot_name:
            return
        if len_of_command < 2:
            return

        command = self.config.get("command")
        if command_list[1] != command:
            return
        else:  # 正式进入插件运行部分
            group_id = event.group_id
            effected_group: list = self.config.get("effected_group")
            if group_id not in effected_group:
                self.api.groupService.send_group_msg(group_id=group_id, message=f"该功能未在此群{group_id}生效")
                return

            user_id = event.user_id

            score = random.randint(0, 4)
            log.debug(f"查询到的信息是：{score}", debug)


            self.api.groupService.send_group_msg(group_id=group_id, message=f"{At(qq=user_id)} {self.trans_score(score)}")


    @classmethod
    def trans_score(cls, score):
        if score == 0:
            return Face(id=63)  # 这个是花的id
        elif score == 1:
            return Face(id=112)  # 这个是刀的id
        elif score == 2:
            return f"{Face(id=112)}{Face(id=112)}"
        elif score == 3:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}"
        elif score == 4:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}"

