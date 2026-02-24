from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log

log = Log()


class Apingpong(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Apingpong"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                Apingpong
                                usage: ping
                            """
        self.init_status()

    @plugin_main(call_word=["ping", "try"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        try:
            if "ping" in message:
                reply_message = message.replace("ping", "", 1)
                self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            elif "try" in message:
                reply_message = [
                    {
                        "type": "node",
                        "data": {
                            "content": [
                                {
                                    "type": "file",
                                    "data": {
                                        "file": r"C:\Users\cojita\Pictures\ENDFIELD\ENDFIELD_SHARE_1769696344.png"
                                    },
                                }
                            ]
                        },
                    }
                ]

                self.api.groupService.send_group_forward_msg(
                    group_id=event.group_id, forward_message=reply_message
                )
        except Exception as e:
            log.error(f"插件{self.name}运行时出错，{e}")
        else:
            log.debug(f"成功向{event.group_id}发送内容{reply_message}", debug)

        return
