from Event.EventHandler.NoticeEventHandler import GroupPokeEvent
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
from CQMessage.CQType import At, Face
from random import randint
import time

log = Log()


class DontPoke(Plugins):
    """
    插件名：DontPoke \n
    插件类型：群聊戳一戳插件 \n
    插件功能：当有人戳一戳时，bot作出回复\n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "DontPoke"
        self.type = "Poke"
        self.author = "Heai"
        self.introduction = """
                                回复戳一戳
                                usage: 戳！
                            """
        self.user_cooldown = {}  # 用户冷却时间记录字典
        self.init_status()

    @plugin_main(check_call_word=False, check_group=True)
    async def main(self, event: GroupPokeEvent, debug):
        group_id = event.group_id
        target_id = event.target_id
        self_id = event.self_id
        if (target_id != self_id):
            return

        current_time = time.time()
        last_ask_time = self.user_cooldown.get(event.user_id, 0)
        if current_time - last_ask_time < int(self.config.get("cooldown_time")):
            # if event.role in ["admin", "owner"]:
            #     return
            # self.api.groupService.send_group_msg(group_id=group_id, message=f"{At(qq=event.user_id)} 还戳，挨ban了吧")
            # ban_time = self.config.get("ban_time")
            # ban_time_cuts = ban_time.split("-")
            # min_ban_time = ban_time_cuts[0].split(":")
            # max_ban_time = ban_time_cuts[1].split(":")
            # duration = randint(int(min_ban_time[0]) * 3600 + int(min_ban_time[1]) * 60 +
            #                 int(min_ban_time[2]), int(max_ban_time[0]) * 3600 + int(max_ban_time[1]) * 60 +
            #                 int(max_ban_time[2]))
            # self.api.groupService.set_group_ban(group_id=group_id, user_id=event.user_id, duration=duration)
            return

        user_id = event.user_id
        self.user_cooldown[user_id] = current_time

        if user_id == 2046889405:
            message = f"{At(qq=user_id)} {Face(id=319)}"
        else:
            message_list = [
                "戳什么戳！",
                "喵喵喵",
                "叔叔你别戳了我害怕",
                f"滚{Face(id=326)}",
                "你没活可以咬打火机",
                "呜——",
                "还戳，再戳ban你喵",
                "扑棱我干哈？",
                "把你种进土里，你重新长吧",
                "哼~",
                "哎呦疼——"
            ]
            message = f"{At(qq=user_id)} " + message_list[randint(0, len(message_list) - 1)]
        self.api.groupService.send_group_msg(group_id=group_id, message=message)

        repoke_frequency = self.config.get("repoke_frequency")
        if randint(0, 99) < int(repoke_frequency):
            self.api.groupService.send_group_poke(group_id=group_id, user_id=user_id)
        return
