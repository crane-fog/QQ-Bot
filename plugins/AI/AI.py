import re
import time

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.AITools import get_api_response
from utils.CQType import At

log = Log()


class AI(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "AI"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                无提示词 deepseek
                                usage: monika ask <提问内容>
                            """
        self.init_status()

        self.user_cooldown = {}  # 用户冷却时间记录字典
        self.cooldown_time = 1  # 冷却时间（秒）

    @plugin_main(call_word=["monika ask"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        # 检查是否是纯ask命令
        if message.strip() == "monika ask":
            self.api.groupService.send_group_msg(
                group_id=event.group_id, message="请输入你的问题哦"
            )
            log.debug(
                f"插件：{self.name}运行正确，用户{event.user_id}没有提出问题，已发送提示性回复",
                debug,
            )
            return

        # 冷却检查
        current_time = time.time()
        last_ask_time = self.user_cooldown.get(event.user_id, 0)

        if current_time - last_ask_time < self.cooldown_time:
            remaining = self.cooldown_time - int(current_time - last_ask_time)
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 提问太快啦，请等待{remaining}秒后再问哦~",
            )
            return

        try:
            # 更新用户最后提问时间
            self.user_cooldown[event.user_id] = current_time

            self.api.groupService.send_group_msg(group_id=event.group_id, message="小莫正在思考中~")

            # 提取问题内容
            # 删除CQ码
            question = re.sub(r"\[.*?\]", "", message[len(f"{self.bot.bot_name} ask") :]).strip()

            log.debug(
                f"插件：{self.name}运行正确，用户{event.user_id}提出问题{question}",
                debug,
            )

            # 获取大模型回复
            response = get_api_response([{"role": "user", "content": question}])

            # 发送回复到群聊
            reply_message = f"[CQ:reply,id={event.message_id}]{response}"
            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)

            log.debug(f"插件：{self.name}运行正确，成功回答用户{event.user_id}的问题", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}",
            )
