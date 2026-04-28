from asyncio import create_subprocess_shell
from html import unescape
from subprocess import PIPE

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent


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
    async def main(self, event: GroupMessageEvent, debug: bool):
        message = unescape(event.message)

        if not event.user_id == self.bot.owner_id:
            self.api.groupService.send_group_msg(group_id=event.group_id, message="无权限")
            return

        cmd = " ".join(message.split(" ")[1:])
        result = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = await result.communicate()

        msg = ""

        if stdout:
            msg += f"stdout:\n{stdout.decode(errors='ignore')}\n"
            if stderr:
                msg += "------\n"
        if stderr:
            msg += f"stderr:\n{stderr.decode(errors='ignore')}\n"

        msg = msg.replace("[CQ:", "\\CQ:").strip()

        self.api.groupService.send_group_msg(group_id=event.group_id, message=msg)
        return
