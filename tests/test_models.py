import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src import Models


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


def test_message_formatted_time_uses_china_standard_time():
    message = Models.Message(send_time=datetime(2026, 8, 2, 0, 30, tzinfo=UTC))

    assert message.formatted_time == "08/02 08:30"


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
        f"数据库模型必须统一定义在 src/Models.py，以下文件存在自定义模型: {violations}"
    )
