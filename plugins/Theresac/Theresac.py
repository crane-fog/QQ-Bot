import subprocess

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler


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

    @plugin_main(check_group=False, call_word=["Theresac"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        cmd = " ".join(message.split(" ")[1:])
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        msg = result.stdout.replace("[CQ:", "\\CQ:").strip()
        self.api.GroupService.send_group_msg(self, group_id=event.group_id, message=f"{msg}")
        return
