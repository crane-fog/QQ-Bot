from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, mock_open, patch

import pytest
from sqlalchemy.dialects import postgresql

from plugins.DataImport.DataImport import DataImport
from src.Models import LineCounts, Scores, StuList

if TYPE_CHECKING:
    from src.Api import Api
    from src.Bot import Bot


class FakeAsyncSession:
    def __init__(self):
        self.executions = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def begin(self):
        return self

    async def execute(self, statement, parameters=None):
        self.executions.append((statement, parameters))


class FakeSessionFactory:
    def __init__(self):
        self.sessions = []

    def __call__(self):
        session = FakeAsyncSession()
        self.sessions.append(session)
        return session


def make_plugin():
    group_service = SimpleNamespace(send_group_msg=Mock())
    session_factory = FakeSessionFactory()
    plugin = object.__new__(DataImport)
    # 测试替身只提供被测代码访问的属性；经 object 中转以通过 basedpyright 的重叠性检查
    plugin.bot = cast("Bot", cast(object, SimpleNamespace(owner_id=10001)))
    plugin.api = cast("Api", cast(object, SimpleNamespace(groupService=group_service)))
    plugin.session_factory = cast(Any, session_factory)
    return plugin, group_service, session_factory


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_name", "file_content", "expected_model", "expected_rows"),
    [
        (
            "scores",
            "1 2350001 95\n2 2350002 80\n",
            Scores,
            [
                {"semester": 252620, "stu_id": 2350001, "score": 95},
                {"semester": 252620, "stu_id": 2350002, "score": 80},
            ],
        ),
        (
            "linecounts",
            "2350002 20\n2350001 10\n",
            LineCounts,
            [
                {"semester": 252620, "stu_id": 2350001, "count": 10, "rank": 0},
                {"semester": 252620, "stu_id": 2350002, "count": 20, "rank": 1},
            ],
        ),
        (
            "stulists",
            "2350001 Alice\n2350002 Bob\n",
            StuList,
            [
                {"semester": 252620, "stu_id": 2350001, "name": "Alice", "class_": 0},
                {"semester": 252620, "stu_id": 2350002, "name": "Bob", "class_": 0},
            ],
        ),
        (
            "stulists_detail",
            "软件工程03 2350001 Alice\n软件工程12 2350002 Bob\n",
            StuList,
            [
                {"semester": 252620, "stu_id": 2350001, "name": "Alice", "class_": 3},
                {"semester": 252620, "stu_id": 2350002, "name": "Bob", "class_": 12},
            ],
        ),
    ],
)
async def test_data_import_parses_and_replaces_semester_rows(
    table_name, file_content, expected_model, expected_rows
):
    plugin, _, session_factory = make_plugin()
    event = SimpleNamespace(
        message=f"DataImport {table_name} 252620",
        user_id=10001,
        group_id=20001,
    )

    with patch("builtins.open", mock_open(read_data=file_content)):
        await cast(Any, DataImport.main).__wrapped__(plugin, event, debug=False)

    assert len(session_factory.sessions) == 1
    delete_statement, _ = session_factory.sessions[0].executions[0]
    insert_statement, inserted_rows = session_factory.sessions[0].executions[1]
    compiled_delete = delete_statement.compile(dialect=postgresql.dialect())

    assert delete_statement.table.name == expected_model.__tablename__
    assert 252620 in compiled_delete.params.values()
    assert insert_statement.table.name == expected_model.__tablename__
    assert inserted_rows == expected_rows


@pytest.mark.asyncio
async def test_data_import_rejects_unknown_table_without_database_access():
    plugin, group_service, session_factory = make_plugin()
    event = SimpleNamespace(
        message="DataImport unknown 252620",
        user_id=10001,
        group_id=20001,
    )

    await cast(Any, DataImport.main).__wrapped__(plugin, event, debug=False)

    assert session_factory.sessions == []
    group_service.send_group_msg.assert_called_once()
