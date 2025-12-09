from Plugins import Plugins
from Event.EventHandler import GroupMessageEventHandler
import subprocess

class Theresac(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Theresac"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                cmd
                            """
        self.init_status()

    async def main(self, event: GroupMessageEventHandler, debug):
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

        message = event.message
        if not message.startswith("Theresac"):
            return

        if not event.user_id == 2046889405:
            return

        cmd = message.split(" ")[1:]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        msg = result.stdout
        self.api.GroupService.send_group_msg(self, group_id=group_id, message=f"{msg}")
        return