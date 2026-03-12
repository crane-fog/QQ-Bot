import re

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.CQType import At


class TheresaBan(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaBan"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                禁言，仅限管理员使用
                                usage: Theresa ban <@> <禁言秒数>
                            """
        self.init_status()

    @plugin_main(call_word=["Theresa ban"])
    async def main(self, event: GroupMessageEventHandler, debug: bool):
        message = event.message
        command_list = message.split()
        if len(command_list) != 4:
            return

        for i in range(len(command_list)):
            command_list[i] = command_list[i].strip()

        try:
            # 检查用户权限
            if (
                (event.user_id != self.bot.owner_id)
                and (event.role not in ["admin", "owner"])
                and (event.user_id not in self.bot.assistant_list)
            ):
                return
            else:
                match = re.search(r"qq=(\d+)", command_list[2])
                if match:
                    qq = match.group(1)
                    ban_seconds = int(command_list[3].split(".")[0])
                    if qq == str(self.bot.owner_id):
                        reply_message = f"{At(qq=event.user_id)} 你想干嘛"
                        self.api.groupService.set_group_ban(
                            group_id=event.group_id, user_id=event.user_id, duration=ban_seconds
                        )
                    else:
                        reply_message = ""
                        self.api.groupService.set_group_ban(
                            group_id=event.group_id, user_id=qq, duration=ban_seconds
                        )
                else:
                    reply_message = f"{At(qq=event.user_id)} 格式错误，@不存在"

            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)

        except Exception as e:
            Log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}",
            )
