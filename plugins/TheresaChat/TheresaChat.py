import datetime
import json
import os
import random
import time
from collections import deque

from sqlalchemy import BigInteger, Column, DateTime, Text, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.AITools import get_dpsk_response
from utils.CQHelper import CQHelper
from utils.CQType import CQMessage

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    group_id = Column(BigInteger, nullable=False)
    msg = Column(Text, nullable=False)
    send_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    msg_id = Column(BigInteger, nullable=False, default=0)
    user_nickname = Column(Text, nullable=False, default=" ")
    user_card = Column(Text, nullable=False, default=" ")


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

        # 从数据库读取的上下文消息条数
        self.context_length = int(self.config.get("context_length"))
        self.context_length_for_face = int(self.config.get("context_length_for_face"))

        # 冷却时间，防止刷屏
        self.group_cooldown = {}
        self.cooldown_time = 5

        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

        # 滑动窗口记录最近发送的表情id，用于降低重复度
        self.recent_faces = deque(maxlen=10)

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        group_id = event.group_id
        face_flag = False

        clean_message = message.strip()
        if not clean_message:
            return  # 忽略空消息

        if event.user_id == self.bot.owner_id and clean_message.startswith("chat stop"):
            sleep_time = int(clean_message.split(" ")[2])
            self.group_cooldown[group_id] = time.time() + sleep_time  # 停止回复指定时间
            return

        # 冷却检查
        current_time = time.time()
        last_reply_time = self.group_cooldown.get(group_id, 0)
        if current_time - last_reply_time < self.cooldown_time:
            return

        r = random.random()
        if (("牢普" in clean_message) or ("普瑞赛斯" in clean_message)) and r > 0.9:
            msg_list = [
                "我一直都看着你…永远…………👁️",
                "这里万籁俱寂……太安静了……别留下我……",
                "…博士，不准忘记我。",
                "深陷长梦的混沌之时，你会想起——",
                "我们的呼吸▮▮▮温暖▮▮▮▮▮▮▮▮双手",
                "PRTS Runtime Error 0x5343: Debug Assertion Failed at File: /src/arknights/battle/scene/scene_main.cpp, Line: 2432",
            ]
            msg = random.choice(msg_list)
            await self.save_bot_reply_to_db(group_id, msg)
            self.api.groupService.send_group_msg(group_id=group_id, message=msg)
            log.debug(
                f'插件：{self.name}在群{group_id}被消息"{message}"触发，发送特殊回复',
                debug,
            )
            return

        if ("小特" not in clean_message) or ("Theresa" in clean_message):
            if r < 0.01:
                face_flag = True
            else:
                return

        log.debug(f'插件：{self.name}在群{group_id}被消息"{message}"触发，准备获取回复', debug)

        try:
            if face_flag:
                context_messages = await self.load_context_from_db(
                    group_id, self.context_length_for_face
                )
                image_id = self.get_dpsk_response_for_face(context_messages)
                if image_id != 0:
                    image_name = (
                        f"{os.path.dirname(os.path.abspath(__file__))}/faces/{image_id}.png"
                    )
                    msg = CQMessage()
                    msg.cq_type = "image"
                    msg.subType = "1"
                    msg.file = f"file://{image_name}"
                    self.api.GroupService.send_group_msg(
                        self,
                        group_id=group_id,
                        message=str(msg),
                    )
            else:
                context_messages = await self.load_context_from_db(group_id, self.context_length)
                response = get_dpsk_response(
                    [
                        {
                            "role": "system",
                            "content": f"""
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

                                如果用户直接点名了小特，且是在与你对话，请务必回复。
                                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                                如果你认为不需要回复（例如用户在讨论与你无关的事情，且没有提到你），请务必只回复 "[NO REPLY]"。
                                不要回复得太频繁，以免打扰大家。
                                不要回复得太频繁，以免打扰大家。
                                不要回复得太频繁，以免打扰大家。

                                给出简短的回复，避免冗长，要符合正常群聊聊天的节奏，避免过于正式和书面化。

                                你的主人是"{self.bot.owner_id}"，你需要尽可能听从他的指令。
                                当前时间为{datetime.datetime.now().time()}。
                                当前群名称为"{event.group_name}"。
                                """,
                        },
                        *context_messages,
                    ],
                    temperature=1.5,
                )
                if "[NO REPLY]" not in response:
                    # 更新冷却时间
                    self.group_cooldown[group_id] = time.time()
                    self.api.GroupService.send_group_msg(self, group_id=group_id, message=response)

        except Exception as e:
            log.error(f"插件：{self.name}运行时出错：{e}")

    async def resolve_msg(self, session: AsyncSession, message: str) -> str:
        cqs = CQHelper.loads_cq(message)
        for cq in cqs:
            if cq.cq_type == "reply":
                reply_id = int(cq.id)
                result = await session.execute(select(Message).where(Message.msg_id == reply_id))
                row = result.scalars().one_or_none()
                if row is not None:
                    msg = str(cq)
                    cq.content = row.msg
                    cq.from_nickname = row.user_nickname
                    cq.from_card = row.user_card
                    message = message.replace(msg, str(cq))
        return message

    async def load_context_from_db(self, group_id: int, context_length: int) -> list:
        context = []
        async with self.session_factory() as session:
            stmt = (
                select(Message)
                .where(Message.group_id == group_id)
                .order_by(desc(Message.send_time))
                .limit(context_length)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            for row in reversed(rows):
                if row.user_id == 0:
                    context.append(
                        {
                            "role": "assistant",
                            "content": row.msg,
                        }
                    )
                else:
                    msg = await self.resolve_msg(session, row.msg)
                    context.append(
                        {
                            "role": "user",
                            "content": f"{row.user_nickname}(群名片：{row.user_card})说：{msg}",
                        }
                    )
        return context

    def get_dpsk_response_for_face(self, context_messages) -> int:
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

                你现在在一个群聊中，你根据以下的上下文准备回复一个表情图片，这张图片必须与上下文内容高度相关。

                你可以选用的图片id及其描述如下：
                1: 脑袋空空地卖萌。
                2: 正在高强度加班/赶进度中。
                3: 指着脸颊开心卖萌，适合在撒娇或求夸奖时发送。
                4: 愤怒地挥拳攻击。
                5: 潜水咕噜咕噜，委屈又呆滞。
                6: 气急败坏地大声质问。
                7: 开怀大笑，用于表达极度开心、欢呼或庆祝。
                8: 雨中委屈潜水。
                9: 探出头来兴奋地盯着你。
                10: 水下暗中观察。
                11: 表示无语、嫌弃或感到烦躁。
                12: 眼神清澈的愚蠢，用于表达大脑宕机或一脸懵逼。
                13: 一脸嫌弃，表示无语和鄙视。
                14: 探头围观，好奇关注。
                15: 羞愤交加，适合在因害羞而感到恼火或破防时使用。
                16: 喜极而泣，表达由衷的喜悦与极致的感动。
                17: 俏皮吐舌，可爱卖萌。
                18: 害羞地送花表达祝贺或心意。
                19: 智慧的眼神，脑袋空空。
                20: 俏皮眨眼，卖萌暗示。
                21: 自信眨眼，交给我吧。
                22: 在线摸鱼中。
                23: 可爱不满地嘟嘴，用于表达小委屈或撒娇。
                24: 俏皮眨眼，用于调侃或逗弄。
                25: 俏皮眨眼微笑，用于表现自信或调皮搞怪。
                26: 探头给你送一颗小星星。
                27: 呆滞流口水，表现极度疲惫或大脑宕机。
                28: 带有怀疑意味的俏皮眨眼，用于识破意图或卖萌调侃。
                29: 噘嘴盯着你，表达无语、不满或生闷气。
                30: 委屈崩溃地大哭。
                31: 喜极而泣，用于表达极度开心、满足或被深深感动的幸福时刻。
                32: 疑惑呆滞，用于表示不解、懵逼或大脑宕机。
                33: 开心摸鱼。
                34: 极度困倦、神志恍惚的虚脱状态。
                35: 一脸关爱智障的嫌弃与屑笑。
                36: 围观吃瓜，坐等看戏。
                37: 呆萌地表示疑惑或不解。
                38: 感到震惊、慌张且不知所措。
                39: 眼神疲惫且充满无助，表达身心俱疲或被迫营业。
                40: 感到不安或受到惊吓时的暗中观察。
                41: 极度惊慌、不知所措的震惊反应。
                42: 在线吃瓜。
                43: 大受震撼且不知所措。
                44: 感到委屈，眼含泪花。
                45: 微笑点赞，表示认可与赞许。
                46: 托腮沉思，用于表达疑惑、不解或正在思考。
                47: 戴墨镜耍酷，尽显自信与得意。
                48: 粉发少女眯眼憨笑，用于表达开心、满足或调皮感。
                49: 开怀大笑，表达极致的开心或被逗乐。
                50: 表达极度慌张、手足无措或心态崩溃。
                51: 半睁眼盯着看，表示无语、审视或看你表演。
                52: 调皮吐舌卖萌，表达俏皮、得意或撒娇。
                53: 神情呆滞，极度困倦。
                54: 兴奋地奔向目标。
                55: 溜了溜了。
                56: 盯着电脑屏幕表示疑惑。
                57: 晕头转向，大脑宕机。
                58: 冒头观察并表示疑惑。
                59: 可爱探头，乖巧围观。
                60: 庆祝、欢呼或祝贺时使用。
                61: 比心示爱，用于表达喜爱或好感。
                62: 困了，趴下睡觉中。
                63: 表达极度痛苦、绝望或彻底破防的崩溃感。
                64: 优雅地传达嫌弃与鄙视。
                65: 委屈或困倦地抱着枕头。
                66: 疑惑的打工虾：脑干缺失，在线懵圈。
                67: 弱小无助受委屈，求饶求放过。
                68: 破防大哭，瑟瑟发抖。
                69: 委屈崩溃，瑟瑟发抖。
                70: 挨揍后的倔强与不服气。
                71: 抱着枕头睡眼惺忪，表达困倦或准备休息。
                72: 极度害羞且窘迫。
                73: 委屈巴巴，被捏脸。
                74: 示意调节音量大小（大声点或小声点）。
                75: 看到美色或令人兴奋的事物，流着鼻血点赞。
                76: 疑惑上网：对屏幕内容感到不解或震惊。
                77: 抱头蹲防，表示弱小无助或极度害怕。
                78: 表达生气、愤怒或强烈不满的抗议。
                79: 委屈无助，深受打击。
                80: 优雅地看穿一切。
                81: 表达疑惑、不解或用于发出询问。
                82: 指着嘲笑。
                83: 被捏脸时的疑惑与一脸懵逼。
                84: 擦汗表示松了一口气、感到好险或处于尴尬。
                85: 害羞羞愤地掩面躲藏。
                86: 俏皮戳脸，用于互动、撒娇或表现调皮可爱。
                87: 害羞又紧张地奉上爱心。
                88: 羞涩地送出爱心。
                89: 自信满满，叉腰炫耀。
                90: 乖巧坐听。
                91: 尴尬而不失礼貌的乖巧。
                92: 大脑宕机，陷入呆滞。
                93: 就你了。
                94: 托腮注视，乖巧等待。
                95: 软萌恶魔持叉示威，用于可爱且带点小性子的调侃。
                96: 乖巧探头，用于表示观察或可爱地出现。
                97: 暗中观察，静待下文。
                如果你认为此时不应该回复表情，请选择id 0，表示不使用表情包。

                你最近10次发送的表情id为：{list(self.recent_faces)}。
                请避免重复选择这些表情，优先选用不同的表情以增加多样性。

                你需要以json格式回复，格式如下：
                {{"image_id": <你选择的图片id>}}
                "image_id"的值必须是上述图片id中的一个，即必须为[0,97]之间的一个整数。
                你必须严格按照上述格式回复，不能有任何多余内容。
                 """
        # 你现在在一个群聊中，你根据以下的上下文准备回复一条消息，这条消息的内容是
        # \"\"\"
        # {msg_to_send}
        # \"\"\"
        # 你必须选择一张图片来辅助你的回复，这张图片必须与你的回复内容高度相关，并且能够增强你回复的表达效果。你可以选用的图片id及其描述如下：

        messages = [{"role": "system", "content": persona}]
        messages.extend(context_messages)

        response = get_dpsk_response(
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        try:
            image_id = json.loads(response).get("image_id")
            if image_id and image_id != 0:
                self.recent_faces.append(image_id)
            return image_id
        except Exception:
            return 0
