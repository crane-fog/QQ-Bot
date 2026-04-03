from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent


class TheresaCardBatch(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaCardBatch"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                批量群 Theresa card
                                usage: Theresa card (kick/debug) (strict) (unenter) (<小时数>)
                            """

        self.init_status()

    @plugin_main(call_word=["Theresa card"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        target_groups: list[int] = list(map(int, self.config.get("target_groups").split(",")))
        origin_group_id = event.group_id
        for plugin in self.bot.plugins_list:
            if plugin.name == "TheresaCard":
                for group_id in target_groups:
                    event.group_id = group_id
                    await plugin.main(event, debug)
                break
        event.group_id = origin_group_id
        return
