"""数据库一键建表脚本

以 src/Models.py 为唯一表结构来源，为 configs/bot.toml 中 [Init] 配置的数据库
创建所有缺失的表，已存在的表不会被修改。

用法：
    uv run python scripts/create_tables.py
"""

import asyncio
import os
import sys

import tomlkit
from sqlalchemy import inspect
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.Models import Base
from utils.Database import build_database_url


def load_database_url() -> URL:
    """从 configs/bot.toml 读取数据库配置并构造连接 URL"""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "configs", "bot.toml"
    )
    if not os.path.exists(config_path):
        sys.exit(f"找不到配置文件：{config_path}")

    with open(config_path, encoding="utf-8") as f:
        init_config = tomlkit.load(f).unwrap().get("Init", {})

    if not init_config.get("database_enable", False):
        sys.exit("bot.toml 中 database_enable 为 false，请先启用数据库再建表")

    keys = {
        "database_username": init_config.get("database_username"),
        "database_address": init_config.get("database_address"),
        "database_passwd": init_config.get("database_passwd"),
        "database_name": init_config.get("database_name"),
    }
    missing = [key for key, value in keys.items() if not value]
    if missing:
        sys.exit(f"bot.toml 缺少以下数据库配置项：{', '.join(missing)}")

    # 使用 URL.create 构造连接串，用户名和密码会由 SQLAlchemy 自动做 URL 转义
    return build_database_url(**keys)


async def create_tables() -> None:
    engine = create_async_engine(load_database_url())
    try:
        async with engine.begin() as conn:
            existing = set(
                await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            )
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        await engine.dispose()
        sys.exit(f"连接数据库或建表失败：{e}")
    await engine.dispose()

    defined = set(Base.metadata.tables)
    created = sorted(defined - existing)
    kept = sorted(defined & existing)
    if created:
        print(f"新建的表：{', '.join(created)}")
    if kept:
        print(f"已存在（跳过）的表：{', '.join(kept)}")
    print("建表完成")


if __name__ == "__main__":
    asyncio.run(create_tables())
