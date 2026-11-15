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


def test_locked_edit_concurrent_writers_do_not_lose_updates(tmp_path):
    """并发读-改-写经锁串行化，所有更新都保留（丢更新回归）。"""
    from concurrent.futures import ThreadPoolExecutor

    from src.config_schema import locked_edit

    path = tmp_path / "groups.toml"
    path.write_text("[group]\n", encoding="utf-8")

    def add_key(index):
        with locked_edit(path) as document:
            document["group"][f"plugin_{index}"] = True

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add_key, range(40)))

    result = tomlkit.loads(path.read_text(encoding="utf-8")).unwrap()
    assert len(result["group"]) == 40
    assert all(result["group"][f"plugin_{i}"] is True for i in range(40))


def test_file_lock_is_exclusive(tmp_path):
    """持锁期间第二个写者必须等待，不能同时进入临界区。"""
    import threading
    import time

    from src.config_schema import file_lock

    path = tmp_path / "groups.toml"
    path.write_text("a = 1\n", encoding="utf-8")
    inside = []
    release = threading.Event()

    def holder():
        with file_lock(path):
            inside.append("holder")
            release.wait(5)

    def contender():
        with file_lock(path):
            inside.append("contender")

    first = threading.Thread(target=holder)
    first.start()
    for _ in range(200):
        if inside:
            break
        time.sleep(0.01)
    second = threading.Thread(target=contender)
    second.start()
    time.sleep(0.2)
    # holder 未释放前，contender 不得进入。
    assert inside == ["holder"]
    release.set()
    first.join(5)
    second.join(5)
    assert inside == ["holder", "contender"]


def test_file_lock_times_out(tmp_path):
    """锁按进程互斥（Windows msvcrt 以句柄判锁），用子进程持锁验证超时。"""
    import subprocess
    import sys

    from src.config_schema import file_lock

    path = tmp_path / "groups.toml"
    path.write_text("a = 1\n", encoding="utf-8")
    project_root = os.path.dirname(os.path.dirname(__file__))
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import time\n"
                "from src.config_schema import file_lock\n"
                f"with file_lock({str(path)!r}):\n"
                "    print('LOCKED', flush=True)\n"
                "    time.sleep(30)\n"
            ),
        ],
        cwd=project_root,
        stdout=subprocess.PIPE,
        env=dict(os.environ, PYTHONPATH=project_root),
    )
    try:
        # 等子进程确认已持锁（导入可能较慢），再验证主进程获锁超时。
        assert holder.stdout.readline().strip() == b"LOCKED"
        with pytest.raises(TimeoutError):
            with file_lock(path, timeout=0.3):
                pass
    finally:
        holder.terminate()
        holder.wait(timeout=10)
