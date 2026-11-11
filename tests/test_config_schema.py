"""src.config_schema：单一来源的字段约定与安全读写原语。"""

import os
import stat

import pytest
import tomlkit

from src.config_schema import BOT_SCHEMA, CONFIG_FILES, atomic_write, load_toml


def test_schema_covers_the_template():
    """模板与字段约定互为镜像：任何一侧漂移都在这里暴露。"""
    document = tomlkit.load(open("configs/bot.toml.template", encoding="utf-8")).unwrap()
    for section, fields in BOT_SCHEMA.items():
        table = document[section]
        for key, (expected, _) in fields.items():
            assert type(table[key]) is expected, f"{section}.{key} 与模板类型不一致"


def test_config_files_match_templates():
    import os

    for name in CONFIG_FILES:
        assert os.path.isfile(os.path.join("configs", name + ".template"))


def test_load_toml_reports_location_without_source(tmp_path):
    path = tmp_path / "bot.toml"
    path.write_text('database_passwd = "s3cret"\nbroken = ', encoding="utf-8")
    with pytest.raises(ValueError, match="bot.toml 语法错误（第 2 行") as error:
        load_toml(path)
    assert "s3cret" not in str(error.value)
    assert "Unexpected" not in str(error.value)


def test_load_toml_rejects_non_utf8(tmp_path):
    path = tmp_path / "bot.toml"
    path.write_bytes(b"a = 1\n\xff\xfe\n")
    with pytest.raises(ValueError, match="UTF-8"):
        load_toml(path)


def test_atomic_write_keeps_mode_and_leaves_no_temporary(tmp_path):
    path = tmp_path / "nested" / "groups.toml"
    path.parent.mkdir()
    path.write_text("a = 1\n", encoding="utf-8")
    path.chmod(0o640)

    atomic_write(path, "a = 2\n")

    assert path.read_text(encoding="utf-8") == "a = 2\n"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert not list(tmp_path.rglob(".tmp-*"))


def test_atomic_write_new_file_uses_default_mode(tmp_path):
    path = tmp_path / "new.toml"
    atomic_write(path, "a = 1\n")
    assert path.read_text(encoding="utf-8") == "a = 1\n"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
