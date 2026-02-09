from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.event_handler.RequestEventHandler import GroupRequestEvent
from src.PrintLog import Log

log = Log()


class GroupApprove(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = (
            "GroupApprove"  # 插件的名字（一定要和类的名字完全一致（主要是我能力有限，否则会报错））
        )
        self.type = "GroupRequest"  # 插件的类型（这个插件是在哪种消息类型中触发的）
        self.author = "kiriko"  # 插件开发作者（不用留真名，但是当插件报错的时候需要根据这个名字找到对应的人来修）
        self.introduction = """
                                自动处理入群申请
                                usage: auto
                            """
        self.init_status()
        self.real_answer = ""
        self.all_inform = None
        self.spacer = [" ", "-"]
        self.spacer_type = ""

    @plugin_main(check_call_word=False, require_db=True)
    async def main(self, event: GroupRequestEvent, debug):
        if self.all_inform is None:
            for _ in range(5):
                try:
                    self.all_inform = await self.select_all_infom()
                    log.debug("初始化验证信息成功", debug)
                    break
                except Exception as e:
                    log.debug(e, debug=debug)
                    continue
        if event.sub_type != "add":
            return
        group_id = event.group_id
        reject_flag1 = self.config.get("reject1")
        reject_flag2 = self.config.get("reject2")
        flag = event.flag
        full_comment = event.comment

        # 正式进入插件运行部分
        requests = full_comment.split("\n答案：")
        self.real_answer = requests[1]
        if not self.request_conform(debug):
            if reject_flag1:
                reject_reason = "请以正确格式申请入群"
                self.api.GroupService.set_group_add_request(
                    self, flag=flag, approve="false", reason=reject_reason
                )
                log.debug(
                    f"{self.name}:{group_id}错误入群申请{flag}拒绝，拒绝理由为{reject_reason}",
                    debug,
                )
            else:
                log.debug(f"{self.name}:{group_id}错误入群申请{flag}挂起", debug)
            return

        stu_id = int(self.real_answer[:7])
        if not self.stu_id_conform(stu_id):
            if reject_flag2:
                reject_reason = "学号错误"
                self.api.GroupService.set_group_add_request(
                    self, flag=flag, approve="false", reason=reject_reason
                )
                log.debug(
                    f"{self.name}:{group_id}无信息入群申请{flag}拒绝，拒绝理由为{reject_reason}",
                    debug,
                )
            else:
                log.debug(f"{self.name}:{group_id}无信息入群申请{flag}挂起", debug)
        else:
            self.api.GroupService.set_group_add_request(self, flag=flag)
            log.debug(f"{self.name}:{group_id}正确入群申请{flag}批准", debug)

    def request_conform(self, debug):
        parts = self.config.get("parts")
        flag = False
        for spacer in self.spacer:
            answer_cuts = self.real_answer.split(spacer)
            if len(answer_cuts) == int(parts):
                flag = True
                self.spacer_type = spacer
                break

        if not answer_cuts[0].isdigit():
            flag = False
        else:
            if len(answer_cuts[0]) != 7:
                flag = False
        if not flag:
            return answer_cuts[0][:7].isdigit() and (not answer_cuts[0][7].isdigit())
        else:
            return True

    def stu_id_conform(self, stu_id):
        if stu_id > 2550000 and stu_id < 2557000:
            return True
        # data = self.all_inform.get("data")
        # select_result = data.get(stu_id)
        # if select_result:
        #     return True

    async def select_all_infom(self):
        async_sessions = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

        async with async_sessions() as sessions:
            raw_table = select(self.StuInformation)
            results = await sessions.execute(raw_table)

            indexs = results.scalars().all()
            indexs_dict = {
                lc.stu_id: {"name": lc.name, "major_short": lc.major_short} for lc in indexs
            }

            return {"data": indexs_dict}

    Basement = declarative_base()

    class StuInformation(Basement):
        __tablename__ = "stu_information"
        stu_id = Column(Integer, primary_key=True)
        name = Column(String)
        major_short = Column(String)
