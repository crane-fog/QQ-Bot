from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log

log = Log()


class Apingpong(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Apingpong"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                Apingpong
                                usage: ping
                            """
        self.init_status()

    @plugin_main()
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "ping" in message:
            reply_message = message
            try:
                self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            except Exception as e:
                log.debug(f"插件{self.name}运行时出错，作者{self.author}")
                log.debug(f"{e}")
            else:
                log.debug(f"成功向{event.group_id}发送内容", debug)

        return
