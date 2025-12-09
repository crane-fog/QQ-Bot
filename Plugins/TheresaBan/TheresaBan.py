import re
from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import Plugins
from CQMessage.CQType import At, Reply

log = Log()


class TheresaBan(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaBan"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                禁言
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
        command_list = message.split()
        if len(command_list) < 2:
            return

        for i in range(len(command_list)):
            command_list[i] = command_list[i].strip()

        if not command_list[0] == "Theresa" or not command_list[1] == "ban":
            return

        try:
            # 检查用户权限
            permissionList = [2046889405]
            if (event.user_id not in permissionList) and (event.role not in ["admin", "owner"]):
                return
            else:
                if len(command_list) != 4:
                    reply_message = f"{At(qq=event.user_id)} 格式错误"
                else:
                    match = re.search(r"qq=(\d+)", command_list[2])
                    if match:
                        qq = match.group(1)
                        ban_seconds = int(command_list[3])
                        reply_message = ""
                        self.api.groupService.set_group_ban(group_id=event.group_id, user_id=qq, duration=ban_seconds)
                    else:
                        reply_message = f"{At(qq=event.user_id)} 格式错误"

            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            log.debug(f"插件：{self.name}运行正确，ban用户", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(group_id=event.group_id, message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}")
