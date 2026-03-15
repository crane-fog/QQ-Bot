import json

import requests


class Api:
    def __init__(self, server_address):
        self.bot_api_address = f"http://{server_address}/"

        # 传递Api类的实例引用
        self.botSelfInfo: Api.BotSelfInfo = self.BotSelfInfo(self)
        self.privateService: Api.PrivateService = self.PrivateService(self)
        self.groupService: Api.GroupService = self.GroupService(self)
        self.messageService: Api.MessageService = self.MessageService(self)

    class BotSelfInfo:
        def __init__(self, api_instance):
            self.api = api_instance  # 保存对Api类实例的引用

        def get_login(self):
            """
            获取bot服务端是否在线
            :return: bot服务端返回的信息
            """
            response = requests.get(self.api.bot_api_address)
            return response.text

        def get_login_info(self):
            """
            获取bot自身的登录信息
            :return: bot的QQ号和昵称
            """
            response = requests.get(self.api.bot_api_address + "get_login_info")
            return response.json()

    class PrivateService:
        def __init__(self, api_instance):
            self.api = api_instance  # 保存对Api类实例的引用

        def send_private_msg(self, user_id, message):
            params = {"user_id": user_id, "message": message}
            response = requests.post(self.api.bot_api_address + "send_private_msg", json=params)
            return response.json()

        def send_private_forward_msg(self, user_id, forward_message: list):
            params = {"user_id": user_id, "messages": forward_message}
            response = requests.post(
                self.api.bot_api_address + "send_private_forward_msg", json=params
            )
            return response.json()

    class GroupService:
        def __init__(self, api_instance):
            self.api = api_instance  # 保存对Api类实例的引用

        def get_group_member_list(self, group_id, no_cache=True):
            params = {"group_id": group_id, "no_cache": no_cache}
            response = requests.post(
                self.api.bot_api_address + "get_group_member_list", json=params
            )
            return response.json()

        def get_group_member_info(self, group_id, user_id, no_cache=True):
            params = {"group_id": group_id, "user_id": user_id, "no_cache": no_cache}
            response = requests.post(
                self.api.bot_api_address + "get_group_member_info", json=params
            )
            return response.json()

        def send_group_msg(self, group_id, message):
            params = {"group_id": group_id, "message": message}
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_record_msg(self, group_id, file_path):
            params = {
                "group_id": group_id,
                "message": [{"type": "record", "data": {"file": f"file://{file_path}"}}],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_forward_msg(self, group_id, forward_message: list):
            params = {"group_id": group_id, "messages": forward_message}
            response = requests.post(
                self.api.bot_api_address + "send_group_forward_msg", json=params
            )
            return response.json()

        def send_group_img(self, group_id, image_path):
            params = {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": f"file://{image_path}"}}],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_msg_with_img(self, group_id, message, image_path):
            params = {
                "group_id": group_id,
                "message": [
                    {"type": "text", "data": {"text": message}},
                    {"type": "image", "data": {"file": f"file://{image_path}"}},
                ],
            }
            response = requests.post(self.api.bot_api_address + "send_group_msg", json=params)
            return response.json()

        def send_group_file(self, group_id, file_path, name, folder_id=None):
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

        def set_group_ban(self, group_id, user_id, duration):
            params = {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration,  # 禁言时长，单位为秒
            }
            response = requests.post(self.api.bot_api_address + "set_group_ban", json=params)
            return response.json()

        def set_group_kick(self, group_id, user_id):
            params = {
                "group_id": group_id,
                "user_id": user_id,
            }
            response = requests.post(self.api.bot_api_address + "set_group_kick", json=params)
            return response.json()

        def delete_msg(self, message_id):
            params = {
                "message_id": message_id,
            }
            response = requests.post(self.api.bot_api_address + "delete_msg", json=params)
            return response.json()

        def set_group_add_request(self, flag, approve="true", reason=""):
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

        def get_group_info(self, group_id):
            params = {"group_id": group_id}
            response = requests.post(self.api.bot_api_address + "get_group_info", json=params)
            return response.json()

        def set_msg_emoji_like(self, message_id, emoji_id):
            params = {"message_id": message_id, "emoji_id": emoji_id}
            response = requests.post(self.api.bot_api_address + "set_msg_emoji_like", json=params)
            return response.json()

        def send_group_poke(self, group_id, user_id):
            params = {"group_id": group_id, "user_id": user_id}
            response = requests.post(self.api.bot_api_address + "group_poke", json=params)
            return response.json()

    class MessageService:
        def __init__(self, api_instance):
            self.api = api_instance  # 保存对Api类实例的引用

        def get_msg(self, message_id):
            params = {
                "message_id": message_id,
            }
            response = requests.post(self.api.bot_api_address + "get_msg", json=params)
            return response.json()

        def get_image(self, file_name):
            params = {
                "file": file_name,
            }
            response = requests.post(self.api.bot_api_address + "get_image", json=params)
            return response.json()

        def get_forward(self, message_id):
            """使用这个函数得到的结果可以直接由send_forward_message发出,确保完全一致性"""
            params = {"message_id": str(message_id)}
            response = requests.post(self.api.bot_api_address + "get_forward_msg", json=params)
            origin_dict = response.json()
            from utils.CQHelper import CQHelper
            from utils.CQType import Forward

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
