from sqlalchemy.engine import make_url

from utils.Database import build_database_url


def test_build_database_url_splits_host_and_port():
    url = build_database_url(
        database_username="admin",
        database_passwd="secret",
        database_address="bot.database.address:3306",
        database_name="bot",
    )

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "admin"
    assert url.password == "secret"
    assert url.host == "bot.database.address"
    assert url.port == 3306
    assert url.database == "bot"


def test_build_database_url_escapes_special_characters_in_password():
    url = build_database_url(
        database_username="admin",
        database_passwd="p@ss:w/ord",
        database_address="db.example.com:5432",
        database_name="bot",
    )

    # 渲染后再次解析，密码应能无损还原，证明特殊字符被正确转义
    reparsed = make_url(url.render_as_string(hide_password=False))
    assert reparsed.password == "p@ss:w/ord"


def test_build_database_url_without_port():
    url = build_database_url(
        database_username="admin",
        database_passwd="secret",
        database_address="localhost",
        database_name="bot",
    )

    assert url.host == "localhost"
    assert url.port is None
