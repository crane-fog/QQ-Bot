from sqlalchemy import Column, Integer, select, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Logging.PrintLog import Log
from Plugins import plugin_main, Plugins

log = Log()


class QiuDaoData(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "QiuDaoData"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                导入求刀数据
                                usage: QiuDaoData <文件名>
                            """
        self.init_status()
        self.all_line_count = None

    @plugin_main(call_word=["QiuDaoData"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        filename = f"{os.path.dirname(os.path.abspath(__file__))}/data/" + message.split(" ")[1]

        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.api.groupService.send_group_msg(group_id=event.group_id, message=f"共导入{len(lines)}条数据")

        async_sessions = sessionmaker(bind=self.bot.database, class_=AsyncSession, expire_on_commit=False)
        async with async_sessions() as session:
            async with session.begin():
                for line in lines:
                    stu_id, score = line.strip().split(" ")
                    score_info = self.Scores(stu_id=int(stu_id), score=int(score))
                    await session.merge(score_info)
        return

    Basement = declarative_base()

    class Scores(Basement):
        __tablename__ = "score"
        stu_id = Column(Integer, primary_key=True)
        score = Column(Integer)
