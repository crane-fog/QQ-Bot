import os
from datetime import date, datetime, time, timedelta

import requests
import xlrd
from jinja2 import Template
from playwright.async_api import async_playwright
from sqlalchemy import BigInteger, Boolean, Column, Integer, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from plugins import Plugins, plugin_main
from src.EventController import GroupMessageEvent
from src.PrintLog import Log
from utils.CQHelper import CQHelper

Base = declarative_base()


class Courses(Base):
    __tablename__ = "courses"

    calendar_id = Column(Integer, primary_key=True)
    new_course_code = Column(Text, primary_key=True)
    course_code = Column(Text, primary_key=True)
    teacher = Column(Text, primary_key=True)
    course_name = Column(Text, nullable=False)
    time_info = Column(JSONB, nullable=False)


class PersonalSchedule(Base):
    __tablename__ = "personal_schedule"

    calendar_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    group_id = Column(BigInteger, primary_key=True)
    is_new_code = Column(Boolean, nullable=False)
    new_course_codes = Column(JSONB, nullable=False)
    course_codes = Column(JSONB, nullable=False)


class Schedule(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "Schedule"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                查看群友课表\n导入个人课表：1系统-个人课表-(下滑)查看教材-导出-将导出的 textbook.xls 文件发送到群聊中
                                usage: Schedule
                            """
        self.TIME_MAP = [
            time(8, 0),
            time(8, 50),
            time(10, 0),
            time(10, 50),
            time(13, 30),
            time(14, 20),
            time(15, 30),
            time(16, 20),
            time(18, 30),
            time(19, 20),
            time(20, 10),
        ]
        self.COURSE_TIME = timedelta(minutes=45)
        self.init_status()
        self.session_factory = sessionmaker(
            bind=self.bot.database, class_=AsyncSession, expire_on_commit=False
        )

    @plugin_main(call_word=["Schedule", "[CQ:file,file=textbook"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        calendar = self.config.getint("current_calendar")
        first_day = datetime.strptime(self.config.get("first_day"), "%Y-%m-%d").date()

        if event.message.startswith("[CQ:file,file=textbook"):
            cq = CQHelper.load_cq(event.message)
            file_data = self.api.messageService.get_group_file_url(
                group_id=event.group_id, file_id=cq.file_id
            )
            url = file_data.get("data").get("url")
            response = requests.get(url)
            file_name = f"{os.path.dirname(os.path.abspath(__file__))}/temp/textbook/{event.user_id}_{event.group_id}_{cq.file_id.replace('/', '')}.xls"
            with open(file_name, "wb") as f:
                f.write(response.content)
            try:
                workbook = xlrd.open_workbook(file_name)
                sheet = workbook.sheet_by_index(0)
                target_col_index = 1
                header_value_col3 = sheet.cell_value(0, 2)
                if header_value_col3 == "课程序号":
                    target_col_index = 2
                course_codes: list[str] = []
                for row_idx in range(1, sheet.nrows):
                    value = sheet.cell_value(row_idx, target_col_index)
                    if len(value) > 2:
                        course_codes.append(value)
                async with self.session_factory() as session:
                    new_schedule = PersonalSchedule(
                        calendar_id=calendar,
                        user_id=event.user_id,
                        group_id=event.group_id,
                        is_new_code=(target_col_index == 1),
                        new_course_codes=course_codes if target_col_index == 1 else [],
                        course_codes=course_codes if target_col_index == 2 else [],
                    )
                    await session.merge(new_schedule)
                    await session.commit()
                self.api.groupService.send_group_msg(
                    group_id=event.group_id,
                    message=f"已导入{event.user_id}课表文件",
                )
            except Exception as e:
                Log.error(f"解析课表文件失败，错误信息: {e}")
                self.api.groupService.send_group_msg(
                    group_id=event.group_id, message=f"解析{event.user_id}课表文件失败"
                )
            return

        current_time = datetime.now()
        today = date.today()
        delta_days = (today - first_day).days
        current_week = (delta_days // 7) + 1
        weekday_num = today.isoweekday()

        render_data = {"current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"), "users": []}
        async with self.session_factory() as session:
            stmt = select(PersonalSchedule).where(
                PersonalSchedule.group_id == event.group_id,
                PersonalSchedule.calendar_id == calendar,
            )
            persons: list[PersonalSchedule] = (await session.execute(stmt)).scalars().all()
            for person in persons:
                if person.is_new_code:
                    stmt = select(Courses).where(
                        Courses.calendar_id == calendar,
                        Courses.new_course_code.in_(person.new_course_codes),
                        Courses.time_info.contains(
                            [{"day_of_week": weekday_num, "weeks": [current_week]}]
                        ),
                    )
                else:
                    stmt = select(Courses).where(
                        Courses.calendar_id == calendar,
                        Courses.course_code.in_(person.course_codes),
                        Courses.time_info.contains(
                            [{"day_of_week": weekday_num, "weeks": [current_week]}]
                        ),
                    )
                today_courses: list[Courses] = (await session.execute(stmt)).scalars().all()

                schedule_blocks = []
                # 1. 扁平化提取所有的【今日课程时间块】
                for course in today_courses:
                    for info in course.time_info:
                        if info["day_of_week"] == weekday_num and current_week in info["weeks"]:
                            periods = sorted(info["periods"])
                            start_time = self.TIME_MAP[periods[0] - 1]
                            start_dt = datetime.combine(today, start_time)
                            end_time = self.TIME_MAP[periods[-1] - 1]
                            end_dt = datetime.combine(today, end_time) + self.COURSE_TIME
                            schedule_blocks.append(
                                {
                                    "course_name": course.course_name,
                                    "teacher": course.teacher,
                                    "location": info["location"],
                                    "start_dt": start_dt,
                                    "end_dt": end_dt,
                                }
                            )
                # 2. 按上课时间从小到大排序
                schedule_blocks.sort(key=lambda x: x["start_dt"])
                # 3. 构造默认数据模型（默认状态为今天没课）
                person_data = {
                    "name": self.api.groupService.get_group_member_info(
                        group_id=person.group_id, user_id=person.user_id
                    )["data"]["card_or_nickname"],
                    "id": person.user_id,
                    "status_type": "none",
                    "status_text": "今天没课",
                    "course_name": "-",
                    "teacher": "-",
                    "location": "-",
                    "time_info": "-",
                }
                # 4. 判断具体状态
                if schedule_blocks:
                    # 先预设为“已下课”，如果在下方循环中触发了 current/next，会被覆盖修改
                    person_data["status_type"] = "done"
                    person_data["status_text"] = "已上完课"
                    for block in schedule_blocks:
                        start_dt = block["start_dt"]
                        end_dt = block["end_dt"]
                        time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
                        # 场景 A: 正在上这节课 (当前时间落在起止时间之间)
                        if start_dt <= current_time <= end_dt:
                            person_data["status_type"] = "current"
                            person_data["status_text"] = "正在上课"
                            person_data["course_name"] = block["course_name"]
                            person_data["teacher"] = block["teacher"]
                            person_data["location"] = block["location"]
                            rem_mins = int((end_dt - current_time).total_seconds() / 60)
                            person_data["time_info"] = f"{time_str} (还剩 {rem_mins} 分钟)"
                            break  # 命中当前课，终止判定
                        # 场景 B: 还没到这节课 (按照时间排序找到的第一节还在未来的课)
                        elif current_time < start_dt:
                            person_data["status_type"] = "next"
                            person_data["status_text"] = "下一节课"
                            person_data["course_name"] = block["course_name"]
                            person_data["teacher"] = block["teacher"]
                            person_data["location"] = block["location"]
                            rem_mins = int((start_dt - current_time).total_seconds() / 60)
                            if rem_mins >= 60:
                                rem_str = f"{rem_mins // 60}小时{rem_mins % 60}分钟后"
                            else:
                                rem_str = f"{rem_mins}分钟后"
                            person_data["time_info"] = f"{time_str} ({rem_str})"
                            break  # 命中下节课，终止判定
                    # 场景 C: 所有课程都已结束（循环完毕都没有触发 break）
                    if person_data["status_type"] == "done":
                        last_block = schedule_blocks[-1]
                        person_data["course_name"] = last_block["course_name"]
                        person_data["teacher"] = last_block["teacher"]
                        person_data["location"] = last_block["location"]
                        person_data["time_info"] = (
                            f"最后一节课已于 {last_block['end_dt'].strftime('%H:%M')} 结束"
                        )
                # 5. 将该用户的数据加入到主列表
                render_data["users"].append(person_data)
        sorted_users = sorted(render_data["users"], key=lambda x: x["time_info"][:5])
        render_data["users"] = sorted_users

        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.j2")
        with open(template_path, encoding="utf-8") as f:
            template = Template(f.read())
        html_content = template.render(**render_data)
        output_image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"temp/pic/schedule_{event.group_id}_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.png",
        )
        async with async_playwright() as p:
            # 启动无头浏览器
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(device_scale_factor=3)
            # 将渲染好的 HTML 塞进网页
            await page.set_content(html_content)
            # 【关键点】等待网络空闲，确保所有的 QQ 头像图片都已经加载完毕
            await page.wait_for_load_state("networkidle")
            # 定位到包含所有内容的容器，并对其进行截图 (确保不会截到大片空白)
            element = await page.query_selector("#capture-area")
            await element.screenshot(path=output_image_path)
            await browser.close()

        self.api.groupService.send_group_img(group_id=event.group_id, image_path=output_image_path)
        return
