from Logging.PrintLog import Log

log = Log()


class GroupRequestEvent:
    def __init__(self, data):
        self.data = data
        self.time: int = data.get("time")
        self.self_id: int = data.get("self_id")
        self.post_type: str = data.get("post_type")
        self.request_type: str = data.get("request_type")
        self.sub_type: str = data.get("sub_type")
        self.group_id: int = data.get("group_id")
        self.user_id: int = data.get("user_id")
        self.comment: str = data.get("comment")
        self.flag: str = data.get("flag")
        ...

    def post_event(self, debug):
        if self.sub_type == "add":
            c = self.comment.replace("\n", "  ")
            log.debug(f"群聊 {self.group_id} 收到入群申请，申请内容为{c}", debug)
