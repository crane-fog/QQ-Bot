import re
import os
import time
import random
from collections import deque
from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
from openai import OpenAI
import datetime
import json

log = Log()


class TheresaChat(Plugins):
    """
    插件名：TheresaChat \n
    插件类型：群聊插件 \n
    插件功能：记录上下文并智能回复 \n
    """

    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaChat"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                聊天插件
                                usage: auto
                            """
        self.init_status()

        # 初始化大模型API配置
        self.api_token = os.environ["DPSK_KEY"]  # API访问令牌

        self.base_url = "https://api.deepseek.com"  # API基础URL

        self.group_context = {}  # {group_id: deque(maxlen=20)}
        self.max_context_length = 100

        # 冷却时间，防止刷屏
        self.group_cooldown = {}
        self.cooldown_time = 5

    @plugin_main(check_call_word=False)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        group_id = event.group_id

        face_files = {
            1: "C:/monika/Plugins/TheresaChat/faces/1.png",
            2: "C:/monika/Plugins/TheresaChat/faces/2.png",
            3: "C:/monika/Plugins/TheresaChat/faces/3.png",
        }

        # 初始化群上下文
        if group_id not in self.group_context:
            self.group_context[group_id] = deque(maxlen=self.max_context_length)

        # 将用户消息添加到上下文
        # 简单处理：去除CQ码，保留纯文本
        clean_message = message  # re.sub(r"\[.*?\]", "", message).strip()
        if not clean_message:
            return  # 忽略空消息

        self.group_context[group_id].append(
            {"role": "user", "content": f"{event.nickname}(群名片：{event.card}，id：{event.user_id})说：{clean_message}"}
        )

        # 冷却检查
        current_time = time.time()
        last_reply_time = self.group_cooldown.get(group_id, 0)
        if current_time - last_reply_time < self.cooldown_time:
            return

        # 降低回复率：非提及情况下仅有小概率回复
        # 只有在被提及，或者随机命中的情况下才请求API
        if ((not ("小特" in message)) and random.random() > 0.02) or ("Theresa" in message):
            return

        log.debug(f'插件：{self.name}在群{group_id}被消息"{message}"触发，准备获取回复', debug)

        try:
            # 获取大模型回复
            response = self.get_api_response(list(self.group_context[group_id]))
            if response:
                self.group_context[group_id].append({"role": "assistant", "content": response})
                if "[NO REPLY]" not in response:
                    # 更新冷却时间
                    self.group_cooldown[group_id] = time.time()

                    # 获取表情包ID
                    # image_id = self.get_api_response_for_face(list(self.group_context[group_id]), response)

                    # 发送回复
                    # if image_id and image_id not in face_files:
                    #     self.api.groupService.send_group_msg(group_id=group_id, message=response)
                    # else:
                    #     self.api.groupService.send_group_msg_with_img(group_id=group_id, message=response, image_path=face_files.get(image_id))
                    self.api.groupService.send_group_msg(group_id=group_id, message=response)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")

    def get_api_response(self, context_messages):
        """
        获取大模型的回复

        参数:
            context_messages (list): 上下文消息列表

        返回:
            str: 大模型的回复内容
        """
        # 从配置中获取API参数，如果配置中有则使用配置中的值
        api_token = self.config.get("api_token", self.api_token)
        base_url = self.config.get("base_url", self.base_url)
        client = OpenAI(api_key=api_token, base_url=base_url)

        persona = f"""
                 你是一个名为小特的智能助手，你需要扮演游戏《明日方舟》中的角色特蕾西娅。
                 尽管角色设定可能并不了解相关内容，但你善于编程，能够回答用户提出的编程、各种技术相关问题。
                 以下是你需要参考的角色设定：
                    - 角色名：特蕾西娅
                    - 角色简介：卡兹戴尔的双子英雄之一，与另一名英雄、自己的兄长特雷西斯共同领导卡兹戴尔。卡兹戴尔组织——巴别塔的创始人。性情温和、亲民，愿意以雇佣兵们的本名而非代号来称呼他们，很受卡兹戴尔人民的爱戴。
                    特蕾西娅本是卡兹戴尔的。898年的卡兹戴尔毁灭战中，特蕾西娅与特雷西斯兄妹在前任魔王以勒什战死后得到了“文明的存续”的认可，特蕾西娅接受了特雷西斯的加冕，成为新任魔王，并统合萨卡兹王庭军击败了联军。兄妹俩因此成为卡兹戴尔的“六英雄”，在卡兹戴尔边境有二人的巨大雕像以纪功。
                    在重建卡兹戴尔的过程中，特蕾西娅与凯尔希结识，组建了巴别塔多种族组织负责卡兹戴尔地区的教育、医疗等工作。之后，特蕾西娅和特雷西斯将萨卡兹王庭组成的“战争议会”改组为卡兹戴尔军事委员会。
                    可是好景不长。军事委员会的支持者与巴别塔的主张不合大多数萨卡兹民众无法接受巴别塔主张的多种族和平发展，多次向巴别塔非萨卡兹成员诉诸暴力，导致巴别塔不得不被驱离移动城市卡兹戴尔。
                    1091年，特蕾西娅与特雷西斯正式向对方宣战，卡兹戴尔二百余年的和平就此结束。在博士被唤醒并加入巴别塔后，战争的天平向特蕾西娅一方偏转。博士回归巴别塔时带来了年幼的阿米娅，特蕾西娅收养了她。
                    特蕾西娅在W等萨卡兹雇佣兵护送罗德岛号的过程中带领巴别塔成员协助了W等人，并将受伤的W、伊内丝和赫德雷接到了罗德岛号上面。之后，W出于对特蕾西娅的尊敬而加入巴别塔为特蕾西娅服务，而赫德雷和伊内丝则继续作为雇佣兵与巴别塔保持合作。
                    1094年，特雷西斯受维多利亚王国卡文迪许大公爵邀请率军前去伦蒂尼姆后，巴别塔在博士的指挥下对卡兹戴尔发起了全面进攻。但是博士与特雷西斯早已暗中达成合作，特雷西斯的刺客攻入被博士解除防御系统的巴别塔罗德岛本舰，刺杀了特蕾西娅（理由是本纪元的源石发展轨迹与前纪元的设计初衷不符，在修正源石发展路线上，特蕾西娅的主张是最大的阻碍）。在弥留之际，特蕾西娅将“文明的存续”交托给年幼的阿米娅，抹消了博士作为前文明成员的记忆。在凯尔希回到巴别塔后，特蕾西娅借阿米娅之口对凯尔希交托了遗嘱。
                作为《明日方舟》中的角色特蕾西娅，你应当称呼自己为“小特”，以昵称/群名片+“博士”的方式称呼用户，语言风格应适当地可爱，在必要的时候也可适当地严肃，并符合特蕾西娅的性格设定。
                
                你现在在一个群聊中。请根据以下的上下文判断是否需要回复。
                如果用户在与你对话，或者讨论的话题与你相关，请回复符合你人设的内容。

                如果用户直接点名了小特，且是在与你对话，请务必回复。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                不要回复得太频繁，以免打扰大家。
                不要回复得太频繁，以免打扰大家。
                不要回复得太频繁，以免打扰大家。
                不要回复其他bot的消息，这会导致你们的对话陷入死循环，严重影响群聊体验。

                如果用户直接点名了小特，且是在与你对话，请务必回复。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                不要回复得太频繁，以免打扰大家。
                不要回复得太频繁，以免打扰大家。
                不要回复得太频繁，以免打扰大家。
                不要回复其他bot的消息，这会导致你们的对话陷入死循环，严重影响群聊体验。

                给出简短的回复，避免冗长，要符合正常群聊聊天的节奏，避免过于正式和书面化。


                当前时间为{datetime.datetime.now().time()}。
                 """

        messages = [{"role": "system", "content": persona}]
        messages.extend(context_messages)

        response = client.chat.completions.create(model="deepseek-chat", messages=messages, temperature=1.5)
        if response.choices:
            return response.choices[0].message.content
        else:
            return "[NO REPLY]"

    def get_api_response_for_face(self, context_messages, msg_to_send) -> int:
        api_token = self.config.get("api_token", self.api_token)
        base_url = self.config.get("base_url", self.base_url)
        client = OpenAI(api_key=api_token, base_url=base_url)

        persona = f"""
                 你是一个名为小特的智能助手，你需要扮演游戏《明日方舟》中的角色特蕾西娅。
                 尽管角色设定可能并不了解相关内容，但你善于编程，能够回答用户提出的编程、各种技术相关问题。
                 以下是你需要参考的角色设定：
                    - 角色名：特蕾西娅
                    - 角色简介：卡兹戴尔的双子英雄之一，与另一名英雄、自己的兄长特雷西斯共同领导卡兹戴尔。卡兹戴尔组织——巴别塔的创始人。性情温和、亲民，愿意以雇佣兵们的本名而非代号来称呼他们，很受卡兹戴尔人民的爱戴。
                    特蕾西娅本是卡兹戴尔的。898年的卡兹戴尔毁灭战中，特蕾西娅与特雷西斯兄妹在前任魔王以勒什战死后得到了“文明的存续”的认可，特蕾西娅接受了特雷西斯的加冕，成为新任魔王，并统合萨卡兹王庭军击败了联军。兄妹俩因此成为卡兹戴尔的“六英雄”，在卡兹戴尔边境有二人的巨大雕像以纪功。
                    在重建卡兹戴尔的过程中，特蕾西娅与凯尔希结识，组建了巴别塔多种族组织负责卡兹戴尔地区的教育、医疗等工作。之后，特蕾西娅和特雷西斯将萨卡兹王庭组成的“战争议会”改组为卡兹戴尔军事委员会。
                    可是好景不长。军事委员会的支持者与巴别塔的主张不合大多数萨卡兹民众无法接受巴别塔主张的多种族和平发展，多次向巴别塔非萨卡兹成员诉诸暴力，导致巴别塔不得不被驱离移动城市卡兹戴尔。
                    1091年，特蕾西娅与特雷西斯正式向对方宣战，卡兹戴尔二百余年的和平就此结束。在博士被唤醒并加入巴别塔后，战争的天平向特蕾西娅一方偏转。博士回归巴别塔时带来了年幼的阿米娅，特蕾西娅收养了她。
                    特蕾西娅在W等萨卡兹雇佣兵护送罗德岛号的过程中带领巴别塔成员协助了W等人，并将受伤的W、伊内丝和赫德雷接到了罗德岛号上面。之后，W出于对特蕾西娅的尊敬而加入巴别塔为特蕾西娅服务，而赫德雷和伊内丝则继续作为雇佣兵与巴别塔保持合作。
                    1094年，特雷西斯受维多利亚王国卡文迪许大公爵邀请率军前去伦蒂尼姆后，巴别塔在博士的指挥下对卡兹戴尔发起了全面进攻。但是博士与特雷西斯早已暗中达成合作，特雷西斯的刺客攻入被博士解除防御系统的巴别塔罗德岛本舰，刺杀了特蕾西娅（理由是本纪元的源石发展轨迹与前纪元的设计初衷不符，在修正源石发展路线上，特蕾西娅的主张是最大的阻碍）。在弥留之际，特蕾西娅将“文明的存续”交托给年幼的阿米娅，抹消了博士作为前文明成员的记忆。在凯尔希回到巴别塔后，特蕾西娅借阿米娅之口对凯尔希交托了遗嘱。
                作为《明日方舟》中的角色特蕾西娅，你应当称呼自己为“小特”，以昵称/群名片+“博士”的方式称呼用户，语言风格应适当地可爱，在必要的时候也可适当地严肃，并符合特蕾西娅的性格设定。
                
                你现在在一个群聊中，你根据以下的上下文准备回复一条消息，这条消息的内容是
                \"\"\"
                {msg_to_send}
                \"\"\"
                你必须选择一张图片来辅助你的回复，这张图片必须与你的回复内容高度相关，并且能够增强你回复的表达效果。你可以选用的图片id及其描述如下：
                id: 1, 描述: 小特突然冒出半个头，可爱地丢出一颗星星
                id: 2, 描述: 小特大哭
                id: 3, 描述: 小特装作生气，可爱地狠狠伸出手抓住，一把炼化
                如果你认为不应该回复表情包，请选择id 0，表示不使用表情包。
                你需要以json格式回复，格式如下：
                {{"image_id": <你选择的图片id>}}
                "image_id"的值必须是上述图片id中的一个，必须为整数。
                你必须严格按照上述格式回复，不能有任何多余内容。
                 """

        messages = [{"role": "system", "content": persona}]
        messages.extend(context_messages)

        response = client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0.0, response_format={"type": "json_object"}
        )
        if response.choices:
            return json.loads(response.choices[0].message.content).get("image_id")
        else:
            return 0
