import subprocess

from plugins import Plugins, plugin_main
from src.event_handler import PrivateMessageEventHandler
from src.PrintLog import Log

log = Log()


class Areloader(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Areloader"
        self.type = "Private"
        self.author = "cojitaZ"
        self.introduction = """
                                Areloader
                                usage: 发送重启
                            """
        self.init_status()

    @plugin_main()
    async def main(self, event: PrivateMessageEventHandler, debug):
        if event.message == "re0":
            try:
                log.debug(f"收到来自{event.user_id}的重启指令,尝试重启中...")
                self.api.privateService.send_private_msg(user_id=event.user_id, message="重启中")
                subprocess.run("cls")
                exit()
            except Exception as e:
                log.debug(f"插件{self.name}运行时出错，作者{self.author}")
                log.debug(f"{e}")
            else:
                log.debug("成功重启", debug)

            return
