import re
import os
import time
from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
from CQMessage.CQType import At
from openai import OpenAI

log = Log()


class AI(Plugins):
    """
    插件名：AI \n
    插件类型：群聊插件 \n
    插件功能：用户可以通过"<bot name> ask <问题内容>"的形式向远程大模型提问，支持文本提问\n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "AI"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                deepseek
                                usage: monika ask <提问内容>
                            """
        self.init_status()

        # 初始化大模型API配置
        self.api_token = os.environ["DPSK_KEY"]  # API访问令牌
        self.base_url = "https://api.deepseek.com"  # API基础URL

        self.user_cooldown = {}  # 用户冷却时间记录字典
        self.cooldown_time = 1  # 冷却时间（秒）

    @plugin_main(check_group=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        # 检查是否是纯ask命令
        if message.strip() == f"monika ask":
            self.api.groupService.send_group_msg(group_id=event.group_id, message="请输入你的问题哦")
            log.debug(f"插件：{self.name}运行正确，用户{event.user_id}没有提出问题，已发送提示性回复", debug)
            return

        # 检查是否是ask命令
        if not message.startswith(f"monika ask"):
            return

        # 冷却检查
        current_time = time.time()
        last_ask_time = self.user_cooldown.get(event.user_id, 0)

        if current_time - last_ask_time < self.cooldown_time:
            remaining = self.cooldown_time - int(current_time - last_ask_time)
            self.api.groupService.send_group_msg(
                group_id=event.group_id, message=f"{At(qq=event.user_id)} 提问太快啦，请等待{remaining}秒后再问哦~"
            )
            return

        try:
            # 更新用户最后提问时间
            self.user_cooldown[event.user_id] = current_time

            self.api.groupService.send_group_msg(group_id=event.group_id, message="小莫正在思考中~")

            # 提取问题内容
            # 删除CQ码
            question = re.sub(r"\[.*?\]", "", message[len(f"{self.bot.bot_name} ask") :]).strip()

            log.debug(f"插件：{self.name}运行正确，用户{event.user_id}提出问题{question}", debug)

            # 获取大模型回复
            response = self.get_api_response(question)

            # 发送回复到群聊
            reply_message = f"[CQ:reply,id={event.message_id}]{response}"
            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)

            log.debug(f"插件：{self.name}运行正确，成功回答用户{event.user_id}的问题", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(group_id=event.group_id, message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}")

    def get_api_response(self, prompt):
        """
        获取大模型的回复

        参数:
            prompt (str): 用户输入的提示词

        返回:
            str: 大模型的回复内容
        """
        # 从配置中获取API参数，如果配置中有则使用配置中的值
        api_token = self.config.get("api_token", self.api_token)
        base_url = self.config.get("base_url", self.base_url)
        client = OpenAI(api_key=api_token, base_url=base_url)

        response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=1.5)
        if response.choices:
            return response.choices[0].message.content
        else:
            return "未收到有效回复"
