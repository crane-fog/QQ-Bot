import re
import time

from sqlalchemy import Column, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from utils.CQType import At, Forward

Base = declarative_base()


class StuList(Base):
    __tablename__ = "stulists"

    semester = Column(Integer, primary_key=True)
    stu_id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)


class TheresaCard(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "TheresaCard"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                检查高程群名片格式\nkick: 踢出\ndebug: 不@\nstrict: 检查选课名单\nunenter: 检查未入群成员\n最后参数: 仅检查已入群>x小时
                                usage: Theresa card (kick/debug) (strict) (unenter) (<小时数>)
                            """

        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

        self.semester_dict = {
            893688452: 252620,
            1082118774: 252620,
            1084322221: 252620,
        }

        self.init_status()

    @plugin_main(call_word=["Theresa card"], require_db=True)
    async def main(self, event, debug):
        # 可使用 kick
        permission_ids: list[int] = list(map(int, self.config.get("permission_ids").split(",")))
        permission_ids.append(self.bot.owner_id)
        # 可使用普通检查
        if (
            (event.user_id not in permission_ids)
            and (event.role not in ["admin", "owner"])
            and (event.user_id not in self.bot.assistant_list)
        ):
            self.api.groupService.send_group_msg(group_id=event.group_id, message="权限不足")
            return

        # 解析参数
        debug_flag = "debug" in event.message
        kick_flag = ("kick" in event.message) and (not debug_flag)
        strict_flag = "strict" in event.message
        unenter_flag = "unenter" in event.message
        check_time_flag = False
        if event.message.split(" ")[-1].isdigit():
            time_limit_hours = int(event.message.split(" ")[-1])
            time_limit_seconds = time_limit_hours * 3600
            check_time_flag = True
        if kick_flag and (event.user_id not in permission_ids):
            self.api.groupService.send_group_msg(group_id=event.group_id, message="权限不足")
            return
        if strict_flag or unenter_flag:
            semester = self.semester_dict.get(event.group_id)
            if semester is None:
                self.api.groupService.send_group_msg(
                    group_id=event.group_id,
                    message=f"未设定群 {event.group_id} 学期信息，请联系 bot 管理员",
                )
                return

        # 获取群成员列表，初始化变量
        group_member_list = self.api.groupService.get_group_member_list(
            group_id=event.group_id
        ).get("data")
        ignored_ids: list[int] = list(map(int, self.config.get("ignored_ids").split(",")))
        not_allowed_ids = []
        not_allowed_cards = []
        strict_candidates: list[tuple[int, int, str, str]] = []
        not_entered: dict[int, str] = {}

        # 执行检查
        for member in group_member_list:
            user_id = member["user_id"]

            if user_id in ignored_ids:
                continue

            if check_time_flag:
                if member["join_time"] > int(time.time()) - time_limit_seconds:
                    continue

            card = member.get("card_or_nickname")
            passed, stu_id, name = self.basic_card_check(card)
            if not passed:
                # 对常见错误进行提示
                if "–" in card or "—" in card or "_" in card or "⁻" in card:
                    card += "\n名片中连字符应为英文状态下的-"
                if "微电" in card and "应" in card:
                    card += "\n微电子应用物理双学位应为微应物"

                not_allowed_ids.append(user_id)
                not_allowed_cards.append(card)
            elif strict_flag or unenter_flag:
                if user_id not in self.bot.assistant_list:
                    strict_candidates.append((user_id, stu_id, name, card))

        if strict_flag or unenter_flag:
            stu_ids = {stu_id for _, stu_id, _, _ in strict_candidates}
        if strict_flag and strict_candidates:
            db_name_map = await self.check_in_list_batch(semester, stu_ids)
            for user_id, stu_id, _, card in strict_candidates:
                if db_name_map.get(stu_id) is None:  # != name:
                    not_allowed_ids.append(user_id)
                    not_allowed_cards.append(card + "\n不在选课名单中")
        if unenter_flag and strict_candidates:
            not_entered = await self.check_in_list_batch(semester, stu_ids, reverse=True)

        # 处理检查结果
        if not_allowed_ids:
            if debug_flag:
                entry_lines = [
                    f"{user_id} 名片: {card}"
                    for user_id, card in zip(not_allowed_ids, not_allowed_cards, strict=True)
                ]
            else:
                entry_lines = [
                    f"      {At(qq=user_id)} \n名片: {card}"
                    for user_id, card in zip(not_allowed_ids, not_allowed_cards, strict=True)
                ]

            if kick_flag:
                suffix = "\n\n已将不符合要求的成员踢出群聊"
            else:
                suffix = "\n\n以上成员不在选课名单或群名片不符合要求，请参照群公告修改"

            if len(entry_lines) > 20:
                for entry_chunk in chunked(entry_lines, 20):
                    message = "\n".join(entry_chunk)
                    self.api.groupService.send_group_msg(group_id=event.group_id, message=message)
                self.api.groupService.send_group_msg(
                    group_id=event.group_id, message=suffix.strip()
                )
            else:
                message = "\n".join(entry_lines) + suffix
                self.api.groupService.send_group_msg(group_id=event.group_id, message=message)
        else:
            message = "所有群成员名片格式均符合要求"
            self.api.groupService.send_group_msg(group_id=event.group_id, message=message)

        if unenter_flag:
            if strict_candidates:
                if not_entered:
                    not_entered_lines = [f"{stu_id} {name}" for stu_id, name in not_entered.items()]
                    forward = Forward()
                    forward.add_node(
                        type="text", text=f"以下成员已选课但未入群，共{len(not_entered)}人"
                    )
                    forward.add_node(type="text", text="\n".join(not_entered_lines))
                    self.api.groupService.send_group_forward_msg(
                        group_id=event.group_id, forward_message=forward.message
                    )
                else:
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message="所有已选课成员均已入群"
                    )
            else:
                self.api.groupService.send_group_msg(
                    group_id=event.group_id, message="所有成员均未入群"
                )

        if kick_flag:
            for user_id in not_allowed_ids:
                self.api.groupService.set_group_kick(group_id=event.group_id, user_id=user_id)
        return

    def basic_card_check(self, card: str) -> tuple[bool, int | None, str | None]:
        pattern = r"^(\d{7})-(助教|数学|数拔|材料|测绘|车辆|汽车|城规|地物|地质|电气|电科|电信|园林|土法|工力|工力强|国豪|同德|济美|光电|海技|海洋|环工|环科|机电|机械|化拔|计拔|力拔|计科|国豪计科|图灵|智交|交通|交通应数|交运|金融|物理|领军|AI|AI拔|国豪AI|软工|视传|大数据|数金|应数|应数强|通信|统计|微电子|微应物|文管|物流|新能材|信安|信管|行政|应物强|智建|智造|自动化|卓\d{2}|卓越|经管|计算机|生科|外国语|医学|航力|人文|物拔|中德|中德车辆|中外机械)-(.+)$"
        match = re.match(pattern, card)
        if not match:
            return False, None, None
        stu_id = int(match.group(1))
        name = match.group(3)
        return True, stu_id, name

    async def check_in_list_batch(
        self, semester: int, stu_ids: set[int], reverse: bool = False
    ) -> dict[int, str]:
        async with self.session_factory() as session:
            if reverse:
                stmt = select(StuList.stu_id, StuList.name).where(
                    StuList.semester == semester,
                    StuList.stu_id.not_in(stu_ids),
                )
            else:
                stmt = select(StuList.stu_id, StuList.name).where(
                    StuList.semester == semester,
                    StuList.stu_id.in_(stu_ids),
                )
            result = await session.execute(stmt)

            return {stu_id: name for stu_id, name in result.all()}


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]
