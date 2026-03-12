from src.PrintLog import Log


class PrivateMessageEvent:
    def __init__(self, data):
        sender = data.get("sender")
        self.user_id = sender.get("user_id")
        self.nickname = sender.get("nickname")
        self.raw_message = data.get("raw_message")
        self.message = data.get("message")
        ...

    def post_event(self, debug: bool):
        log_message = self.message.replace("&amp;", "&")
        Log.debug(f"好友 {self.nickname}({self.user_id}) 私聊消息：{log_message}", debug)
