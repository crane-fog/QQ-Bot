from sqlalchemy import Column, Integer, select, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from Event.EventHandler.GroupMessageEventHandler import GroupMessageEvent
from Plugins import plugin_main, Plugins


class LineCountData(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "LineCountData"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                导入LineCount数据
                                usage: LineCountData <文件名> <表名>
                            """
        self.init_status()
        self.all_line_count = None
        self._count_models = {}

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

    @plugin_main(call_word=["LineCountData"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        filename = f"{os.path.dirname(os.path.abspath(__file__))}/data/" + message.split(" ")[1]
        table_name = message.split(" ")[2]

        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.api.groupService.send_group_msg(group_id=event.group_id, message=f"正在向表 {table_name} 导入{len(lines)}条数据")

        CountsModel = self.get_counts_model(table_name)

        data_list = []
        for line in lines:
            stu_id, count = line.strip().split(" ")
            data_list.append({"stu_id": int(stu_id), "count": int(count)})

        data_list.sort(key=lambda x: x["count"])

        async_sessions = sessionmaker(bind=self.bot.database, class_=AsyncSession, expire_on_commit=False)
        async with async_sessions() as session:
            async with session.begin():
                for index, data in enumerate(data_list):
                    count_info = CountsModel(stu_id=data["stu_id"], count=data["count"], rank=index)
                    await session.merge(count_info)
        return

    Basement = declarative_base()
