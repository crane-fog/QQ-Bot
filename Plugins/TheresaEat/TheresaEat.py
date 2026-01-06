from Plugins import plugin_main, Plugins
from Logging.PrintLog import Log
from random import choice

log = Log()


class TheresaEat(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaEat"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                今天吃什么
                                usage: Theresa eat 四平/嘉定
                            """
        self.init_status()

    @plugin_main(call_word=["Theresa eat"])
    async def main(self, event, debug):
        location_list = ["四平", "嘉定"]
        choices = {
            "四平": [
                "麦当劳",
                "KFC",
                "西北风",
                "萨莉亚",
                "海底捞",
                "必胜客",
                "滨寿司",
                "北苑面包房",
                "晨羊",
                "生滚牛肉米线（出停车场门往学校后面）",
                "柒月粉",
                "鱼籽村",
                "烤冷面（联广）",
                "缙云烧饼",
                "赣湘集",
                "糖葫芦（北门）",
                "肉蛋堡（北门）",
                "淀粉肠（彰武门外19:00左右刷新）",
                "鸡蛋灌饼（南门）",
                "coco（南门）",
                "煎饼果子（正门和彰武中间）",
                "肉夹馍（联广）",
            ],
            "嘉定": [
                "麦当劳",
                "KFC",
                "西北风",
                "萨莉亚",
                "海底捞",
                "必胜客",
                "老乡鸡",
                "赣湘小炒",
            ],
        }
        if event.message.strip() == "Theresa eat":
            msg = "usage: Theresa eat 四平/嘉定"
        elif event.message.strip().split(" ")[2] not in location_list:
            msg = "usage: Theresa eat 四平/嘉定"
        else:
            msg = choice(choices[event.message.strip().split(" ")[2]])

        self.api.GroupService.send_group_msg(group_id=event.group_id, message=msg)
        return
