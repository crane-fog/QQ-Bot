import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql

from src import models

EXPECTED_SCHEMAS = {
    "messages": {
        "columns": {
            "id": ("BIGINT", False),
            "user_id": ("BIGINT", False),
            "group_id": ("BIGINT", False),
            "msg": ("TEXT", False),
            "send_time": ("TIMESTAMP WITH TIME ZONE", False),
            "msg_id": ("BIGINT", False),
            "user_nickname": ("TEXT", False),
            "user_card": ("TEXT", False),
        },
        "primary_key": ["id"],
    },
    "ask_messages": {
        "columns": {
            "id": ("BIGINT", False),
            "discussion_id": ("INTEGER", False),
            "id_of_message": ("BIGINT", False),
        },
        "primary_key": ["id"],
    },
    "scores": {
        "columns": {
            "semester": ("INTEGER", False),
            "stu_id": ("INTEGER", False),
            "score": ("INTEGER", False),
        },
        "primary_key": ["semester", "stu_id"],
    },
    "linecounts": {
        "columns": {
            "semester": ("INTEGER", False),
            "stu_id": ("INTEGER", False),
            "count": ("INTEGER", False),
            "rank": ("INTEGER", False),
        },
        "primary_key": ["semester", "stu_id"],
    },
    "stu_qq_id_map": {
        "columns": {
            "stu_id": ("INTEGER", False),
            "qq_id": ("VARCHAR", True),
        },
        "primary_key": ["stu_id"],
    },
    "stulists": {
        "columns": {
            "semester": ("INTEGER", False),
            "stu_id": ("INTEGER", False),
            "name": ("TEXT", True),
            "class": ("INTEGER", True),
        },
        "primary_key": ["semester", "stu_id"],
    },
    "courses": {
        "columns": {
            "calendar_id": ("INTEGER", False),
            "new_course_code": ("TEXT", False),
            "course_code": ("TEXT", False),
            "teacher": ("TEXT", False),
            "course_name": ("TEXT", False),
            "time_info": ("JSONB", False),
        },
        "primary_key": ["calendar_id", "new_course_code", "course_code", "teacher"],
    },
    "personal_schedule": {
        "columns": {
            "calendar_id": ("INTEGER", False),
            "user_id": ("BIGINT", False),
            "group_id": ("BIGINT", False),
            "is_new_code": ("BOOLEAN", False),
            "new_course_codes": ("JSONB", False),
            "course_codes": ("JSONB", False),
        },
        "primary_key": ["calendar_id", "user_id", "group_id"],
    },
}


def defines_database_model(source, filename="<unknown>"):
    tree = ast.parse(source, filename=filename)
    declarative_base_names = {"declarative_base"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "declarative_base":
                    declarative_base_names.add(alias.asname or alias.name)

    calls_declarative_base = any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in declarative_base_names
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "declarative_base"
        )
        for node in ast.walk(tree)
    )
    defines_table_name = any(
        isinstance(statement, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "__tablename__"
            for target in (
                statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            )
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for statement in node.body
    )
    return calls_declarative_base or defines_table_name


@pytest.mark.parametrize(("table_name", "expected"), EXPECTED_SCHEMAS.items())
def test_model_schema_matches_database_contract(table_name, expected):
    table = models.Base.metadata.tables[table_name]

    actual_columns = {
        column.name: (column.type.compile(dialect=postgresql.dialect()), column.nullable)
        for column in table.columns
    }

    assert actual_columns == expected["columns"]
    assert [column.name for column in table.primary_key.columns] == expected["primary_key"]


def test_shared_metadata_contains_only_expected_tables():
    assert set(models.Base.metadata.tables) == set(EXPECTED_SCHEMAS)


def test_attribute_mapping_and_unique_constraint_are_preserved():
    assert models.StuList.class_.property.columns[0].name == "class"
    assert models.AskMessage.id_of_message.property.columns[0].unique is True


def test_message_formatted_time_uses_china_standard_time():
    message = models.Message(send_time=datetime(2026, 8, 2, 0, 30, tzinfo=UTC))

    assert message.formatted_time == "08:30"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('# declarative_base\nvalue = "__tablename__"', False),
        ("from sqlalchemy.orm import declarative_base as base\nBase = base()", True),
        ("import sqlalchemy.orm as orm\nBase = orm.declarative_base()", True),
        ('class Message:\n    __tablename__ = "messages"', True),
    ],
)
def test_database_model_detection_uses_python_syntax(source, expected):
    assert defines_database_model(source) is expected


def test_plugins_do_not_define_their_own_models():
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    violations = []
    for path in plugins_dir.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if defines_database_model(source, filename=str(path)):
            violations.append(str(path.relative_to(plugins_dir.parent)))
    assert violations == [], (
        f"数据库模型必须统一定义在 src/models.py，以下文件存在自定义模型: {violations}"
    )
