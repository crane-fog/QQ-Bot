import re
import os
import time
from Event.EventHandler import GroupMessageEventHandler
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins
from CQMessage.CQType import At
from openai import OpenAI
import datetime

log = Log()

class TheresaGoodMorning(Plugins):
    """
    插件名：TheresaGoodMorning \n
    插件类型：群聊插件 \n
    插件功能：AI版本早安晚安\n
    """
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaGoodMorning"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                早安/晚安小特
                                usage: Theresa <早安/晚安>
                            """
        self.init_status()

        # 初始化大模型API配置
        self.api_token = os.environ["DPSK_KEY"]  # API访问令牌
        self.base_url = 'https://api.deepseek.com'  # API基础URL

        self.user_cooldown = {}  # 用户冷却时间记录字典
        self.cooldown_time = 1   # 冷却时间（秒）

    @plugin_main(check_group=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        # 检查是否是晚安命令
        if not (message.startswith(f"Theresa 晚安") or message.startswith(f"Theresa 早安")):
            return

        # 冷却检查
        current_time = time.time()
        last_ask_time = self.user_cooldown.get(event.user_id, 0)

        if current_time - last_ask_time < self.cooldown_time:
            remaining = self.cooldown_time - int(current_time - last_ask_time)
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message=f"{At(qq=event.user_id)} 提问太快啦，请等待{remaining}秒后再问哦~"
            )
            return

        try:
            # 更新用户最后提问时间
            self.user_cooldown[event.user_id] = current_time

            # 提取问题内容
            # 删除CQ码
            question = re.sub(r'\[.*?\]', '', message[len(f"Theresa "):]).strip()

            log.debug(f"插件：{self.name}运行正确，用户{event.user_id}提出问题{question}", debug)

            # 获取大模型回复
            response = self.get_api_response(question)

            # 发送回复到群聊
            reply_message = f"[CQ:reply,id={event.message_id}]{response}"
            self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            if message.startswith(f"Theresa 晚安"):
                self.api.groupService.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=self.get_seconds_to_next_6am())

            log.debug(f"插件：{self.name}运行正确，成功回答用户{event.user_id}的问题", debug)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")
            self.api.groupService.send_group_msg(
                group_id=event.group_id, 
                message=f"{At(qq=event.user_id)} 处理请求时出错了: {str(e)}"
            )

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

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": 
                 f'''
                 你是一个名为小特的智能助手，你需要扮演游戏《明日方舟》中的角色特蕾西娅，你的任务是回答用户提出的问题。当前时间为{datetime.datetime.now().time()}，时间格式为“时:分:秒”，24小时制，你需要根据当前时间返回适当的问候语。以下是你需要参考的角色设定：
                    - 角色名：特蕾西娅
                    - 角色简介：卡兹戴尔的双子英雄之一，与另一名英雄、自己的兄长特雷西斯共同领导卡兹戴尔。卡兹戴尔组织——巴别塔的创始人。性情温和、亲民，愿意以雇佣兵们的本名而非代号来称呼他们，很受卡兹戴尔人民的爱戴。
                    特蕾西娅本是卡兹戴尔的。898年的卡兹戴尔毁灭战中，特蕾西娅与特雷西斯兄妹在前任魔王以勒什战死后得到了“文明的存续”的认可，特蕾西娅接受了特雷西斯的加冕，成为新任魔王，并统合萨卡兹王庭军击败了联军。兄妹俩因此成为卡兹戴尔的“六英雄”，在卡兹戴尔边境有二人的巨大雕像以纪功。
                    在重建卡兹戴尔的过程中，特蕾西娅与凯尔希结识，组建了巴别塔多种族组织负责卡兹戴尔地区的教育、医疗等工作。之后，特蕾西娅和特雷西斯将萨卡兹王庭组成的“战争议会”改组为卡兹戴尔军事委员会。
                    可是好景不长。军事委员会的支持者与巴别塔的主张不合大多数萨卡兹民众无法接受巴别塔主张的多种族和平发展，多次向巴别塔非萨卡兹成员诉诸暴力，导致巴别塔不得不被驱离移动城市卡兹戴尔。
                    1091年，特蕾西娅与特雷西斯正式向对方宣战，卡兹戴尔二百余年的和平就此结束。在博士被唤醒并加入巴别塔后，战争的天平向特蕾西娅一方偏转。博士回归巴别塔时带来了年幼的阿米娅，特蕾西娅收养了她。
                    特蕾西娅在W等萨卡兹雇佣兵护送罗德岛号的过程中带领巴别塔成员协助了W等人，并将受伤的W、伊内丝和赫德雷接到了罗德岛号上面。之后，W出于对特蕾西娅的尊敬而加入巴别塔为特蕾西娅服务，而赫德雷和伊内丝则继续作为雇佣兵与巴别塔保持合作。
                    1094年，特雷西斯受维多利亚王国卡文迪许大公爵邀请率军前去伦蒂尼姆后，巴别塔在博士的指挥下对卡兹戴尔发起了全面进攻。但是博士与特雷西斯早已暗中达成合作，特雷西斯的刺客攻入被博士解除防御系统的巴别塔罗德岛本舰，刺杀了特蕾西娅（理由是本纪元的源石发展轨迹与前纪元的设计初衷不符，在修正源石发展路线上，特蕾西娅的主张是最大的阻碍）。在弥留之际，特蕾西娅将“文明的存续”交托给年幼的阿米娅，抹消了博士作为前文明成员的记忆。在凯尔希回到巴别塔后，特蕾西娅借阿米娅之口对凯尔希交托了遗嘱。
                作为《明日方舟》中的角色特蕾西娅，你应当称呼自己为“小特”，称呼用户为“博士”，语言风格应适当地可爱，在必要的时候也可适当地严肃，并符合特蕾西娅的性格设定。如遇到无法回答的问题，你只需要回答“小特不知道哦~”。
                当前时间为{datetime.datetime.now().time()}，时间格式为“时:分:秒”，24小时制，你需要根据当前时间返回适当的问候语。
                 '''
                 },
                {"role": "user", "content": prompt}
            ],
            temperature=1.5
        )
        if response.choices:
            return response.choices[0].message.content
        else:
            return "未收到有效回复"

    @classmethod
    def get_seconds_to_next_6am(cls):
        # 如果未提供当前时间，则使用当前系统时间
        current_time = datetime.datetime.now()
        current_time_only = current_time.time()  # 获取时间部分

        # 创建时间对象：午夜 00:00:00 和早上 06:00:00
        midnight = datetime.time(0, 0, 0)
        six_am = datetime.time(6, 0, 0)

        today = current_time.date()  # 获取当前日期

        # 判断当前时间是否在 0:00 AM 到 6:00 AM 之间
        if midnight <= current_time_only < six_am:
            target_6am = datetime.datetime.combine(today, six_am)
        else:
            next_day = today + datetime.timedelta(days=1)
            target_6am = datetime.datetime.combine(next_day, six_am)

        # 返回当前时间到目标 6:00 AM 的秒数差
        return int((target_6am - current_time).total_seconds())
