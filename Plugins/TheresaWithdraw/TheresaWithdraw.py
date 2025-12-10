from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
from CQMessage.CQType import At
import re

log = Log()

class TheresaWithdraw(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaWithdraw"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                防止防撤回的撤回，仅限群管理员使用
                                usage: <回复消息>Twithdraw
                            """
        self.init_status()

    @plugin_main(check_call_word=False)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        pattern = re.compile(r'(\[CQ:reply,id=.+\])(.+)')
        p = pattern.match(message)
        if p is None:
            return

        # 检查是否是ask命令
        if not "Twithdraw" in message:
            return

        try:
            # 检查用户权限
            permissionList = [2046889405]
            if (event.user_id not in permissionList) and (event.role not in ["admin", "owner"]):
                return
            else:
                target_message_id = message[13:message.find("]")]
                reply_message = ""
                self.api.groupService.delete_msg(message_id=target_message_id)
                self.api.groupService.delete_msg(message_id=event.message_id)

            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            log.debug(f"插件：{self.name}运行正确，撤回用户", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id, 
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}"
            )
