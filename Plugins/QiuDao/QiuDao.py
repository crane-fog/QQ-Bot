from sqlalchemy import Column, Integer, select, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from CQMessage.CQType import At, Face
from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins

log = Log()


class QiuDao(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "QiuDao"
        self.type = "Group"
        self.author = "just monika / Heai"
        self.introduction = """
                                根据高程期末考试成绩发送对应的表情
                                usage: Theresa 求刀
                            """
        self.init_status()
        self.all_line_count = None

    @plugin_main(call_word=["Theresa 求刀"], require_db=True)
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
            try:
                select_result = await self.query_by_stu_id(stu_id)
            except Exception as e:
                raise e

            log.debug(f"查询到的信息是：{select_result}", debug)
            if select_result is not None:
                score = select_result.get("score")
                query_user_id = select_result.get("user_id")
                if int(query_user_id) != user_id:
                    self.api.groupService.send_group_msg(
                        group_id=group_id,
                        message=f"{At(qq=user_id)} " f"该学号所有者的QQ号{query_user_id}，与你的QQ号{user_id}不匹配，不予查询！",
                    )
                    return
                else:
                    self.api.groupService.send_group_msg(group_id=group_id, message=f"{At(qq=user_id)} " f"{self.trans_score(score)}")
            else:
                self.api.groupService.send_group_msg(group_id=group_id, message=f"{At(qq=user_id)} 未查询到学号{stu_id}的信息！")

    @classmethod
    def trans_score(cls, score):
        max_knives = min(score, 4)
        if max_knives == 0:
            return Face(id=63)  # 这个是花的id
        elif max_knives == 1:
            return Face(id=112)  # 这个是刀的id
        elif max_knives == 2:
            return f"{Face(id=112)}{Face(id=112)}"
        elif max_knives == 3:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}"
        elif max_knives == 4:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}"
        elif max_knives == 5:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}"
        elif max_knives == 6:
            return f"{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}{Face(id=112)}"
        else:
            return f"你的分数是-114514，超越了全同济-100%的同学！你无敌啦孩子！"  # 虽然理论上不可能有低于0分的，但是还是做了这个的情况, 59是便便表情

    async def query_by_stu_id(self, stu_id):
        async_sessions = sessionmaker(bind=self.bot.database, class_=AsyncSession, expire_on_commit=False)
        async with async_sessions() as session:
            async with session.begin():
                stmt = (
                    select(self.Scores.score, self.StuId.qq_id)
                    .join(self.StuId, self.Scores.stu_id == self.StuId.stu_id)
                    .where(self.Scores.stu_id == stu_id)
                )
                result = await session.execute(stmt)
                data = result.first()
                if data:
                    return {"score": data.score, "user_id": data.qq_id}
                return None

    Basement = declarative_base()

    class Scores(Basement):
        __tablename__ = 'score'
        stu_id = Column(Integer, primary_key=True)
        score = Column(Integer)

    class StuId(Basement):
        __tablename__ = "stu_id"
        stu_id = Column(Integer, primary_key=True)
        qq_id = Column(String)
