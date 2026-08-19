"""数据库连接相关的公共工具。"""

from sqlalchemy.engine import URL


def build_database_url(
    database_username: str,
    database_passwd: str,
    database_address: str,
    database_name: str,
) -> URL:
    """根据 bot.toml 的 [Init] 配置构造异步 PostgreSQL 连接 URL。

    使用 ``URL.create`` 构造连接串，用户名和密码会由 SQLAlchemy 自动做 URL 转义，
    无需调用方手动处理含 ``@``、``:`` 等特殊字符的密码。
    """
    host, port = _split_address(database_address)
    return URL.create(
        "postgresql+asyncpg",
        username=database_username,
        password=database_passwd,
        host=host,
        port=port,
        database=database_name,
    )


def _split_address(address: str) -> tuple[str, int | None]:
    """将 ``host:port`` 拆分为 ``(host, port)``；不含端口时返回 ``(address, None)``。"""
    if ":" in address:
        host, _, port = address.rpartition(":")
        if port.isdigit():
            return host, int(port)
    return address, None
