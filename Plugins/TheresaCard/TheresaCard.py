import re
from Plugins import plugin_main, Plugins
from Logging.PrintLog import Log

log = Log()


def check_card_format(card: str) -> bool:
    pattern = r"^\d{7}-(围观|助教|数学|材料|测绘|车辆|车辆|汽车|城规|地物|地质|电气|电科|电信|园林|土法|工力|工力强|国豪|济勤|网联|同德|济美|光电|海技|海洋|环工|环科|机电|机械|化拔|计拔|力拔|计科|国豪计科|图灵|智交|交通|交通应数|交运|金融|物理|领军|AI|AI拔|国豪AI|软工|视传|大数据|数金|应数|应数强|通信|统计|微电子|微应物|文管|物流|新能材|信安|信管|行政|应物强|智建|智造|自动化|卓\d{2})-.+$"
    return bool(re.match(pattern, card))


class TheresaCard(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaCard"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                检查高程群名片格式，将不符合要求的踢出，仅限群管理员使用
                                usage: Theresa card (kick/debug)
                            """
        self.init_status()

    @plugin_main(call_word=["Theresa card"])
    async def main(self, event, debug):
        permissionList = [self.bot.owner_id]
        if (event.user_id not in permissionList) and (event.role not in ["admin", "owner"]):
            return

        kick_flag = event.message == "Theresa card kick"

        group_member_list = self.api.GroupService.get_group_member_list(self, group_id=event.group_id).get("data")
        ignored_ids: list = self.config.get("ignored_ids")

        not_allowed_ids = []
        not_allowed_cards = []

        for member in group_member_list:
            user_id = member["user_id"]
            if user_id in ignored_ids:
                continue
            # card = self.api.GroupService.get_group_member_info(self, group_id=event.group_id, user_id=user_id).get("data").get("card")
            card = member.get("card_or_nickname")
            if not check_card_format(card):
                not_allowed_ids.append(user_id)
                not_allowed_cards.append(card)
                log.info(f"用户 {user_id} 的名片格式不符合要求: {card}")
        if not_allowed_ids:
            if event.message == "Theresa card debug":
                message = "\n".join([f"{user_id} 名片: {card}" for user_id, card in zip(not_allowed_ids, not_allowed_cards)])
            else:
                message = "\n".join(
                    [f"      [CQ:at,qq={user_id}] \n名片: {card}" for user_id, card in zip(not_allowed_ids, not_allowed_cards)]
                )
            if kick_flag:
                message += "\n\n已将不符合要求的成员踢出群聊"
            else:
                message += "\n\n以上成员群名片格式不符合要求，请参照群公告修改"
        else:
            message = "所有群成员名片格式均符合要求"
        self.api.GroupService.send_group_msg(self, group_id=event.group_id, message=message)
        if kick_flag:
            for user_id in not_allowed_ids:
                self.api.GroupService.set_group_kick(self, group_id=event.group_id, user_id=user_id)
        return
