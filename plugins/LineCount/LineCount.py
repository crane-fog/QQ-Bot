from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from utils.CQType import At

Base = declarative_base()


class LineCounts(Base):
    __tablename__ = "linecounts"

    semester = Column(Integer, primary_key=True)
    stu_id = Column(Integer, primary_key=True)
    count = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)


class StuId(Base):
    __tablename__ = "stu_qq_id_map"
    stu_id = Column(Integer, primary_key=True)
    qq_id = Column(String)


class LineCount(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "LineCount"
        self.type = "Group"
        self.author = "just monika / Heai"
        self.introduction = """
                                获取自己本学期一共在高程作业网提交了多少行代码
                                usage: Theresa linecount
                            """
        self.init_status()
        self.semester_dict = {
            893688452: 252610,
            861871927: 252610,
            110275974: 252610,
            927504458: 252610,
        }
        self.total_people = {
            252610: 904,
        }
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    @plugin_main(call_word=["Theresa linecount"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        group_id = event.group_id
        user_id = event.user_id
        sender_card = event.card.split("-")
        if len(sender_card) != 3:
            self.api.groupService.send_group_msg(
                group_id=group_id,
                message=f"{At(qq=user_id)} 群名片格式不正确，请改正后再进行查询",
            )
            return
        else:
            stu_id = int(sender_card[0])
            select_result = None
            semester_id = self.semester_dict.get(group_id)
            select_result = await self.query_by_stu_id(stu_id, semester_id)

            if select_result is not None:
                rank = select_result.get("rank")
                count = select_result.get("count")
                query_user_id = select_result.get("user_id")
                total = self.total_people.get(semester_id)
                if int(query_user_id) != user_id:
                    self.api.groupService.send_group_msg(
                        group_id=group_id,
                        message=f"{At(qq=user_id)} "
                        f"该学号所有者的QQ号{query_user_id}，与你的QQ号{user_id}不匹配，不予查询！",
                    )
                    return
                else:
                    self.api.groupService.send_group_msg(
                        group_id=group_id,
                        message=f"{At(qq=user_id)} 本学期你一共提交了 {count} 行代码，代码量超过了同期课程的 {(rank / total) * 100:.0f}% 的学生！",
                    )
            else:
                self.api.groupService.send_group_msg(
                    group_id=group_id,
                    message=f"{At(qq=user_id)} 未查询到学号{stu_id}，QQ号{user_id}的信息！",
                )

    async def query_by_stu_id(self, stu_id, semester_id):
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    select(LineCounts.rank, LineCounts.count, StuId.qq_id)
                    .join(StuId, LineCounts.stu_id == StuId.stu_id)
                    .where(LineCounts.stu_id == stu_id, LineCounts.semester == semester_id)
                )
                result = await session.execute(stmt)
                data = result.first()
                if data:
                    return {
                        "rank": data.rank,
                        "count": data.count,
                        "user_id": data.qq_id,
                    }
                return None
