from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent


class Configset(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Configset"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                便于重启某一插件和更改插件的状态，仅限所有者使用，不加群号默认为当前群
                                usage: /open / /close <插件名> (<群号，可多个，空格分隔>)
                            """
        self.init_status()

    @plugin_main(call_word=["/open", "/close"], check_group=False)
    async def main(self, event: GroupMessageEvent, debug):
        messages: list[str] = event.message.replace("&amp;", "&").split(" ")
        cmd: str = messages[0]
        plugin_name: str = messages[1].strip() if len(messages) > 1 else None
        group_ids: list[str] = (
            [gid.strip() for gid in messages[2:]] if len(messages) > 2 else [str(event.group_id)]
        )

        if event.user_id != self.bot.owner_id:
            return

        if plugin_name is None:
            reply_msg = "未选择插件"
        else:
            reply_msg = f"插件 {plugin_name} 重载"
            if cmd == "/open":
                status = self.bot.modify_plugin(
                    plugin_name=plugin_name, group_ids=group_ids, enable=True
                )
                reply_msg += "成功" if status else "失败"
            elif cmd == "/close":
                if plugin_name == "TheresaHelp":
                    reply_msg = "帮助插件不能关闭，将导致无法看到当前插件运行状态"
                elif plugin_name == "Configset":
                    reply_msg = "就算是你也不能将这个插件关掉，我不会允许"
                else:
                    status = self.bot.modify_plugin(
                        plugin_name=plugin_name, group_ids=group_ids, enable=False
                    )
                    reply_msg += "成功" if status else "失败"

        self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_msg)
        return
