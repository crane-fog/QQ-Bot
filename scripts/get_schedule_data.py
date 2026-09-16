# 用于 Schedule 插件获取同济大学课程信息的脚本，需每学期执行一次，手动填写 calendar_id 和 session_id
# uv run scripts/get_schedule_data.py

import os
import re
import sys

import requests
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.Models import Courses
from utils.Database import load_database_url

calendar_id = 122  # 26271
session_id = ""  # 自行登录1系统获取


database = create_engine(load_database_url())
Session = sessionmaker(bind=database)


def parse_schedule(schedule_str: str) -> list[dict]:
    weekday_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
    entries = re.split(r"[；\n]+", schedule_str.strip())
    pattern = re.compile(r"([一二三四五六日天])：([\d\-,]+)\[(.*?)\]\((.*?)\)")
    parsed_data = []
    for entry in entries:
        if not entry.strip():
            continue
        match = pattern.search(entry)
        if match:
            weekday_str, periods_str, weeks_str, location = match.groups()
            weekday = weekday_map.get(weekday_str)
            periods = []
            for p in periods_str.split(","):
                if "-" in p:
                    start, end = map(int, p.split("-"))
                    periods.extend(range(start, end + 1))
                else:
                    periods.append(int(p))
            weeks = []
            week_parts = re.split(r"\s+|,|，", weeks_str.strip())
            for part in week_parts:
                if not part:
                    continue
                part_match = re.match(r"(\d+)(?:-(\d+))?(单|双)?", part)
                if part_match:
                    start = int(part_match.group(1))
                    end = int(part_match.group(2)) if part_match.group(2) else start
                    flag = part_match.group(3)

                    for w in range(start, end + 1):
                        if flag == "单" and w % 2 == 0:
                            continue
                        if flag == "双" and w % 2 != 0:
                            continue
                        weeks.append(w)
            weeks = sorted(list(set(weeks)))
            parsed_data.append(
                {"day_of_week": weekday, "periods": periods, "weeks": weeks, "location": location}
            )
    return parsed_data


def get_dept_list(session_id: str) -> list[str]:
    base_url = (
        "https://1.tongji.edu.cn/api/userservice/dept/findDept?virtualDept=0&type=1&manageDept=1"
    )
    data = requests.get(
        base_url,
        cookies={"sessionid": session_id},
    )
    result = []
    for item in data.json().get("data", []):
        dept_id = item.get("deptCode")
        if dept_id is not None:
            result.append(dept_id)
    return result


def get_course_list(session_id: str, calendar_id: int, dept_id: str) -> list[dict]:
    base_url = "https://1.tongji.edu.cn/api/arrangementservice/manualArrange/pagePrint?profile"
    data = requests.post(
        base_url,
        cookies={"sessionid": session_id},
        json={"condition": {"calendar": calendar_id, "college": dept_id}},
    )
    result = []
    for item in data.json().get("data", {}).get("list", []):
        course_time: str = item.get("courseTime", "")
        time_info = parse_schedule(course_time)
        new_course_code = item.get("newCourseCode", "")
        if new_course_code is None:
            new_course_code = ""
        else:
            new_course_code += item.get("code", "00")[-2:]
        result.append(
            {
                "calendar_id": calendar_id,
                "new_course_code": new_course_code,
                "course_code": item.get("code", ""),
                "teacher": item.get("teacherName", ""),
                "course_name": item.get("courseName", ""),
                "time_info": time_info,
            }
        )
    return result


def merge_courses_by_teacher(courses: list[dict]) -> list[dict]:
    course_dict = {}
    for course in courses:
        # 创建一个不包含 teacher 的 key
        key = (
            course["calendar_id"],
            course["new_course_code"],
            course["course_code"],
            course["course_name"],
            str(course["time_info"]),  # 转换为字符串以便作为 key
        )
        if key in course_dict:
            # 如果已存在相同的课程，将 teacher 追加到列表中
            course_dict[key]["teachers"].append(course["teacher"])
        else:
            # 否则创建新记录
            course_dict[key] = {
                "calendar_id": course["calendar_id"],
                "new_course_code": course["new_course_code"],
                "course_code": course["course_code"],
                "course_name": course["course_name"],
                "time_info": course["time_info"],
                "teachers": [course["teacher"]],
            }

    # 将 teachers 列表合并为字符串
    merged_courses = []
    for course_data in course_dict.values():
        merged_courses.append(
            {
                "calendar_id": course_data["calendar_id"],
                "new_course_code": course_data["new_course_code"],
                "course_code": course_data["course_code"],
                "teacher": "、".join(course_data["teachers"]),
                "course_name": course_data["course_name"],
                "time_info": course_data["time_info"],
            }
        )

    return merged_courses


if __name__ == "__main__":
    if session_id == "":
        print("请在代码中填写 session_id 后再运行")
        exit(1)
    dept_list = get_dept_list(session_id)
    all_courses = []
    for dept_id in dept_list:
        all_courses.extend(get_course_list(session_id, calendar_id, dept_id))

    # 合并除了 teacher 以外其他字段相同的课程
    all_courses = merge_courses_by_teacher(all_courses)

    with Session() as session:
        stmt = insert(Courses).values(all_courses)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["calendar_id", "new_course_code", "course_code", "teacher"],
            set_={
                "course_name": stmt.excluded.course_name,
                "time_info": stmt.excluded.time_info,
            },
        )

        session.execute(upsert_stmt)
        session.commit()
        print(f"成功插入 {len(all_courses)} 条数据")
