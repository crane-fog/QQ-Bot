from sqlalchemy.dialects.postgresql import JSONB

from src.PrintLog import Log

log = Log()


class SendEvent:
    def __init__(self, data):
        self.message_type: str = data.get("message_type")
        self.user_id: int = data.get("user_id")
        self.message_id: int = data.get("message_id")
        sender = data.get("sender")
        self.nickname: str = sender.get("nickname")
        self.card: str = sender.get("card")
        if self.message_type == "group":
            self.role: str = sender.get("role")
            self.group_id: int = data.get("group_id")
            self.group_name: str = data.get("group_name")
        self.target_id: int = sender.get("target_id")
        self.post_type: str = data.get("post_type")
        self.message: str = data.get("message")
        self.raw_message: str = data.get("raw_message")
        self.all_data: JSONB = data
        ...

    def post_event(self, debug): ...
