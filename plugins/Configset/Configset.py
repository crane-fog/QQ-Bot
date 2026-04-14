import re

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log

log = Log()


class msghandle:
    def __init__(self, msg):
        self.message = msg

    def handle(self):
        self.message = self.message.replace("&#91;", "[").replace("&#93;", "]")
        return self.message


class Configset(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Configset"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                Configset,方便重启某一插件和更改插件的状态
                                usage: /open ,/close +[插件名]+ <群组号>,
                                当然只有root能这样做,
                                没写群组号默认是当前群组
                            """
        self.init_status()

    @plugin_main(call_word=["/open", "/close"], check_group=False)
    async def main(self, event: GroupMessageEventHandler, debug):
        try:
            if event.user_id == self.bot.owner_id:
                if event.message[0:5] == "/open":
                    msg = msghandle(event.message).handle()
                    plugin = re.findall(r"\[(.*?)\]", msg)
                    group_ids = re.findall(r"\<(.*?)\>", msg)
                    status_list = []
                    if group_ids == []:
                        group_ids.append(str(event.group_id))
                        if plugin == []:
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id, message="未选择插件"
                            )
                            return

                        else:
                            if len(plugin) > 1:
                                self.api.groupService.send_group_msg(
                                    group_id=event.group_id, message="选择插件过多,将会只处理第一个"
                                )
                            for group_id in group_ids:
                                status = self.bot.reload_plugins(
                                    plugin_name=plugin[0], group_id=group_id, oi=True
                                )
                                status_list.append((group_id, status))
                    else:
                        if plugin == []:
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id, message="未选择插件"
                            )
                            return
                        else:
                            if len(plugin) > 1:
                                self.api.groupService.send_group_msg(
                                    group_id=event.group_id, message="选择插件过多,将会只处理第一个"
                                )
                            for group_id in group_ids:
                                status = self.bot.reload_plugins(
                                    plugin_name=plugin[0], group_id=group_id, oi=True
                                )
                                status_list.append((group_id, status))

                    reply_message = "当前修正状态"
                    for statue in status_list:
                        reply_message += "\n"
                        if statue[1]:
                            reply_message = reply_message + statue[0] + " " + "成功"
                        else:
                            reply_message = reply_message + statue[0] + " " + "失败"

                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message=reply_message
                    )

                elif event.message[0:6] == "/close":
                    msg = msghandle(event.message).handle()
                    plugin = re.findall(r"\[(.*?)\]", msg)
                    group_ids = re.findall(r"\<(.*?)\>", msg)
                    status_list = []
                    if group_ids == []:
                        group_ids.append(str(event.group_id))
                        if plugin == []:
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id, message="未选择插件"
                            )
                            return

                        elif plugin[0] == "TheresaHelp":
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id,
                                message="我不建议将提示信息关闭，这样可能导致无法明确看到当前插件运行的状态",
                            )
                            return
                        elif plugin[0] == "Configset":
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id,
                                message="就算是你也不能将这个插件关掉，我不会允许",
                            )
                            return
                        else:
                            if len(plugin) > 1:
                                self.api.groupService.send_group_msg(
                                    group_id=event.group_id, message="选择插件过多,将会只处理第一个"
                                )
                            for group_id in group_ids:
                                status = self.bot.reload_plugins(
                                    plugin_name=plugin[0], group_id=group_id, oi=False
                                )
                                status_list.append((group_id, status))
                    reply_message = "当前修正状态"
                    for statue in status_list:
                        reply_message += "\n"
                        if statue[1]:
                            reply_message = reply_message + statue[0] + " " + "成功"
                        else:
                            reply_message = reply_message + statue[0] + " " + "失败"

                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message=reply_message
                    )

        except Exception as e:
            log.error(f"插件{self.name}运行时出错，{e}")
        else:
            log.debug("成功修正设置", debug)

        return
