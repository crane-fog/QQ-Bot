import asyncio

from src.Api import Api
from src.PrintLog import Log


class BanEmojiPostTask:
    def __init__(self, api: Api, config: dict):
        self.api = api
        self.banned_tiny_ids: list[int] = config.get("banned_tiny_ids", [])
        self.banned_emoji_ids: list[int] = config.get("banned_emoji_ids", [])
        self.banned_group_ids: list[int] = config.get("banned_group_ids", [])
        self.ban_duration: int = config.get("ban_duration", 600)

    async def run(self) -> None:
        if not self.banned_tiny_ids:
            return

        group_ids = self._resolve_group_ids()

        for group_id in group_ids:
            emoji_ids = self._resolve_emoji_ids(group_id)
            for emoji_id in emoji_ids:
                await self._check_and_ban(group_id, emoji_id)

    def _resolve_group_ids(self) -> list[int]:
        if self.banned_group_ids:
            return self.banned_group_ids
        return []

    def _resolve_emoji_ids(self, group_id: int) -> list[int]:
        if self.banned_emoji_ids:
            return self.banned_emoji_ids
        return []

    async def _check_and_ban(self, group_id: int, emoji_id: int) -> None:
        msg_history_dict = self.api.groupService.get_group_msg_history(group_id)
        if msg_history_dict is None or msg_history_dict.get("status") != "ok":
            Log.error(f"获取群 {group_id} 聊天记录失败")
            return

        msg_history = msg_history_dict.get("data", {}).get("messages", [])
        if not msg_history:
            return

        async def _query_one(msg_id):
            try:
                return await self.api.asyncService.aget_msg_emoji_poster(msg_id, emoji_id)
            except Exception:
                return None

        results = await asyncio.gather(*[_query_one(msg["message_id"]) for msg in msg_history])

        poster_set: set[int] = set()
        for result in results:
            if result and result.get("status") == "ok":
                data = result.get("data")
                if data:
                    for emoji_likes in data.get("emoji_likes_list", []):
                        poster_set.add(emoji_likes["tiny_id"])

        violators = [uid for uid in poster_set if uid in self.banned_tiny_ids]

        for user_id in violators:
            Log.info(
                f"用户 {user_id} 在群 {group_id} 使用了禁止表情 {emoji_id}，禁言 {self.ban_duration}s"
            )
            ban_result = self.api.groupService.set_group_ban(
                group_id=group_id, user_id=user_id, duration=self.ban_duration
            )
            if ban_result.get("status") != "ok":
                Log.error(f"禁言用户 {user_id} 在群 {group_id} 失败：{ban_result}")
