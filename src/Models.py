from datetime import timedelta, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    group_id = Column(BigInteger, nullable=False)
    msg = Column(Text, nullable=False)
    send_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    msg_id = Column(BigInteger, nullable=False, default=0)
    user_nickname = Column(Text, nullable=False, default=" ")
    user_card = Column(Text, nullable=False, default=" ")

    @property
    def formatted_time(self) -> str:
        return self.send_time.astimezone(timezone(timedelta(hours=8))).strftime("%m/%d %H:%M")


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discussion_id = Column(Integer, nullable=False)
    id_of_message = Column(BigInteger, nullable=False, unique=True)


class Scores(Base):
    __tablename__ = "scores"

    semester = Column(Integer, primary_key=True)
    stu_id = Column(Integer, primary_key=True)
    score = Column(Integer, nullable=False)


class LineCounts(Base):
    __tablename__ = "linecounts"

    semester = Column(Integer, primary_key=True)
    stu_id = Column(Integer, primary_key=True)
    count = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)


class StuId(Base):
    __tablename__ = "stu_qq_id_map"

    stu_id = Column(Integer, primary_key=True)
    qq_id = Column(String)


class StuList(Base):
    __tablename__ = "stulists"

    semester = Column(Integer, primary_key=True)
    stu_id = Column(Integer, primary_key=True)
    name = Column(Text)
    class_ = Column("class", Integer)


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


class Memory(Base):
    __tablename__ = "memories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=True)
    group_id = Column(BigInteger, nullable=True)
    content = Column(Text, nullable=False)
    memory_type = Column(Integer, nullable=False)  # 0=人记忆 1=群记忆
    source = Column(Integer, nullable=False)  # 0=主动 1=定时 2=滚动
    stale = Column(Integer, nullable=False)  # 0=强 1=弱 2=失效
    message_start_id = Column(BigInteger, nullable=True)
    message_end_id = Column(BigInteger, nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def formatted_time(self) -> str:
        return self.updated_at.astimezone(timezone(timedelta(hours=8))).strftime("%m/%d %H:%M")


class GroupStatus(Base):
    __tablename__ = "group_status"

    group_id = Column(BigInteger, primary_key=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    description = Column(Text, nullable=False)


Index(
    "idx_memories_content_trgm",
    Memory.content,
    postgresql_using="gin",
    postgresql_ops={"content": "gin_trgm_ops"},
)
