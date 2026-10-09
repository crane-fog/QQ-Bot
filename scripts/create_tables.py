# 数据库建表脚本
# uv run scripts/create_tables.py

import os
import sys

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.Models import Base
from utils.Database import load_database_url


def create_tables() -> None:
    engine = create_engine(load_database_url())
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            existing = set(inspect(conn).get_table_names())
            Base.metadata.create_all(conn)
    except Exception as e:
        engine.dispose()
        sys.exit(f"连接数据库或建表失败：{e}")
    engine.dispose()

    defined = set(Base.metadata.tables)
    created = sorted(defined - existing)
    kept = sorted(defined & existing)
    if created:
        print(f"新建的表：{', '.join(created)}")
    if kept:
        print(f"已存在（跳过）的表：{', '.join(kept)}")
    print("建表完成")


if __name__ == "__main__":
    create_tables()
