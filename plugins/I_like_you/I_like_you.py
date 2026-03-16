from pathlib import Path

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log


class I_like_you(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "I_like_you"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                I_like_you
                                usage: 我喜欢你，你喜欢我
                            """
        self.init_status()

    @plugin_main()
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "我喜欢你" in message:
            try:
                self.api.groupService.send_group_record_msg(
                    group_id=event.group_id,
                    file_path=Path(__file__).resolve().parent / "我喜欢你_你喜欢我.wav",
                )

            except Exception as e:
                Log.error(f"插件{self.name}运行时出错，{e}")
            else:
                Log.debug(f"成功向{event.group_id}发送我喜欢你", debug)

            return
        elif "我不喜欢你" in message:
            try:
                self.api.groupService.send_group_record_msg(
                    group_id=event.group_id,
                    file_path=Path(__file__).resolve().parent / "我不喜欢你.wav",
                )
            except Exception as e:
                Log.error(f"插件{self.name}运行时出错，{e}")
            else:
                Log.debug(f"成功向{event.group_id}发送我不喜欢你", debug)
