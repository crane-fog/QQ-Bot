from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log


class TheresaWithdraw(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaWithdraw"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                防止防撤回的撤回，仅限管理员使用
                                usage: <回复消息>Twithdraw
                            """
        self.init_status()

    @plugin_main(call_word=["[CQ:reply,"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        if "Twithdraw" not in message:
            return

        # 检查用户权限
        if (
            (event.user_id != self.bot.owner_id)
            and (event.role not in ["admin", "owner"])
            and (event.user_id not in self.bot.assistant_list)
        ):
            return
        else:
            target_message_id = message[13 : message.find("]")]
            reply_message = ""
            self.api.groupService.delete_msg(message_id=target_message_id)
            self.api.groupService.delete_msg(message_id=event.message_id)

        self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
        Log.debug(f"插件：{self.name}运行正确，撤回用户", debug)
