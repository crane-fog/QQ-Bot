from sqlalchemy import Column, Integer, select, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from CQMessage.CQType import At, Face
from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins

log = Log()


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
        self.table_dict = {
            893688452: "linecount_252610",  # bot测试群
            861871927: "linecount_252610",  # 25261卓班高程
            110275974: "linecount_252610",  # 25261AI拔高程
            927504458: "linecount_252610",  # 25261嘉定高程
        }
        self.total_people = {
            893688452: 904,  # bot测试群
            861871927: 904,  # 25261卓班高程
            110275974: 904,  # 25261AI拔高程
            927504458: 904,  # 25261嘉定高程
        }
        self._count_models = {}

    @plugin_main(call_word=["Theresa linecount"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        group_id = event.group_id
        user_id = event.user_id
        sender_card = event.card.split("-")
        if len(sender_card) != 3:
            self.api.groupService.send_group_msg(group_id=group_id, message=f"{At(qq=user_id)} 群名片格式不正确，请改正后再进行查询")
            return
        else:
            stu_id = int(sender_card[0])
            select_result = None
            table_name = self.table_dict.get(group_id)
            try:
                select_result = await self.query_by_stu_id(stu_id, table_name)
            except Exception as e:
                raise e

            log.debug(f"查询到的信息是：{select_result}", debug)
            if select_result is not None:
                rank = select_result.get("rank")
                count = select_result.get("count")
                query_user_id = select_result.get("user_id")
                total = self.total_people.get(group_id)
                if int(query_user_id) != user_id:
                    self.api.groupService.send_group_msg(
                        group_id=group_id,
                        message=f"{At(qq=user_id)} " f"该学号所有者的QQ号{query_user_id}，与你的QQ号{user_id}不匹配，不予查询！",
                    )
                    return
                else:
                    self.api.groupService.send_group_msg(
                        group_id=group_id,
                        message=f"{At(qq=user_id)} 本学期你一共提交了 {count} 行代码，代码量超过了同期课程的 {(rank / total) * 100:.0f}% 的学生！",
                    )
            else:
                self.api.groupService.send_group_msg(
                    group_id=group_id, message=f"{At(qq=user_id)} 未查询到学号{stu_id}，QQ号{user_id}的信息！"
                )

    def get_counts_model(self, table_name):
        if table_name in self._count_models:
            return self._count_models[table_name]

        class DynamicCounts(self.Basement):
            __tablename__ = table_name
            __table_args__ = {"extend_existing": True}
            stu_id = Column(Integer, primary_key=True)
            count = Column(Integer)
            rank = Column(Integer)

        self._count_models[table_name] = DynamicCounts
        return DynamicCounts

    async def query_by_stu_id(self, stu_id, table_name):
        Counts = self.get_counts_model(table_name)
        async_sessions = sessionmaker(bind=self.bot.database, class_=AsyncSession, expire_on_commit=False)
        async with async_sessions() as session:
            async with session.begin():
                stmt = (
                    select(Counts.rank, Counts.count, self.StuId.qq_id)
                    .join(self.StuId, Counts.stu_id == self.StuId.stu_id)
                    .where(Counts.stu_id == stu_id)
                )
                result = await session.execute(stmt)
                data = result.first()
                if data:
                    return {"rank": data.rank, "count": data.count, "user_id": data.qq_id}
                return None

    Basement = declarative_base()

    class StuId(Basement):
        __tablename__ = "stu_id"
        stu_id = Column(Integer, primary_key=True)
        qq_id = Column(String)
