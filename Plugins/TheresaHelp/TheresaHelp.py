from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins

log = Log()


class TheresaHelp(Plugins):
    """
    插件名：TheresaHelp \n
    插件类型：群聊插件 \n
    插件功能：读取当前群聊启用了的插件，并将其self.introduction输出\n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaHelp"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                查看当前群聊启用的插件及说明
                                usage: Theresa help
                            """
        self.init_status()

    @plugin_main(check_group=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        if message.strip() != "Theresa help":
            return

        group_id = event.group_id
        response = "当前群聊启用的插件如下：\n"

        # 遍历所有已加载的插件
        for plugin in self.bot.plugins_list:
            # 获取插件启用的群组列表
            effected_groups: list = plugin.config.get("effected_group")

            # 如果当前群组在插件的启用列表中
            if group_id in effected_groups:
                # 获取插件介绍，去除首尾空白
                intro = plugin.introduction.strip() if plugin.introduction else "暂无介绍"
                # 格式化输出，去除多余的缩进
                intro_lines = [line.strip() for line in intro.split("\n") if line.strip()]
                formatted_intro = "\n".join(intro_lines)

                response += f"[{plugin.name}]\n{formatted_intro}\n\n"

        # 发送消息
        self.api.groupService.send_group_msg(group_id=group_id, message=response.strip())
        log.debug(f"插件：{self.name}运行正确，已发送帮助信息", debug)
