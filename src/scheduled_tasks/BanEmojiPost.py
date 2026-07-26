from configparser import SectionProxy

from src.Api import Api
from src.PrintLog import Log
from src.Scheduler import Scheduler


class BanEmojiPostTask:
    def __init__(self, api: Api, config: SectionProxy):
        self.api = api
        self.banned_tiny_ids: list[int] = Scheduler._parse_list(
            config.get("banned_tiny_ids", fallback="[]")
        )
        self.banned_emoji_ids: list[int] = Scheduler._parse_list(
            config.get("banned_emoji_ids", fallback="[]")
        )
        self.banned_group_ids: list[int] = Scheduler._parse_list(
            config.get("banned_group_ids", fallback="[]")
        )
        self.ban_duration: int = config.getint("ban_duration", fallback=600)

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
        try:
            result = self.api.groupService.get_group_recent_emoji_posters(group_id, emoji_id)
        except ConnectionError as e:
            Log.error(f"获取群 {group_id} 表情 {emoji_id} 的张贴者失败：{e}")
            return

        if result.get("status") != "ok":
            return

        posters: list[int] = result.get("data", {}).get("posters", [])
        violators = [uid for uid in posters if uid in self.banned_tiny_ids]

        for user_id in violators:
            Log.info(f"用户 {user_id} 在群 {group_id} 使用了禁止表情 {emoji_id}，禁言 {self.ban_duration}s")
            ban_result = self.api.groupService.set_group_ban(
                group_id=group_id, user_id=user_id, duration=self.ban_duration
            )
            if ban_result.get("status") != "ok":
                Log.error(f"禁言用户 {user_id} 在群 {group_id} 失败：{ban_result}")
