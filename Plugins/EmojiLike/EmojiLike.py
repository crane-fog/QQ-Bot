from random import randint
from Plugins import plugin_main, Plugins
from Event.EventHandler import GroupMessageEventHandler

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
        ignored_ids: list = self.config.get("ignored_ids")
        if event.user_id in ignored_ids:
            return

        frequency = int(self.config.get("frequency"))

        emoji_ids = [
            4, 5, 8, 9, 10, 12, 14, 16, 21, 23, 24, 25, 26, 27, 28, 29, 30, 
            32, 33, 34, 38, 39, 41, 42, 43, 49, 53, 60, 63, 66, 74, 75, 76, 
            78, 79, 85, 89, 96, 97, 98, 99, 100, 101, 102, 103, 104, 106, 
            109, 111, 116, 118, 120, 122, 123, 124, 125, 129, 144, 147, 171, 
            173, 174, 175, 176, 179, 180, 181, 182, 183, 201, 203, 212, 214, 
            219, 222, 227, 232, 240, 243, 246, 262, 264, 265, 266, 267, 268, 
            269, 270, 271, 272, 273, 277, 278, 281, 282, 284, 285, 287, 289, 
            290, 293, 294, 297, 298, 299, 305, 306, 307, 314, 315, 318, 319, 
            320, 322, 324, 326
        ]

        if (randint(0, 99) < frequency):
            emoji_id = emoji_ids[randint(0, len(emoji_ids) - 1)]
            self.api.GroupService.set_msg_emoji_like(self, message_id=event.message_id, emoji_id=emoji_id)

        return
