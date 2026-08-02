from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from plugins.GroupApprove.GroupApprove import GroupApprove
from plugins.LineCount.LineCount import LineCount
from plugins.QiuDao.QiuDao import QiuDao


class FakeResult:
    def __init__(self, *, first=None, rows=None):
        self._first = first
        self._rows = rows or []

    def first(self):
        return self._first

    def all(self):
        return self._rows


class FakeAsyncSession:
    def __init__(self, result):
        self.result = result
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def begin(self):
        return self

    async def execute(self, statement):
        self.statements.append(statement)
        return self.result


def plugin_with_result(plugin_class, result):
    session = FakeAsyncSession(result)
    plugin = object.__new__(plugin_class)
    plugin.session_factory = lambda: session
    return plugin, session


def assert_query_contract(statement, expected_tables, expected_parameters):
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled).lower()

    for table in expected_tables:
        assert table in sql
    assert set(compiled.params.values()) == set(expected_parameters)


@pytest.mark.asyncio
async def test_line_count_query_returns_shared_model_data():
    result = FakeResult(first=SimpleNamespace(rank=7, count=1234, qq_id="10001"))
    plugin, session = plugin_with_result(LineCount, result)

    data = await plugin.query_by_stu_id(2350001, 252620)

    assert data == {"rank": 7, "count": 1234, "user_id": "10001"}
    assert_query_contract(
        session.statements[0],
        expected_tables={"linecounts", "stu_qq_id_map"},
        expected_parameters={2350001, 252620},
    )


@pytest.mark.asyncio
async def test_line_count_query_returns_none_when_student_is_missing():
    plugin, _ = plugin_with_result(LineCount, FakeResult())

    assert await plugin.query_by_stu_id(2350001, 252620) is None


@pytest.mark.asyncio
async def test_qiu_dao_query_returns_shared_model_data():
    result = FakeResult(first=SimpleNamespace(score=3, qq_id="10001"))
    plugin, session = plugin_with_result(QiuDao, result)

    data = await plugin.query_by_stu_id(2350001, 252620)

    assert data == {"score": 3, "user_id": "10001"}
    assert_query_contract(
        session.statements[0],
        expected_tables={"scores", "stu_qq_id_map"},
        expected_parameters={2350001, 252620},
    )


@pytest.mark.asyncio
async def test_qiu_dao_query_returns_none_when_student_is_missing():
    plugin, _ = plugin_with_result(QiuDao, FakeResult())

    assert await plugin.query_by_stu_id(2350001, 252620) is None


@pytest.mark.asyncio
async def test_group_approve_loads_student_and_semester_pairs():
    plugin, session = plugin_with_result(
        GroupApprove,
        FakeResult(rows=[(2350001, 252620), (2350002, 252621), (2350001, 252620)]),
    )

    data = await plugin.select_all_inform()

    assert data == {(2350001, 252620), (2350002, 252621)}
    assert_query_contract(
        session.statements[0],
        expected_tables={"stulists"},
        expected_parameters=set(),
    )
