from Plugins import plugin_main, Plugins
from Event.EventHandler import GroupMessageEventHandler
import subprocess

class Theresac(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Theresac"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                执行命令，仅限Bot主人使用
                                usage: Theresac <命令>
                            """
        self.init_status()

    @plugin_main(check_group=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if not message.startswith("Theresac"):
            return

        if not event.user_id == 2046889405:
            return

        cmd = message.split(" ")[1:]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        msg = result.stdout
        self.api.GroupService.send_group_msg(self, group_id=event.group_id, message=f"{msg}")
        return
