from plugins import Plugins, plugin_main
from src.event_handler import PrivateMessageEventHandler
from src.PrintLog import Log

log = Log()


class Bpingpong(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Bpingpong"
        self.type = "Private"
        self.author = "cojitaZ"
        self.introduction = """
                                Apingpong
                                usage: ping
                            """
        self.init_status()

    @plugin_main()
    async def main(self, event: PrivateMessageEventHandler, debug):
        message = event.message
        if message == "ping":
            reply_message = message
            try:
                self.api.privateService.send_private_msg(
                    user_id=event.user_id, message=reply_message
                )
            except Exception as e:
                log.debug(f"插件{self.name}运行时出错，作者{self.author}")
                log.debug(f"{e}")
            else:
                log.debug(f"成功向{event.user_id}发送pong", debug)

        return
