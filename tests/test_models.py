from datetime import UTC, datetime

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
