from Plugins import plugin_main, Plugins
from Event.EventHandler import GroupMessageEventHandler
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from Logging.PrintLog import Log


class GetStuId(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "GetStuId"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                获取指定群的成员QQ号和学号对应关系存入数据库
                                usage: GetStuId <群号>
                            """
        self.init_status()

    @plugin_main(call_word=["GetStuId"], require_db=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        group_id = int(message.split(" ")[1])
        group_member_list = self.api.GroupService.get_group_member_list(self, group_id=group_id).get("data")

        info_list = []
        for member in group_member_list:
            user_id = member["user_id"]
            card = member.get("card_or_nickname")
            if ("-" in card) and (card.split("-")[0].isdigit()):
                stu_id = card.split("-")[0]
                info_list.append((user_id, stu_id))
        self.api.GroupService.send_group_msg(self, group_id=event.group_id, message=f"共获取到{len(info_list)}条数据")

        async_sessions = sessionmaker(bind=self.bot.database, class_=AsyncSession, expire_on_commit=False)

        async with async_sessions() as session:
            async with session.begin():
                for user_id, stu_id in info_list:
                    stu_info = self.StuId(stu_id=int(stu_id), qq_id=str(user_id))
                    await session.merge(stu_info)
        return

    Basement = declarative_base()

    class StuId(Basement):
        __tablename__ = "stu_id"
        stu_id = Column(Integer, primary_key=True)
        qq_id = Column(String)
