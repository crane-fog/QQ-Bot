import os
from datetime import date, datetime, time, timedelta

import requests
import xlrd
from jinja2 import Template
from playwright.async_api import async_playwright
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.Models import Courses, PersonalSchedule
from src.PrintLog import Log
from utils.CQHelper import CQHelper


class Schedule(Plugins):
    def __init__(self, bot):
        super().__init__(bot)
        self.name = "Schedule"
        self.type = "Group"
        self.author = "Heai"
        self.introduction = """
                                查看群友课表\n导入个人课表：1系统-个人课表-(下滑)查看教材-导出-将导出的 textbook.xls 文件发送到群聊中\n查看排名：rank，默认今日 + 显示课时数，week = 本周，time = 显示时长
                                usage: Schedule (rank (week) (time))
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
        self.playwright = None
        self.browser = None
        with open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.j2"),
            encoding="utf-8",
        ) as f:
            self.template = Template(f.read())

    @plugin_main(call_word=["Schedule", "[CQ:file,file=textbook"], require_db=True)
    async def main(self, event: GroupMessageEvent, debug: bool):
        calendar = self.config.get("current_calendar", 121)
        first_day = datetime.strptime(self.config.get("first_day"), "%Y-%m-%d").date()

        # 排名
        if "rank" in event.message:
            is_week_rank = "week" in event.message
            show_time = "time" in event.message
            await self._handle_rank(event, calendar, first_day, is_week_rank, show_time)
            return

        # 导入课表
        if event.message.startswith("[CQ:file,file=textbook"):
            cq = CQHelper.load_cq(event.message)
            file_data = api.messageService.get_group_file_url(
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
                api.groupService.send_group_msg(
                    group_id=event.group_id,
                    message=f"已导入{event.user_id}课表文件",
                )
            except Exception as e:
                Log.error(f"解析课表文件失败，错误信息: {e}")
                api.groupService.send_group_msg(
                    group_id=event.group_id, message=f"解析{event.user_id}课表文件失败"
                )
            return

        # 查看课表
        current_time = datetime.now()
        today = date.today()
        delta_days = (today - first_day).days
        current_week = (delta_days // 7) + 1
        weekday_num = today.isoweekday()

        render_data = {"current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"), "users": []}

        # 一次性获取所有群成员信息并构建字典
        group_members_data = await api.asyncGroupService.get_group_member_list(
            group_id=event.group_id, no_cache=False
        )
        member_dict = {
            member["user_id"]: member["card_or_nickname"]
            for member in group_members_data.get("data", [])
        }

        async with self.session_factory() as session:
            stmt = select(PersonalSchedule).where(
                PersonalSchedule.group_id == event.group_id,
                PersonalSchedule.calendar_id == calendar,
            )
            persons: list[PersonalSchedule] = (await session.execute(stmt)).scalars().all()

            # 收集所有需要查询的课程代码
            all_new_codes = []
            all_old_codes = []
            for p in persons:
                if p.is_new_code:
                    all_new_codes.extend(p.new_course_codes)
                else:
                    all_old_codes.extend(p.course_codes)

            # 单次查询获取所有今日课程数据
            stmt = select(Courses).where(
                Courses.calendar_id == calendar,
                or_(
                    Courses.new_course_code.in_(all_new_codes),
                    Courses.course_code.in_(all_old_codes),
                ),
                Courses.time_info.contains([{"day_of_week": weekday_num, "weeks": [current_week]}]),
            )
            all_today_courses = (await session.execute(stmt)).scalars().all()

            for person in persons:
                # 筛选出属于该用户的今日课程
                if person.is_new_code:
                    today_courses = [
                        c for c in all_today_courses if c.new_course_code in person.new_course_codes
                    ]
                else:
                    today_courses = [
                        c for c in all_today_courses if c.course_code in person.course_codes
                    ]

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
                    "name": member_dict.get(person.user_id, "未知用户"),
                    "id": person.user_id,
                    "status_type": "none",
                    "status_text": "今天没课",
                    "course_name": "-",
                    "teacher": "-",
                    "location": "-",
                    "time_info": "无",
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

        html_content = self.template.render(**render_data)
        output_image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"temp/pic/schedule_{event.group_id}_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.png",
        )
        await self._render_html_to_image(html_content, output_image_path)
        await api.asyncGroupService.send_group_img(
            group_id=event.group_id, image_path=output_image_path
        )
        return

    async def _handle_rank(
        self,
        event: GroupMessageEvent,
        calendar: int,
        first_day: date,
        is_week: bool,
        show_time: bool,
    ):
        """处理课时数排名请求"""
        today = date.today()
        delta_days = (today - first_day).days
        current_week = (delta_days // 7) + 1
        weekday_num = today.isoweekday()

        # 获取所有用户的排名数据
        rank_data = []

        # 一次性获取所有群成员信息并构建字典
        group_members_data = await api.asyncGroupService.get_group_member_list(
            group_id=event.group_id, no_cache=False
        )
        member_dict = {
            member["user_id"]: member["card_or_nickname"]
            for member in group_members_data.get("data", [])
        }

        async with self.session_factory() as session:
            stmt = select(PersonalSchedule).where(
                PersonalSchedule.group_id == event.group_id,
                PersonalSchedule.calendar_id == calendar,
            )
            persons: list[PersonalSchedule] = (await session.execute(stmt)).scalars().all()

            # 收集所有需要查询的课程代码
            all_new_codes = []
            all_old_codes = []
            for p in persons:
                if p.is_new_code:
                    all_new_codes.extend(p.new_course_codes)
                else:
                    all_old_codes.extend(p.course_codes)

            # 单次查询获取所有课程数据（数据库自动去重）
            stmt = select(Courses).where(
                Courses.calendar_id == calendar,
                or_(
                    Courses.new_course_code.in_(all_new_codes),
                    Courses.course_code.in_(all_old_codes),
                ),
            )
            all_courses = (await session.execute(stmt)).scalars().all()

            # 计算每个用户的课时数
            for person in persons:
                total_periods = 0

                # 筛选出属于该用户的课程
                if person.is_new_code:
                    person_courses = [
                        c for c in all_courses if c.new_course_code in person.new_course_codes
                    ]
                else:
                    person_courses = [
                        c for c in all_courses if c.course_code in person.course_codes
                    ]

                # 统计课时
                if is_week:
                    # 本周排名：统计周一到周日的所有课时
                    for day in range(1, 8):
                        for course in person_courses:
                            for info in course.time_info:
                                if info["day_of_week"] == day and current_week in info["weeks"]:
                                    total_periods += len(info["periods"])
                else:
                    # 今日排名：只统计今天的课时
                    for course in person_courses:
                        for info in course.time_info:
                            if info["day_of_week"] == weekday_num and current_week in info["weeks"]:
                                total_periods += len(info["periods"])

                if total_periods > 0:  # 只统计有课的用户
                    rank_data.append(
                        {
                            "name": member_dict.get(person.user_id, "未知用户"),
                            "user_id": person.user_id,
                            "periods": total_periods,
                        }
                    )

        # 按课时数降序排序
        rank_data.sort(key=lambda x: x["periods"], reverse=True)

        # 构造模板渲染数据
        current_time = datetime.now()
        rank_type = "本周" if is_week else "今日"
        render_data = {
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_rank_mode": True,
            "rank_title": f"{rank_type}{'总时长' if show_time else '总课时数'}排名",
            "show_time": show_time,
            "users": [],
        }

        # 添加排名数据
        for idx, data in enumerate(rank_data, 1):
            if show_time:
                hours = data["periods"] * self.COURSE_TIME / timedelta(hours=1)
                value_text = f"{hours:.2f}小时"
            else:
                value_text = f"{data['periods']}节"

            render_data["users"].append(
                {
                    "rank": idx,
                    "name": data["name"],
                    "id": data["user_id"],
                    "value": value_text,
                }
            )

        # 渲染模板并生成图片
        html_content = self.template.render(**render_data)

        output_image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"temp/pic/rank_{event.group_id}_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.png",
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(device_scale_factor=2)
            await page.set_content(html_content)
            await page.wait_for_load_state("networkidle")
            element = await page.query_selector("#capture-area")
            await element.screenshot(path=output_image_path)
            await browser.close()

        await api.asyncGroupService.send_group_img(
            group_id=event.group_id, image_path=output_image_path
        )

    async def _get_browser(self):
        if self.browser is None or not self.browser.is_connected():
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
        return self.browser

    async def _render_html_to_image(self, html_content: str, output_image_path: str):
        browser = await self._get_browser()
        page = await browser.new_page(device_scale_factor=2)
        try:
            await page.set_content(html_content, wait_until="load")
            await page.evaluate("""async () => {
                const imgs = Array.from(document.querySelectorAll("img"));
                await Promise.all(imgs.map(img => img.complete ? null : new Promise(r => { img.onload = r; img.onerror = r; })));
            }""")
            element = await page.query_selector("#capture-area")
            await element.screenshot(path=output_image_path)
        finally:
            await page.close()
