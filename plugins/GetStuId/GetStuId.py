from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler


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
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    @plugin_main(call_word=["GetStuId"], require_db=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message

        if not event.user_id == self.bot.owner_id:
            return

        group_id = int(message.split(" ")[1])
        group_member_list = self.api.groupService.get_group_member_list(group_id=group_id).get(
            "data"
        )

        info_list = []
        for member in group_member_list:
            user_id = member["user_id"]
            card = member.get("card_or_nickname")
            if ("-" in card) and (card.split("-")[0].isdigit()):
                stu_id = card.split("-")[0]
                info_list.append((user_id, stu_id))
        self.api.groupService.send_group_msg(
            group_id=event.group_id, message=f"共获取到{len(info_list)}条数据"
        )

        async with self.session_factory() as session:
            async with session.begin():
                for user_id, stu_id in info_list:
                    stu_info = self.StuId(stu_id=int(stu_id), qq_id=str(user_id))
                    await session.merge(stu_info)
        return

    Basement = declarative_base()

    class StuId(Basement):
        __tablename__ = "stu_qq_id_map"
        stu_id = Column(Integer, primary_key=True)
        qq_id = Column(String)
