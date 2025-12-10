import re
from Plugins import plugin_main, Plugins
from Logging.PrintLog import Log

log = Log()


def check_card_format(card: str) -> bool:
    pattern = r"^\d{7}-(围观|助教|大数据|信安|交通|软工|计科|计拔|数学|自动化|通信|AI|微电子|电信|电气|测绘|光电|领军|图灵|AI拔|汽车|地物|海洋|交工|交数|交运|材料|机电|车辆|力学|地质|机械|领军|卓\d{2})-.+$"
    return bool(re.match(pattern, card) or card == "Q群管家" or card.startswith("bot-"))


class TheresaCard(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaCard"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                检查高程群名片格式，仅限群管理员使用
                                usage: Theresa card
                            """
        self.init_status()

    @plugin_main(call_word=["Theresa card"])
    async def main(self, event, debug):
        permissionList = [2046889405]
        if (event.user_id not in permissionList) and (event.role not in ["admin", "owner"]):
            return

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
                message = "\n".join([f"[CQ:at,qq={user_id}] 名片: {card}" for user_id, card in zip(not_allowed_ids, not_allowed_cards)])
        else:
            message = "所有群成员名片格式均符合要求"
        self.api.GroupService.send_group_msg(self, group_id=event.group_id, message=message)
        return
