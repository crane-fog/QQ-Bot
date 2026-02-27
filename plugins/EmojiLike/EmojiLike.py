from random import randint

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler


class EmojiLike(Plugins):
    """
    插件名：EmojiLike \n
    插件类型：群聊插件 \n
    插件功能：对群聊中的消息随机贴表情\n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "EmojiLike"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                对群聊中的消息随机贴表情
                                usage: auto
                            """
        self.init_status()

    @plugin_main(check_call_word=False)
    async def main(self, event: GroupMessageEventHandler, debug):
        ignored_ids: list[int] = list(map(int, self.config.get("ignored_ids").split(",")))
        if event.user_id in ignored_ids:
            return

        frequency = int(self.config.getint("frequency"))

        if randint(0, 99) < frequency:
            emoji_id = randint(0, 350)
            self.api.groupService.set_msg_emoji_like(message_id=event.message_id, emoji_id=emoji_id)

        return
