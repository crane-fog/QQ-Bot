import os

from sqlalchemy import Column, Integer, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent


class DataImport(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "DataImport"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                导入求刀、行数、名单数据
                                usage: DataImport scores/linecounts/stulists <学期课程编号>
                            """
        self.init_status()
        self.models = {}
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    def get_model(self, table_name: str):
        if table_name in self.models:
            return self.models[table_name]

        class DynamicModel(self.Basement):
            __tablename__ = table_name
            __table_args__ = {"extend_existing": True}
            semester = Column(Integer, primary_key=True)
            stu_id = Column(Integer, primary_key=True)
            if table_name == "scores":
                score = Column(Integer, nullable=False)
            elif table_name == "linecounts":
                count = Column(Integer, nullable=False)
                rank = Column(Integer, nullable=False)
            elif table_name == "stulists":
                name = Column(Text, nullable=False)

        self.models[table_name] = DynamicModel
        return DynamicModel

    @plugin_main(call_word=["DataImport"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        table_name = message.split(" ")[1]
        if table_name not in ["scores", "linecounts", "stulists"]:
            self.api.groupService.send_group_msg(
                group_id=event.group_id,
                message="表名错误，请使用 scores、linecounts 或 stulists",
            )
            return
        semester = int(message.split(" ")[2])
        filename = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data",
            table_name,
            f"{semester}.txt",
        )

        with open(filename, encoding="utf-8") as f:
            lines = f.readlines()

        self.api.groupService.send_group_msg(
            group_id=event.group_id,
            message=f"正在向表 {table_name} 导入学期 {semester} 的 {len(lines)} 条数据",
        )

        model = self.get_model(table_name)

        delimiter = "\t" if "\t" in lines[0] else " "
        async with self.session_factory() as session:
            async with session.begin():
                if table_name == "scores":
                    for line in lines:
                        _, stu_id, score = line.strip().split(delimiter)
                        score_info = model(semester=semester, stu_id=int(stu_id), score=int(score))
                        await session.merge(score_info)
                elif table_name == "linecounts":
                    data_list = []
                    for line in lines:
                        stu_id, count = line.strip().split(delimiter)
                        data_list.append({"stu_id": int(stu_id), "count": int(count)})
                    data_list.sort(key=lambda x: x["count"])
                    for index, data in enumerate(data_list):
                        count_info = model(
                            semester=semester,
                            stu_id=data["stu_id"],
                            count=data["count"],
                            rank=index,
                        )
                        await session.merge(count_info)
                elif table_name == "stulists":
                    for line in lines:
                        stu_id, name = line.strip().split(delimiter)
                        stulist_info = model(semester=semester, stu_id=int(stu_id), name=name)
                        await session.merge(stulist_info)
        return

    Basement = declarative_base()
