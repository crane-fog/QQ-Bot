import asyncio
import json

import requests
from httpx import AsyncClient, Timeout

from utils.CQHelper import CQHelper
from utils.CQType import Forward


class Api:
    def __init__(self, server_address):
        self.bot_api_address = f"http://{server_address}/"

        # 传递Api类的实例引用
        self.botSelfInfo: Api.BotSelfInfo = self.BotSelfInfo(self)
        self.privateService: Api.PrivateService = self.PrivateService(self)
        self.groupService: Api.GroupService = self.GroupService(self)
        self.messageService: Api.MessageService = self.MessageService(self)
        self.asyncService: Api.AsyncService = self.AsyncService(self)

    class BotSelfInfo:
        def __init__(self, api_instance):
            self.api: Api = api_instance  # 保存对Api类实例的引用

        def get_login(self) -> str:
            """
            获取bot服务端是否在线
            :return: bot服务端返回的信息
            """
            response = requests.get(self.api.bot_api_address)
            return response.text

        def get_login_info(self) -> dict:
            """
            获取bot自身的登录信息
            :return: bot的QQ号和昵称
            """
            response = requests.get(self.api.bot_api_address + "get_login_info")
            return response.json()

    class PrivateService:
        def __init__(self, api_instance):
            self.api: Api = api_instance  # 保存对Api类实例的引用

        def send_private_msg(self, user_id: int, message: str) -> dict:
            params = {"user_id": user_id, "message": message}
            response = requests.post(self.api.bot_api_address + "send_private_msg", json=params)
            return response.json()

        def send_private_forward_msg(self, user_id: int, forward_message: list) -> dict:
            params = {"user_id": user_id, "messages": forward_message}
            response = requests.post(
                self.api.bot_api_address + "send_private_forward_msg", json=params
            )
            return response.json()

    class GroupService:
        def __init__(self, api_instance):
            self.api: Api = api_instance  # 保存对Api类实例的引用

        def get_group_msg_history(self, group_id: int, count: int = 50) -> dict:
            params = {"group_id": group_id, "count": count}
            response = requests.post(
                self.api.bot_api_address + "get_group_msg_history", json=params
            )
            return response.json()

        def get_msg_emoji_poster(self, msg_id: int, emoji_id: int) -> dict:
            params = {"message_id": msg_id, "emoji_id": emoji_id}
            response = requests.post(self.api.bot_api_address + "get_msg_emoji_post", json=params)
            return response.json()

        def get_group_recent_emoji_posters(self, group_id: int, emoji_id: int) -> dict:
            msg_history_dict = self.api.groupService.get_group_msg_history(group_id)
            if msg_history_dict is None or msg_history_dict["status"] != "ok":
                raise ConnectionError(
                    f"获取群聊天记录失败，group_id:{group_id}, status:{msg_history_dict.get('status')}"
                )
            msg_history = msg_history_dict.get("data").get("messages")
            msg_id_list = [msg.get("message_id") for msg in msg_history]

            async def _query_all():
                async def _query_one(msg_id):
                    return msg_id, await self.api.asyncService.aget_msg_emoji_poster(
                        msg_id, emoji_id
                    )

                return await asyncio.gather(*[_query_one(mid) for mid in msg_id_list])

            results = asyncio.run(_query_all())

            poster_set: set[int] = set()
            for _msg_id, result in results:
                if result and result.get("status") == "ok":
                    data = result.get("data")
                    if data:
                        for emoji_likes in data.get("emoji_likes_list", []):
                            poster_set.add(emoji_likes["tiny_id"])

            return {
                "status": "ok",
                "data": {
                    "posters": list(poster_set),
                },
            }

        def get_group_member_list(self, group_id: int, no_cache: bool = True) -> dict:
            params = {"group_id": group_id, "no_cache": no_cache}
            response = requests.post(
                self.api.bot_api_address + "get_group_member_list", json=params
            )
            return response.json()

        def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = True) -> dict:
            params = {"group_id": group_id, "user_id": user_id, "no_cache": no_cache}
            response = requests.post(
                self.api.bot_api_address + "get_group_member_info", json=params
            )
            return response.json()

        def send_group_msg(self, group_id: int, message: str | list[dict]) -> dict:
            params = {"group_id": group_id, "message": message}
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_record_msg(self, group_id: int, file_path: str) -> dict:
            params = {
                "group_id": group_id,
                "message": [{"type": "record", "data": {"file": f"file://{file_path}"}}],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_forward_msg(self, group_id: int, forward_message: list[dict]) -> dict:
            params = {"group_id": group_id, "messages": forward_message}
            response = requests.post(
                self.api.bot_api_address + "send_group_forward_msg", json=params
            )
            return response.json()

        def send_group_img(self, group_id: int, image_path: str) -> dict:
            params = {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": f"file://{image_path}"}}],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_msg_with_img(self, group_id: int, message: str, image_path: str) -> dict:
            params = {
                "group_id": group_id,
                "message": [
                    {"type": "text", "data": {"text": message}},
                    {"type": "image", "data": {"file": f"file://{image_path}"}},
                ],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_file(
            self, group_id: int, file_path: str, name: str, folder_id: str = None
        ) -> dict:
            if folder_id:
                params = json.dumps(
                    {
                        "group_id": group_id,
                        "file": f"file://{file_path}",
                        "name": name,
                        "folder_id": folder_id,
                    }
                )
            else:
                params = json.dumps(
                    {"group_id": group_id, "file": f"file://{file_path}", "name": name}
                )
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                self.api.bot_api_address + "upload_group_file",
                data=params,
                headers=headers,
            )
            return response.json()

        def set_group_ban(self, group_id: int, user_id: int, duration: int) -> dict:
            params = {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration,  # 禁言时长，单位为秒
            }
            response = requests.post(self.api.bot_api_address + "set_group_ban", json=params)
            return response.json()

        def set_group_kick(self, group_id: int, user_id: int) -> dict:
            params = {
                "group_id": group_id,
                "user_id": user_id,
            }
            response = requests.post(self.api.bot_api_address + "set_group_kick", json=params)
            return response.json()

        def delete_msg(self, message_id: int) -> dict:
            params = {
                "message_id": message_id,
            }
            response = requests.post(self.api.bot_api_address + "delete_msg", json=params)
            return response.json()

        def set_group_add_request(self, flag: str, approve: bool = True, reason: str = "") -> dict:
            params = {
                "flag": flag,
                "sub_type": "add",
                "approve": approve,
                "reason": reason,
            }
            response = requests.post(
                self.api.bot_api_address + "set_group_add_request", json=params
            )
            return response.json()

        def get_group_info(self, group_id: int) -> dict:
            params = {"group_id": group_id}
            response = requests.post(self.api.bot_api_address + "get_group_info", json=params)
            return response.json()

        def set_msg_emoji_like(self, message_id: int, emoji_id: int) -> dict:
            params = {"message_id": message_id, "emoji_id": emoji_id}
            response = requests.post(self.api.bot_api_address + "set_msg_emoji_like", json=params)
            return response.json()

        def send_group_poke(self, group_id: int, user_id: int) -> dict:
            params = {"group_id": group_id, "user_id": user_id}
            response = requests.post(self.api.bot_api_address + "group_poke", json=params)
            return response.json()

    class AsyncService:
        def __init__(self, api_instance):
            self.api: Api = api_instance
            self.timeout = Timeout(180)
            self._client: AsyncClient | None = None

        @property
        def client(self) -> AsyncClient:
            if self._client is None or self._client.is_closed:
                self._client = AsyncClient(timeout=self.timeout)
            return self._client

        async def aclose(self) -> None:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()

        async def send_group_file(
            self, group_id: int, file_path: str, name: str, folder_id: str = None
        ) -> dict:
            if folder_id:
                params = json.dumps(
                    {
                        "group_id": group_id,
                        "file": f"file://{file_path}",
                        "name": name,
                        "folder_id": folder_id,
                    }
                )
            else:
                params = json.dumps(
                    {"group_id": group_id, "file": f"file://{file_path}", "name": name}
                )
            headers = {"Content-Type": "application/json"}
            response = await self.client.post(
                self.api.bot_api_address + "upload_group_file",
                data=params,
                headers=headers,
            )

            return response.json()

        async def send_group_msg(self, group_id: int, message: str | list[dict]) -> dict:
            params = {"group_id": group_id, "message": message}
            response = await self.client.post(
                self.api.bot_api_address + "send_group_msg", json=params
            )
            return response.json()

        async def send_group_img(self, group_id: int, image_path: str) -> dict:
            params = {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": f"file://{image_path}"}}],
            }
            response = await self.client.post(
                self.api.bot_api_address + "send_group_msg", json=params
            )
            return response.json()

        async def send_group_forward_msg(self, group_id: int, forward_message: list) -> dict:
            params = {"group_id": group_id, "messages": forward_message}
            response = await self.client.post(
                self.api.bot_api_address + "send_group_forward_msg", json=params
            )
            return response.json()

        async def aget_msg_emoji_poster(self, msg_id: int, emoji_id: int) -> dict:
            params = {"message_id": msg_id, "emoji_id": emoji_id}
            response = await self.client.post(
                self.api.bot_api_address + "get_msg_emoji_post", json=params
            )
            return response.json()

        async def send_private_forward_msg(self, user_id: int, forward_message: list) -> dict:
            params = {"user_id": user_id, "messages": forward_message}
            response = await self.client.post(
                self.api.bot_api_address + "send_private_forward_msg", json=params
            )
            return response.json()

    class MessageService:
        def __init__(self, api_instance):
            self.api: Api = api_instance  # 保存对Api类实例的引用

        def get_msg(self, message_id: int) -> dict:
            params = {
                "message_id": message_id,
            }
            response = requests.post(self.api.bot_api_address + "get_msg", json=params)
            return response.json()

        def get_image(self, file_name: str) -> dict:
            params = {
                "file": file_name,
            }
            response = requests.post(self.api.bot_api_address + "get_image", json=params)
            return response.json()

        def get_group_file_url(self, group_id: int, file_id: str) -> dict:
            params = {"group_id": group_id, "file_id": file_id}
            response = requests.post(self.api.bot_api_address + "get_group_file_url", json=params)
            return response.json()

        def get_forward(self, message_id: int) -> list:
            """使用这个函数得到的结果可以直接由 send_forward_message 发出"""
            params = {"message_id": message_id}
            response = requests.post(self.api.bot_api_address + "get_forward_msg", json=params)
            origin_dict = response.json()

            messages = origin_dict.get("data", {}).get("messages", [])

            return_dict = Forward()
            for message in messages:
                msg = message.get("content", None)
                cq_obj = CQHelper.load_cq(msg)
                if cq_obj:
                    if cq_obj.cq_type == "forward":
                        msg = self.get_forward(cq_obj.id)
                return_dict.add_node(
                    type="msg",
                    uid=message.get("sender", {}).get("user_id", None),
                    sender_name=message.get("sender", {}).get("nickname", None),
                    msg=msg,
                )
            return return_dict.message
