"""Bot 配置的共享知识与安全读写原语。

Bot（启动时读取、群开关写回）和部署面板（离线编辑）需要同一份配置知识：
配置文件清单、bot.toml 的字段约定，以及不留下半写文件的替换操作。
本模块是唯一来源，只依赖标准库和 tomlkit，不 import 任何一侧。
"""

import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError

CONFIG_FILES = ("bot.toml", "plugins.toml", "groups.toml", "ai.toml", "scheduler.toml")

# bot.toml 字段约定：section -> key -> (类型, 启动是否必需)。
# 面板据此拒绝白名单之外的表单修改并校验类型；Bot 在必需字段缺失时拒绝启动。
BOT_SCHEMA = {
    "Init": {
        "server_address": (str, True),
        "client_address": (str, True),
        "bot_name": (str, True),
        "debug": (bool, True),
        "database_enable": (bool, True),
        "database_username": (str, True),
        "database_address": (str, True),
        "database_passwd": (str, True),
        "database_name": (str, True),
        "owner_id": (int, True),
        "assistant_group": (int, True),
        "enable_webhook_handler": (bool, True),
    },
    "Gitea": {
        "webhook_handler_address": (str, True),
        "webhook_response_group": (int, True),
        "api_url": (str, True),
        "api_token": (str, True),
    },
}


def load_toml(path):
    """解析 TOML 文件；语法或编码问题转成可读的 ValueError。

    返回 tomlkit 文档，写回的调用方因此保留注释与排版。异常消息只含位置、
    不含解析器原文——后者可能携带源文件行（含密码）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            return tomlkit.load(f)
    except ParseError as exc:
        line, col = getattr(exc, "line", None), getattr(exc, "col", None)
        where = f"（第 {line} 行，第 {col} 列）" if line else ""
        raise ValueError(f"{Path(path).name} 语法错误{where}，请检查格式") from None
    except UnicodeError:
        raise ValueError(f"{Path(path).name} 必须采用 UTF-8 编码") from None


def atomic_write(path: Path, source: str, mode: int = 0o600) -> None:
    """原子替换文件内容：同目录临时文件 + fsync + rename，不留半写状态。

    已存在的文件保留原有权限位；新建文件用 `mode`。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        current = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        current = mode
    descriptor, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(source)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, current)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _lock_byte(handle) -> None:
    """对锁文件首字节加排他锁（跨平台）。"""
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_byte(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    """对 ``<path>.lock`` 加跨进程排他锁，串行化同一文件的读-改-写。

    atomic_write 只保证单次替换原子，保护不了整个读-改-写周期；Bot（群指令）
    与面板可能并发编辑同一配置，需此锁避免互相覆盖丢更新。锁加在独立的 .lock
    文件上，不影响对目标文件本身的原子替换。超时未获锁则抛 TimeoutError。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = path.with_name(path.name + ".lock")
    handle = open(lock_path, "a+b")
    deadline = time.monotonic() + timeout
    locked = False
    try:
        while True:
            try:
                _lock_byte(handle)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"获取配置锁超时：{lock_path.name}") from None
                time.sleep(0.05)
        yield
    finally:
        # 只有真正持锁才解锁；获锁失败时解锁会抛 PermissionError 掩盖原异常。
        if locked:
            _unlock_byte(handle)
        handle.close()


@contextmanager
def locked_edit(path: Path, timeout: float = 10.0):
    """在跨进程排他锁内读取 TOML，交由调用方修改后原子写回。

    用法：``with locked_edit(p) as doc: doc[...] = ...``。读、改、写全程持锁，
    保证并发写者串行化、后写者基于最新内容，不丢更新。
    """
    with file_lock(path, timeout=timeout):
        document = load_toml(path)
        yield document
        atomic_write(path, tomlkit.dumps(document))
