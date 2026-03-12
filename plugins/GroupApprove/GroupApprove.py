from sqlalchemy import Column, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.RequestEventHandler import GroupRequestEvent
from src.PrintLog import Log


class GroupApprove(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "GroupApprove"
        self.type = "GroupRequest"
        self.author = "kiriko / Heai"
        self.introduction = """
                                自动处理入群申请
                                usage: auto
                            """
        self.init_status()
        self.all_inform: set[tuple[int, int]] = set()
        self.spacer = [" ", "-"]
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )
        self.semester_dict = {
            1082118774: 252620,
            1084322221: 252620,
        }

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupRequestEvent, debug):
        if not self.all_inform:
            self.all_inform = await self.select_all_inform()

        if event.sub_type != "add":
            return
        group_id = event.group_id
        reject_flag = self.config.getboolean("reject")
        strict_flag = self.config.getboolean("strict")
        flag = event.flag
        full_comment = event.comment

        # 正式进入插件运行部分
        requests = full_comment.split("\n答案：")
        real_answer = requests[1]
        if not self.format_check(real_answer):
            if reject_flag:
                reject_reason = "请以正确格式申请入群"
                self.api.groupService.set_group_add_request(
                    flag=flag, approve="false", reason=reject_reason
                )
                Log.debug(
                    f"{self.name}:{group_id}错误入群申请{flag}拒绝，拒绝理由为{reject_reason}",
                    debug,
                )
            else:
                Log.debug(f"{self.name}:{group_id}错误入群申请{flag}挂起", debug)
            return

        stu_id = int(real_answer[:7])
        if not self.stu_id_conform(stu_id, strict_flag, self.semester_dict.get(group_id)):
            if reject_flag:
                reject_reason = "学号错误"
                self.api.groupService.set_group_add_request(
                    flag=flag, approve="false", reason=reject_reason
                )
                Log.debug(
                    f"{self.name}:{group_id}无信息入群申请{flag}拒绝，拒绝理由为{reject_reason}",
                    debug,
                )
            else:
                Log.debug(f"{self.name}:{group_id}无信息入群申请{flag}挂起", debug)
        else:
            self.api.groupService.set_group_add_request(flag=flag)
            Log.debug(f"{self.name}:{group_id}正确入群申请{flag}批准", debug)

    def format_check(self, real_answer: str) -> bool:
        parts = self.config.getint("parts")
        flag = False
        spacer_type = ""
        for spacer in self.spacer:
            answer_cuts = real_answer.split(spacer)
            if len(answer_cuts) == parts:
                flag = True
                spacer_type = spacer
                break

        if (not answer_cuts[0].isdigit()) or spacer_type == "":
            flag = False
        else:
            if len(answer_cuts[0]) != 7:
                flag = False
        return flag

    def stu_id_conform(self, stu_id: int, strict_flag: bool, semester: int) -> bool:
        if strict_flag:
            i = semester // 10000 - semester % 10  # 252620 -> 25, 252621 -> 24
            i = i * 100000 + 50000
            if stu_id > i and stu_id < i + 7000:
                return True
            else:
                return False
        else:
            if (stu_id, semester) in self.all_inform:
                return True
            else:
                return False

    async def select_all_inform(self) -> set[tuple[int, int]]:
        async with self.session_factory() as sessions:
            stmt = select(self.StuLists.stu_id, self.StuLists.semester)
            result = await sessions.execute(stmt)
            rows = result.all()
            return {tuple(row) for row in rows}

    Base = declarative_base()

    class StuLists(Base):
        __tablename__ = "stulists"

        semester = Column(Integer, primary_key=True)
        stu_id = Column(Integer, primary_key=True)
        name = Column(Text)
